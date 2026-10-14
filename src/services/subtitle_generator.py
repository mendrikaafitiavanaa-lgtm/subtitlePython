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
from src.services.fuzzy_corrector import FuzzyKnowledgeCorrector
from src.services.model_manager import ModelManager
from src.services.srt_formatter import SubtitleFormatter
from src.services.subtitle_postprocess import RawSegment, Word, postprocess_segments
from src.services.translator import SubtitleTranslator
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
        custom_keywords: list[str] | str | None = None,
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
        self.translator = SubtitleTranslator()
        self.corrector = FuzzyKnowledgeCorrector(
            custom_keywords=custom_keywords,
            default_lang=self.language if self.language != "auto" else "en",
        )
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

        # 1. Choix de la piste audio (VO prioritaire sur les fichiers MULTI) + extraction
        norm_target = normalize_language(target_language)
        norm_source = normalize_language(source_language)

        preferred_track_lang = norm_source if norm_source != "auto" else norm_target
        audio_track = self.audio_extractor.pick_audio_track(media_path, preferred_track_lang)

        if progress_callback:
            progress_callback(5, 0.0, 0.0, f"Extraction audio via FFmpeg (piste {audio_track})...")

        audio_meta = self.audio_extractor.extract_audio(
            media_path, base_output_dir, audio_track=audio_track
        )
        duration = audio_meta.duration

        if cancel_check and cancel_check():
            return GenerationResult(
                output_dir=base_output_dir,
                subtitle_path=Path(""),
                detected_language="cancelled",
                audio_path=audio_meta.path,
                status="cancelled",
            )

        # 2. Langue réellement parlée dans l'audio.
        if progress_callback:
            progress_callback(8, 0.0, duration, "Détection de la langue parlée...")
        spoken_lang = self._detect_spoken_language(audio_meta.path, norm_source) or "en"

        # Logique de transcription vs traduction :
        # - Vidéo anglaise + sous-titres demandés en français -> Whisper transcrit en anglais, puis SubtitleTranslator traduit en français
        # - Vidéo française + sous-titres demandés en anglais -> Whisper traduit directement vers l'anglais (task='translate')
        # - Même langue -> transcription directe
        need_translation_to_fr = (norm_target == "fr" and spoken_lang == "en")
        if need_translation_to_fr:
            task = "transcribe"
            whisper_lang = "en"
        elif norm_target == "en" and spoken_lang != "en":
            task = "translate"
            whisper_lang = spoken_lang
        else:
            task = "transcribe"
            whisper_lang = spoken_lang

        prompt_lang = "en" if (whisper_lang == "en" or task == "translate") else "fr"
        initial_prompt = self.corrector.get_initial_prompt(prompt_lang)

        if progress_callback:
            progress_callback(10, 0.0, duration, f"Transcription ({task}, langue audio: {whisper_lang})...")

        # 3. Transcription optimisée pour CPU (beam_size=2, best_of=1, int8) : vitesse x3 et conso minimale
        segments_generator, info = self.model.transcribe(
            str(audio_meta.path),
            task=task,
            language=whisper_lang,
            initial_prompt=initial_prompt,
            beam_size=2,                        # Optimisé : exploration légère, division par 3 de la charge CPU
            best_of=1,
            temperature=0.0,                    # Décodage stable et déterministe
            # --- Anti-boucles & Détection sensible des voix faibles / rapides ---
            condition_on_previous_text=False,   # évite les répétitions en cascade
            compression_ratio_threshold=2.6,
            log_prob_threshold=-1.5,
            no_speech_threshold=0.85,           # ne saute plus les répliques avec musique de fond
            vad_filter=True,
            vad_parameters=dict(
                threshold=0.20,                 # seuil sensible pour capter les voix calmes / bruits forts
                min_speech_duration_ms=100,
                max_speech_duration_s=30,
                min_silence_duration_ms=500,
                speech_pad_ms=400,              # marge de 400ms avant/après pour ne pas couper le début/fin
            ),
            # --- Timestamps précis par mot (sert au découpage propre) ---
            word_timestamps=True,
            hallucination_silence_threshold=2.5,
        )

        detected_lang = info.language or whisper_lang or "en"
        total_duration = duration if duration > 0 else (info.duration or 1.0)

        raw_segments: list[RawSegment] = []

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
            if not clean_text:
                continue

            words = [
                Word(start=float(w.start), end=float(w.end), text=w.word)
                for w in (seg.words or [])
            ]
            raw_segments.append(
                RawSegment(
                    start=float(seg.start),
                    end=float(seg.end),
                    text=clean_text,
                    words=words or None,
                    avg_logprob=getattr(seg, "avg_logprob", None),
                    no_speech_prob=getattr(seg, "no_speech_prob", None),
                    compression_ratio=getattr(seg, "compression_ratio", None),
                )
            )

            current_end = float(seg.end)
            pct = min(93, max(10, int((current_end / total_duration) * 83) + 10))
            if progress_callback:
                progress_callback(pct, current_end, total_duration, clean_text)

        # Nettoyage et correction intelligente (Logique floue, phonétique, dictionnaire d'entités)
        post_lang = "en" if (need_translation_to_fr or task == "translate" or whisper_lang == "en") else "fr"
        collected_segments = postprocess_segments(
            raw_segments,
            corrector=self.corrector,
            lang=post_lang,
        )

        # Si l'utilisateur a demandé des sous-titres en français pour une vidéo en anglais
        if need_translation_to_fr:
            if progress_callback:
                progress_callback(94, total_duration, total_duration, "Traduction des sous-titres en Français...")
            def on_trans_prog(pct: int, msg: str):
                if progress_callback:
                    overall = 94 + int(pct * 0.05)
                    progress_callback(overall, total_duration, total_duration, msg)

            collected_segments = self.translator.translate_segments(
                collected_segments,
                source_lang="en",
                target_lang="fr",
                progress_callback=on_trans_prog,
            )

            # Re-passer la correction de connaissances en français (Omnitrix, Ben, Gwen, etc.)
            for seg in collected_segments:
                seg.text = self.corrector.correct_text(seg.text, lang="fr")

        # 4. Sauvegarde du fichier SRT
        lang_folder_name = norm_target if norm_target != "auto" else detected_lang
        lang_dir = base_output_dir / lang_folder_name
        ensure_dir(lang_dir)

        # Suffixe pour le nom de fichier (ex: film.fr.srt ou film.en.srt)
        suffix = f".{lang_folder_name}"
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
            note=note,
        )

    def _detect_spoken_language(self, audio_path: Path, source_language: str) -> str | None:
        """Retourne la langue parlée : celle choisie par l'utilisateur, sinon détectée sur l'audio."""
        if source_language != "auto":
            return source_language
        try:
            from faster_whisper.audio import decode_audio

            audio = decode_audio(str(audio_path), sampling_rate=16000)
            lang, prob, _ = self.model.detect_language(
                audio,
                vad_filter=True,
                language_detection_segments=4,
            )
            logger.info(f"Langue détectée : {lang} (confiance {prob:.2f})")
            return lang
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Détection de langue impossible ({exc}), détection automatique Whisper.")
            return None

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