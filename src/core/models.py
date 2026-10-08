"""Modèles de données pour la génération de sous-titres."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AudioMetadata:
    """Métadonnées du fichier audio extrait."""
    path: Path
    duration: float  # en secondes
    channels: int = 1
    sample_rate: int = 16000
    file_size_mb: float = 0.0


@dataclass
class SubtitleSegment:
    """Segment de sous-titre individuel."""
    index: int
    start: float  # secondes
    end: float    # secondes
    text: str

    @property
    def start_str(self) -> str:
        return format_timestamp(self.start)

    @property
    def end_str(self) -> str:
        return format_timestamp(self.end)


def format_timestamp(seconds: float) -> str:
    """Convertit un temps en secondes vers le format SRT HH:MM:SS,mmm."""
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


@dataclass
class GenerationResult:
    """Résultat d'une génération de sous-titres."""
    output_dir: Path
    subtitle_path: Path
    detected_language: str
    audio_path: Path
    status: str = "success"
    task_type: str = "transcribe"  # 'transcribe' ou 'translate'
    duration_seconds: float = 0.0
    segments_count: int = 0
    error_message: str | None = None
