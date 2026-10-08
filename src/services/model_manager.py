"""Gestionnaire de téléchargement et cache des modèles Whisper."""

from collections.abc import Callable
import os
from pathlib import Path
import re
import sys
import threading
from typing import Any

from faster_whisper.utils import _MODELS
import huggingface_hub
import tqdm

from src.utils.helpers import format_file_size

# Modèles et tailles approximatives
MODEL_SIZES = {
    "tiny": 75 * 1024 * 1024,
    "tiny.en": 75 * 1024 * 1024,
    "base": 145 * 1024 * 1024,
    "base.en": 145 * 1024 * 1024,
    "small": 480 * 1024 * 1024,
    "small.en": 480 * 1024 * 1024,
    "medium": 1500 * 1024 * 1024,
    "medium.en": 1500 * 1024 * 1024,
    "large-v3": 3100 * 1024 * 1024,
}


class ModelProgressTqdm(tqdm.tqdm):
    """Intercepteur de progression tqdm pour Hugging Face snapshot_download."""
    callback: Callable[[int, int, str], None] | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def update(self, n=1):
        super().update(n)
        if ModelProgressTqdm.callback and self.total and self.total > 0:
            try:
                desc = getattr(self, "desc", "") or "Téléchargement"
                ModelProgressTqdm.callback(self.n, self.total, desc)
            except Exception:
                pass


class ModelManager:
    """Gère la vérification et le téléchargement transparent des modèles Whisper."""

    @staticmethod
    def get_repo_id(model_size_or_id: str) -> str:
        if re.match(r".*/.*", model_size_or_id):
            return model_size_or_id
        repo_id = _MODELS.get(model_size_or_id)
        if not repo_id:
            return f"Systran/faster-whisper-{model_size_or_id}"
        return repo_id

    @classmethod
    def is_model_cached(cls, model_size_or_id: str) -> bool:
        """Vérifie rapidement si tous les fichiers du modèle sont déjà téléchargés."""
        try:
            from faster_whisper.utils import download_model
            download_model(model_size_or_id, local_files_only=True)
            return True
        except Exception:
            return False

    @classmethod
    def ensure_model_available(
        cls,
        model_size_or_id: str,
        progress_callback: Callable[[int, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> str:
        """
        Télécharge le modèle si nécessaire avec un retour en temps réel vers l'UI.
        Renvoie le chemin local du modèle.
        """
        if cls.is_model_cached(model_size_or_id):
            if progress_callback:
                progress_callback(100, f"Modèle '{model_size_or_id}' prêt en local")
            from faster_whisper.utils import download_model
            return download_model(model_size_or_id, local_files_only=True)

        repo_id = cls.get_repo_id(model_size_or_id)
        approx_size = MODEL_SIZES.get(model_size_or_id, 400 * 1024 * 1024)
        approx_size_str = format_file_size(approx_size)

        if progress_callback:
            progress_callback(
                2,
                f"📥 Téléchargement initial du modèle '{model_size_or_id}' (~{approx_size_str}) depuis HuggingFace..."
            )

        allow_patterns = [
            "config.json",
            "preprocessor_config.json",
            "model.bin",
            "tokenizer.json",
            "vocabulary.*",
        ]

        # Callback pour la progression de téléchargement en direct
        last_logged_pct = [-1]

        def on_tqdm_progress(current_bytes: int, total_bytes: int, desc: str):
            if cancel_check and cancel_check():
                raise InterruptedError("Téléchargement annulé par l'utilisateur.")

            if total_bytes > 0:
                pct = max(2, min(99, int((current_bytes / total_bytes) * 100)))
                # Throttle pour ne pas surcharger l'UI
                if pct != last_logged_pct[0]:
                    last_logged_pct[0] = pct
                    cur_str = format_file_size(current_bytes)
                    tot_str = format_file_size(total_bytes)
                    if pct >= 95:
                        msg = f"📥 Assemblage final du modèle : {cur_str} / {tot_str} ({pct}%) - presque terminé..."
                    else:
                        msg = f"📥 Téléchargement du modèle IA : {cur_str} / {tot_str} ({pct}%)"
                    if progress_callback:
                        progress_callback(pct, msg)

        ModelProgressTqdm.callback = on_tqdm_progress

        try:
            model_path = huggingface_hub.snapshot_download(
                repo_id,
                allow_patterns=allow_patterns,
                tqdm_class=ModelProgressTqdm,
            )
            if progress_callback:
                progress_callback(100, f"✅ Modèle '{model_size_or_id}' téléchargé et prêt en local !")
            return model_path
        finally:
            ModelProgressTqdm.callback = None
