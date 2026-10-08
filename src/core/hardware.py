"""Détection du matériel (CPU / GPU CUDA) et configuration optimale."""

import os
import shutil


def is_cuda_available() -> bool:
    """Vérifie si CUDA est disponible pour CTranslate2/faster-whisper."""
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        pass

    # Fallback check
    if shutil.which("nvidia-smi") is not None:
        try:
            import ctranslate2
            return ctranslate2.get_cuda_device_count() > 0
        except Exception:
            return False
    return False


def get_optimal_device_and_compute_type(requested_device: str | None = None) -> tuple[str, str, int]:
    """
    Détermine le device optimal ('cuda' ou 'cpu'), le compute_type ('float16' ou 'int8'),
    et le nombre de threads CPU recommandés pour éviter les blocages.
    """
    cpu_count = os.cpu_count() or 4
    # Laisser 1 ou 2 cœurs libres pour le système et l'UI
    cpu_threads = max(1, min(cpu_count - 1 if cpu_count > 2 else cpu_count, 8))

    if requested_device == "cuda" or (requested_device is None and is_cuda_available()):
        return "cuda", "float16", 1

    # Sur CPU, int8 est 2x à 4x plus rapide et consomme beaucoup moins de RAM
    return "cpu", "int8", cpu_threads


def get_hardware_info() -> dict:
    """Renvoie les informations matérielles sous forme de dictionnaire lisible."""
    cuda = is_cuda_available()
    device, compute_type, threads = get_optimal_device_and_compute_type()
    cpu_count = os.cpu_count() or 4

    return {
        "cuda_available": cuda,
        "device": device,
        "compute_type": compute_type,
        "cpu_threads": threads,
        "total_cpu_cores": cpu_count,
        "summary": (
            f"GPU CUDA (Accélération matérielle)"
            if cuda
            else f"CPU ({cpu_count} cœurs, {threads} threads dédiés, int8 optimisé)"
        ),
    }
