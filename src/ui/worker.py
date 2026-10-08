"""Worker en arrière-plan (QThread) pour exécuter Whisper sans bloquer l'interface."""

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from src.core.models import GenerationResult
from src.services.subtitle_generator import SubtitleGenerator


class SubtitleWorker(QObject):
    """Worker exécutant la génération en tâche de fond pour garder l'UI fluide."""

    # Signaux Qt pour communiquer avec l'interface principale
    progress_updated = Signal(int, str)             # (pourcentage, texte d'état)
    segment_received = Signal(int, float, float, str) # (numéro, début, fin, texte)
    log_logged = Signal(str)                         # (message de log)
    finished = Signal(list)                          # (liste des GenerationResult)
    error_occurred = Signal(str)                     # (message d'erreur)

    def __init__(
        self,
        video_path: Path,
        output_dir: Path,
        languages: list[str],
        source_language: str = "auto",
        model_size: str = "small",
    ) -> None:
        super().__init__()
        self.video_path = video_path
        self.output_dir = output_dir
        self.languages = languages
        self.source_language = source_language
        self.model_size = model_size
        self._is_cancelled = False

    def cancel(self) -> None:
        """Demande l'annulation propre du traitement."""
        self._is_cancelled = True
        self.log_logged.emit("⚠️ Annulation demandée par l'utilisateur...")

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self) -> None:
        """Point d'entrée du thread de travail."""
        try:
            self.log_logged.emit(f"🚀 Initialisation du moteur Whisper (Modèle: {self.model_size})...")
            self.progress_updated.emit(2, "Vérification / Téléchargement du modèle...")

            def on_model_progress(pct: int, msg: str):
                self.progress_updated.emit(pct, msg)
                self.log_logged.emit(msg)

            generator = SubtitleGenerator(
                model_size=self.model_size,
                language=self.languages[0] if self.languages else "auto",
                model_progress_callback=on_model_progress,
                cancel_check=self.is_cancelled,
            )

            if self._is_cancelled:
                self.progress_updated.emit(0, "Annulé")
                self.finished.emit([])
                return

            def on_progress(pct: int, cur: float, tot: float, msg: str):
                self.progress_updated.emit(pct, msg)
                if cur > 0 and tot > 0:
                    self.log_logged.emit(f"[{pct}%] {msg}")

            results = generator.generate_many_languages(
                media_path=self.video_path,
                output_dir=self.output_dir,
                languages=self.languages,
                source_language=self.source_language,
                progress_callback=on_progress,
                cancel_check=self.is_cancelled,
            )

            if self._is_cancelled:
                self.log_logged.emit("🛑 Traitement annulé.")
                self.finished.emit([])
            else:
                self.progress_updated.emit(100, "Terminé avec succès !")
                self.finished.emit(results)

        except Exception as exc:
            self.log_logged.emit(f"❌ Erreur critique : {str(exc)}")
            self.error_occurred.emit(str(exc))
