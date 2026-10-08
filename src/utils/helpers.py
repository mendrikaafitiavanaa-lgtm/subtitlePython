"""Fonctions utilitaires générales (fichiers, formatage, validation)."""

import os
from pathlib import Path
import re


def sanitize_filename(name: str) -> str:
    """Nettoie une chaîne pour en faire un nom de fichier/dossier valide."""
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def format_duration(seconds: float) -> str:
    """Formate une durée en chaîne lisible (ex: 24m 15s ou 1h 05m 30s)."""
    total_sec = int(round(seconds))
    hours, remainder = divmod(total_sec, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    return f"{minutes}m {secs:02d}s"


def format_file_size(size_bytes: int | float) -> str:
    """Formate une taille en octets en Mo ou Go lisibles."""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 ** 3):.2f} Go"
    return f"{size_bytes / (1024 ** 2):.1f} Mo"


def ensure_dir(path: Path) -> Path:
    """Crée un dossier s'il n'existe pas et renvoie le chemin."""
    path.mkdir(parents=True, exist_ok=True)
    return path
