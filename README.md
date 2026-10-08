# 🎬 SubtitleStudio AI - Générateur & Traducteur de Sous-Titres Vidéo

Application desktop Python moderne (PySide6 + faster-whisper) conçue pour transcrire et traduire automatiquement des vidéos et fichiers audio (Anime 24 min, films, vidéos YouTube, fichiers de 1 Go+, etc.) en sous-titres `.srt` ou `.vtt`.

---

## 🚀 Fonctionnalités Clés

- **Traitement Asynchrone (Non-Bloquant)** : L'interface ne se fige plus jamais grâce à l'exécution en tâche de fond sur `QThread`. Bouton d'annulation intégré.
- **Support des Fichiers Lourds & Longs (1 Go+, Anime 24 min, etc.)** : Extraction audio en flux via FFmpeg vers WAV 16kHz mono, sans surcharger la mémoire RAM.
- **Tous Formats Multimédia** : `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.ts`, `.flv`, `.m4v`, `.mp3`, `.wav`, etc.
- **Transcription & Traduction Automatique** :
  - **Vidéo en Français -> Sous-titres Français** : Transcription fidèle.
  - **Vidéo en Français/Japonais -> Sous-titres Anglais** : Traduction automatique native avec Whisper.
  - **Détection Automatique** : Détecte la langue parlée et génère les sous-titres correspondants.
- **Optimisation Matérielle Intelligente** :
  - Détection automatique CPU / GPU CUDA.
  - Optimisation CPU `int8` avec allocation de threads optimisée pour une vitesse 4x plus rapide sans freeze.
  - Choix du modèle Whisper (`tiny`, `base`, `small`, `medium`, `large-v3`).
- **Suivi en Direct** : Barre de progression réelle, calcul de la durée restante et prévisualisation du texte en temps réel dans le journal.

---

## 📁 Structure Modulaire du Projet (`src/`)

```text
ProjetConvertirvideoEnsubltilte/
├── app.py                      # Point d'entrée principal
├── requirements.txt            # Dépendances Python
├── README.md                   # Documentation complète
└── src/
    ├── __init__.py             # Exports principaux
    ├── core/                   # Cœur de configuration et modèles
    │   ├── __init__.py
    │   ├── config.py           # Langues, modèles Whisper, extensions supportées
    │   ├── hardware.py         # Détection CPU/CUDA et choix du compute_type optimisé
    │   └── models.py           # Dataclasses (GenerationResult, SubtitleSegment, AudioMetadata)
    ├── services/               # Moteurs de traitement métier
    │   ├── __init__.py
    │   ├── audio_extractor.py  # Extraction audio FFmpeg (16kHz mono) & calcul de durée
    │   ├── srt_formatter.py    # Formattage et écriture des fichiers .srt / .vtt
    │   └── subtitle_generator.py # Moteur de transcription / traduction faster-whisper
    ├── ui/                     # Interface graphique PySide6
    │   ├── __init__.py
    │   ├── main_window.py      # Fenêtre principale avec sélection de langues et boutons rapides
    │   ├── styles.py           # Thème sombre moderne et soigné
    │   └── worker.py           # Worker QThread avec signaux Qt pour un streaming fluide
    └── utils/                  # Utilitaires d'aide
        ├── __init__.py
        └── helpers.py          # Formatage temps, tailles de fichiers et sécurité des chemins
```

---

## 🛠️ Lancer l'Application

```bash
cd "/home/mendrika/Documents/ProjetMendrika/Mon projet/ProjetConvertirvideoEnsubltilte"
source .venv/bin/activate
python app.py
```

---

## 💡 Conseils pour les vidéos de 1 Go et Animes de 24 min

1. **Sur CPU** : Utilisez le modèle **`small`** (recommandé par défaut) ou **`base`** pour une exécution rapide (quelques minutes pour 24 minutes d'anime).
2. **Sur GPU (CUDA)** : Vous pouvez utiliser **`medium`** ou **`large-v3`** pour une précision maximale.
3. Pour traduire un anime japonais ou une vidéo française en anglais, cochez **🇬🇧 Anglais** dans la liste des sous-titres cibles.
# subtitlePython
