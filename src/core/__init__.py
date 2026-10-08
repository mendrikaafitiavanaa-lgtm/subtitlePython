"""Core package containing configuration, models, hardware detection, and PyAV compatibility."""

import functools

# Correctif de compatibilité pour PyAV >= 14.0 avec faster-whisper
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

from src.core.config import (
    DEFAULT_MODEL,
    SUPPORTED_LANGUAGES,
    SUPPORTED_VIDEO_EXTENSIONS,
    WHISPER_MODELS,
    normalize_language,
)
from src.core.hardware import (
    get_hardware_info,
    get_optimal_device_and_compute_type,
    is_cuda_available,
)
from src.core.models import (
    AudioMetadata,
    GenerationResult,
    SubtitleSegment,
    format_timestamp,
)

__all__ = [
    "DEFAULT_MODEL",
    "SUPPORTED_LANGUAGES",
    "SUPPORTED_VIDEO_EXTENSIONS",
    "WHISPER_MODELS",
    "normalize_language",
    "get_hardware_info",
    "get_optimal_device_and_compute_type",
    "is_cuda_available",
    "AudioMetadata",
    "GenerationResult",
    "SubtitleSegment",
    "format_timestamp",
]
