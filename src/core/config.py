"""Configuration des langues, modèles et paramètres par défaut."""

SUPPORTED_LANGUAGES = {
    "auto": "Détection automatique",
    "fr": "Français",
    "en": "Anglais",
    "ja": "Japonais (Anime / VO)",
    "es": "Espagnol",
    "de": "Allemand",
    "it": "Italien",
    "pt": "Portugais",
    "ko": "Coréen",
    "zh": "Chinois",
    "ru": "Russe",
    "ar": "Arabe",
}

WHISPER_MODELS = {
    "tiny": {
        "name": "Tiny (Très rapide, ~75 Mo)",
        "description": "Ultra léger, vitesse maximale, précision basique.",
        "recommended_for": "Tests rapides ou CPU très modeste",
    },
    "base": {
        "name": "Base (Rapide, ~145 Mo)",
        "description": "Très rapide, bon compromis pour vidéos claires.",
        "recommended_for": "Usage rapide sur CPU",
    },
    "small": {
        "name": "Small (Recommandé CPU, ~480 Mo)",
        "description": "Excellent équilibre vitesse/précision, idéal anime et vidéos FR/EN.",
        "recommended_for": "Parfait pour la plupart des vidéos sur CPU",
    },
    "medium": {
        "name": "Medium (Haute précision, ~1.5 Go)",
        "description": "Très haute précision, idéal voix complexes et musique de fond.",
        "recommended_for": "CPU puissant (8+ cœurs) ou GPU",
    },
    "large-v3": {
        "name": "Large-v3 (Qualité Studio, ~3 Go)",
        "description": "Précision maximale, mais très lourd sur CPU.",
        "recommended_for": "GPU Nvidia recommandé",
    },
}

DEFAULT_MODEL = "tiny"

SUPPORTED_VIDEO_EXTENSIONS = (
    "*.mp4",
    "*.mkv",
    "*.avi",
    "*.mov",
    "*.wmv",
    "*.webm",
    "*.ts",
    "*.flv",
    "*.m4v",
    "*.3gp",
    "*.mp3",
    "*.wav",
    "*.m4a",
    "*.aac",
    "*.flac",
    "*.ogg",
)


def normalize_language(language: str | None) -> str:
    """Normalise le code langue en chaîne standard."""
    if not language:
        return "auto"
    value = language.strip().lower()
    if value in SUPPORTED_LANGUAGES:
        return value
    return "auto"
