"""Service d'extraction et d'analyse audio via FFmpeg."""

import json
import os
from pathlib import Path
import shutil
import subprocess

from src.core.models import AudioMetadata
from src.utils.helpers import ensure_dir


class AudioExtractor:
    """Extrait et analyse l'audio des fichiers vidéo/audio pour Whisper."""

    @staticmethod
    def get_ffmpeg_path() -> str:
        """Trouve le binaire FFmpeg."""
        path = shutil.which("ffmpeg")
        if not path:
            raise RuntimeError(
                "FFmpeg n'est pas installé ou introuvable dans le PATH système. "
                "Sous Linux: sudo apt install ffmpeg"
            )
        return path

    @staticmethod
    def get_ffprobe_path() -> str | None:
        """Trouve le binaire FFprobe s'il est disponible."""
        return shutil.which("ffprobe")

    def get_media_duration(self, media_path: Path) -> float:
        """
        Détermine la durée exacte du fichier multimédia en secondes.
        Utilise ffprobe si disponible, sinon ffmpeg.
        """
        ffprobe = self.get_ffprobe_path()
        if ffprobe:
            cmd = [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(media_path),
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                val = float(res.stdout.strip())
                if val > 0:
                    return val
            except Exception:
                pass

        # Fallback via ffmpeg
        ffmpeg = self.get_ffmpeg_path()
        cmd = [ffmpeg, "-i", str(media_path)]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            output = res.stderr
            for line in output.splitlines():
                if "Duration:" in line:
                    # Duration: 00:24:15.32, start: ...
                    time_part = line.split("Duration:")[1].split(",")[0].strip()
                    parts = time_part.split(":")
                    if len(parts) == 3:
                        h = float(parts[0])
                        m = float(parts[1])
                        s = float(parts[2])
                        return h * 3600 + m * 60 + s
        except Exception:
            pass

        return 0.0

    def extract_audio(
        self,
        media_path: Path,
        output_dir: Path,
        sample_rate: int = 16000,
    ) -> AudioMetadata:
        """
        Extrait l'audio sous forme de WAV 16kHz mono optimal pour Whisper.
        Gère les fichiers de toute taille (1 Go+, longs animes de 24 min, etc.)
        """
        if not media_path.exists():
            raise FileNotFoundError(f"Le fichier vidéo est introuvable : {media_path}")

        ffmpeg_path = self.get_ffmpeg_path()
        ensure_dir(output_dir)

        audio_output_path = output_dir / f"{media_path.stem}_audio.wav"

        # Si l'audio a déjà été extrait pour ce fichier et existe avec une taille valide
        duration = self.get_media_duration(media_path)

        cmd = [
            ffmpeg_path,
            "-y",               # Écraser sans demander
            "-i", str(media_path),
            "-vn",              # Pas de vidéo
            "-acodec", "pcm_s16le", # PCM 16-bit
            "-ar", str(sample_rate), # 16000 Hz
            "-ac", "1",         # Mono
            str(audio_output_path),
        ]

        # Exécuter l'extraction sans charger en RAM
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if process.returncode != 0:
            raise RuntimeError(
                f"Erreur lors de l'extraction audio avec FFmpeg :\n{process.stderr[:500]}"
            )

        file_size_mb = audio_output_path.stat().st_size / (1024 * 1024)

        if duration == 0.0:
            # Essayer de mesurer la durée sur le wav généré
            duration = self.get_media_duration(audio_output_path)

        return AudioMetadata(
            path=audio_output_path,
            duration=duration,
            channels=1,
            sample_rate=sample_rate,
            file_size_mb=file_size_mb,
        )
