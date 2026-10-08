"""Moteur de génération et transcription de sous-titres via faster-whisper."""

from collections.abc import Callable
import functools
import logging
from pathlib import Path
from typing import Any

# Correctif de compatibilité PyAV >= 14.0 pour faster-whisper
try:
    import av
    orig_av_open = av.open

    @functools.wraps(orig_av_open)
    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return orig_av_open(*args, **kwargs)

    av.open = _safe_av_open
except Exception:
    pass

from faster_whisper import WhisperModel

from src.core.config import DEFAULT_MODEL, normalize_language
from src.core.hardware import get_optimal_device_and_compute_type
from src.core.models import AudioMetadata, GenerationResult, SubtitleSegment
from src.services.audio_extractor import AudioExtractor
from src.services.model_manager import ModelManager
from src.services.srt_formatter import SubtitleFormatter
from src.utils.helpers import ensure_dir

logger = logging.getLogger(__name__)


class SubtitleGenerator:
    """Service de transcription audio vers sous-titres avec gestion du streaming."""

    _cached_model: WhisperModel | None = None
    _cached_model_key: tuple | None = None

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL,
        device: str | None = None,
        compute_type: str | None = None,
        language: str = "auto",
        cpu_threads: int | None = None,
        model_progress_callback: Callable[[int, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        self.model_size = model_size
        optimal_device, optimal_compute, optimal_threads = get_optimal_device_and_compute_type(device)
        self.device = device or optimal_device
        self.compute_type = compute_type or optimal_compute
        self.cpu_threads = cpu_threads or optimal_threads
        self.language = normalize_language(language)

        self.audio_extractor = AudioExtractor()
        self.formatter = SubtitleFormatter()
        self.model = self._get_or_load_model(model_progress_callback, cancel_check)

    def _get_or_load_model(
        self,
        model_progress_callback: Callable[[int, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> WhisperModel:
        """Charge ou réutilise le modèle Whisper en cache pour éviter les rechargements lents."""
        key = (self.model_size, self.device, self.compute_type, self.cpu_threads)
        if SubtitleGenerator._cached_model is not None and SubtitleGenerator._cached_model_key == key:
            return SubtitleGenerator._cached_model

        # Télécharger / vérifier la présence locale du modèle avec progression
        model_path_or_size = ModelManager.ensure_model_available(
            self.model_size,
            progress_callback=model_progress_callback,
            cancel_check=cancel_check,
        )

        if model_progress_callback:
            model_progress_callback(99, f"Initialisation en mémoire du modèle '{self.model_size}'...")

        logger.info(
            f"Chargement du modèle Whisper '{self.model_size}' sur {self.device} (compute_type={self.compute_type}, threads={self.cpu_threads})..."
        )
        model = WhisperModel(
            model_path_or_size,
            device=self.device,
            compute_type=self.compute_type,
            cpu_threads=self.cpu_threads,
        )
        SubtitleGenerator._cached_model = model
        SubtitleGenerator._cached_model_key = key
        return model

    def generate_for_language(
        self,
        media_path: str | Path,
        output_dir: str | Path,
        target_language: str = "auto",
        source_language: str = "auto",
        progress_callback: Callable[[int, float, float, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> GenerationResult:
        """
        Génère un sous-titre .srt pour une langue cible donnée.
        
        Logique de traduction / transcription :
        - Si target_language == 'en' et la langue source n'est pas l'anglais -> task='translate' (traduction directe en anglais)
        - Sinon -> task='transcribe' (transcription dans la langue source / cible demandée)
        """
        media_path = Path(media_path)
        if not media_path.exists():
            raise FileNotFoundError(f"Fichier multimédia introuvable : {media_path}")

        base_output_dir = Path(output_dir)
        ensure_dir(base_output_dir)

        # 1. Extraction Audio optimisée (16kHz mono WAV)
        if progress_callback:
            progress_callback(5, 0.0, 0.0, "Extraction audio via FFmpeg...")

        audio_meta = self.audio_extractor.extract_audio(media_path, base_output_dir)
        duration = audio_meta.duration

        if cancel_check and cancel_check():
            return GenerationResult(
                output_dir=base_output_dir,
                subtitle_path=Path(""),
                detected_language="cancelled",
                audio_path=audio_meta.path,
                status="cancelled",
            )

        # 2. Détermination de la tâche (transcribe vs translate) et de la langue
        norm_target = normalize_language(target_language)
        norm_source = normalize_language(source_language)

        # Déterminer si on utilise task="translate" (Whisper traduit nativement n'importe quelle langue vers l'anglais)
        if norm_target == "en" and norm_source not in ("en", "auto"):
            task = "translate"
            whisper_lang = norm_source
        elif norm_target == "en" and norm_source == "auto":
            # Si l'utilisateur veut spécifiquement de l'anglais à partir d'une vidéo inconnue
            task = "translate"
            whisper_lang = None
        else:
            task = "transcribe"
            if norm_target != "auto":
                whisper_lang = norm_target
            elif norm_source != "auto":
                whisper_lang = norm_source
            else:
                whisper_lang = None

        if progress_callback:
            progress_callback(10, 0.0, duration, f"Initialisation transcription ({task} / {norm_target})...")

        # 3. Transcription par streaming de segments avec faster-whisper
        segments_generator, info = self.model.transcribe(
            str(audio_meta.path),
            task=task,
            language=whisper_lang,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            word_timestamps=False,
        )

        detected_lang = info.language or (norm_target if norm_target != "auto" else "fr")
        total_duration = duration if duration > 0 else (info.duration or 1.0)

        collected_segments: list[SubtitleSegment] = []

        for seg in segments_generator:
            if cancel_check and cancel_check():
                return GenerationResult(
                    output_dir=base_output_dir,
                    subtitle_path=Path(""),
                    detected_language=detected_lang,
                    audio_path=audio_meta.path,
                    status="cancelled",
                )

            clean_text = (seg.text or "").strip()
            if clean_text:
                segment_obj = SubtitleSegment(
                    index=len(collected_segments) + 1,
                    start=float(seg.start),
                    end=float(seg.end),
                    text=clean_text,
                )
                collected_segments.append(segment_obj)

                # Calcul du pourcentage d'avancement
                current_end = float(seg.end)
                pct = min(95, max(10, int((current_end / total_duration) * 85) + 10))

                if progress_callback:
                    progress_callback(pct, current_end, total_duration, clean_text)

        # 4. Sauvegarde du fichier SRT
        lang_folder_name = norm_target if norm_target != "auto" else detected_lang
        lang_dir = base_output_dir / lang_folder_name
        ensure_dir(lang_dir)

        # Suffixe pour le nom de fichier (ex: film.fr.srt ou film.en.srt)
        suffix = f".{lang_folder_name}" if lang_folder_name != "auto" else ""
        srt_path = lang_dir / f"{media_path.stem}{suffix}.srt"

        self.formatter.write_srt(collected_segments, srt_path)

        if progress_callback:
            progress_callback(100, total_duration, total_duration, f"Fichier généré : {srt_path.name}")

        return GenerationResult(
            output_dir=lang_dir,
            subtitle_path=srt_path,
            detected_language=detected_lang,
            audio_path=audio_meta.path,
            status="success",
            task_type=task,
            duration_seconds=total_duration,
            segments_count=len(collected_segments),
        )

    def generate_many_languages(
        self,
        media_path: str | Path,
        output_dir: str | Path | None = None,
        languages: list[str] | None = None,
        source_language: str = "auto",
        progress_callback: Callable[[int, float, float, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[GenerationResult]:
        """Génère les sous-titres pour plusieurs langues sélectionnées."""
        media_path = Path(media_path)
        base_dir = Path(output_dir) if output_dir else media_path.parent
        project_dir = base_dir / media_path.stem
        ensure_dir(project_dir)

        selected = languages or [self.language]
        unique_languages: list[str] = []
        for lang in selected:
            norm = normalize_language(lang)
            if norm not in unique_languages:
                unique_languages.append(norm)

        if not unique_languages:
            unique_languages = ["auto"]

        results: list[GenerationResult] = []
        total_langs = len(unique_languages)

        for idx, lang in enumerate(unique_languages):
            if cancel_check and cancel_check():
                break

            def lang_progress(pct: int, cur: float, tot: float, msg: str):
                if progress_callback:
                    # Diviser la progression globale entre les langues
                    overall_pct = int((idx / total_langs) * 100 + (pct / total_langs))
                    progress_callback(overall_pct, cur, tot, f"[{idx+1}/{total_langs} - {lang.upper()}] {msg}")

            res = self.generate_for_language(
                media_path=media_path,
                output_dir=project_dir,
                target_language=lang,
                source_language=source_language,
                progress_callback=lang_progress,
                cancel_check=cancel_check,
            )
            results.append(res)

        return results

    # Méthodes de compatibilité descendante
    def generate_single_language(
        self,
        video_path: str | Path,
        output_dir: str | Path | None = None,
        language: str | None = None,
    ) -> GenerationResult:
        base_dir = Path(output_dir) if output_dir else Path(video_path).parent
        return self.generate_for_language(
            media_path=video_path,
            output_dir=base_dir,
            target_language=language or self.language,
        )

    def generate(self, video_path: str | Path, output_dir: str | Path | None = None) -> tuple[str, str]:
        result = self.generate_single_language(video_path, output_dir, self.language)
        return str(result.subtitle_path), result.detected_language
