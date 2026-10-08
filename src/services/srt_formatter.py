"""Formatteur et exportateur de sous-titres (SRT, VTT)."""

from pathlib import Path
from src.core.models import SubtitleSegment, format_timestamp
from src.utils.helpers import ensure_dir


class SubtitleFormatter:
    """Formatage et écriture de fichiers de sous-titres standard."""

    @staticmethod
    def format_srt_content(segments: list[SubtitleSegment]) -> str:
        """Génère le texte standardisé au format SRT."""
        blocks: list[str] = []
        for index, seg in enumerate(segments, start=1):
            text = (seg.text or "").strip().replace("\r\n", "\n").replace("\r", "\n")
            if not text:
                continue

            start_ts = format_timestamp(seg.start)
            end_ts = format_timestamp(seg.end)

            blocks.append(f"{index}\n{start_ts} --> {end_ts}\n{text}\n")

        return "\n".join(blocks).strip() + "\n" if blocks else ""

    @staticmethod
    def format_vtt_content(segments: list[SubtitleSegment]) -> str:
        """Génère le texte standardisé au format WebVTT."""
        blocks: list[str] = ["WEBVTT\n"]
        for index, seg in enumerate(segments, start=1):
            text = (seg.text or "").strip().replace("\r\n", "\n").replace("\r", "\n")
            if not text:
                continue

            start_ts = format_timestamp(seg.start).replace(",", ".")
            end_ts = format_timestamp(seg.end).replace(",", ".")

            blocks.append(f"{index}\n{start_ts} --> {end_ts}\n{text}\n")

        return "\n".join(blocks).strip() + "\n"

    def write_srt(self, segments: list[SubtitleSegment], output_path: Path) -> Path:
        """Écrit les segments dans un fichier .srt."""
        ensure_dir(output_path.parent)
        content = self.format_srt_content(segments)
        output_path.write_text(content, encoding="utf-8")
        return output_path

    def write_vtt(self, segments: list[SubtitleSegment], output_path: Path) -> Path:
        """Écrit les segments dans un fichier .vtt."""
        ensure_dir(output_path.parent)
        content = self.format_vtt_content(segments)
        output_path.write_text(content, encoding="utf-8")
        return output_path
