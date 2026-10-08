"""Package principal de l'application de génération de sous-titres."""

from src.core.config import SUPPORTED_LANGUAGES, normalize_language
from src.core.models import GenerationResult, SubtitleSegment
from src.services.audio_extractor import AudioExtractor
from src.services.srt_formatter import SubtitleFormatter
from src.services.subtitle_generator import SubtitleGenerator
from src.ui.main_window import MainWindow, SubtitleWindow, main

__all__ = [
    "SUPPORTED_LANGUAGES",
    "normalize_language",
    "GenerationResult",
    "SubtitleSegment",
    "AudioExtractor",
    "SubtitleFormatter",
    "SubtitleGenerator",
    "MainWindow",
    "SubtitleWindow",
    "main",
]
