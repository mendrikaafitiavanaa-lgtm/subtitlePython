"""Fenêtre principale PySide6 moderne, asynchrone et réactive."""

import os
from pathlib import Path
import subprocess
import sys

# Désactiver les avertissements verbeux de HuggingFace
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.config import (
    DEFAULT_MODEL,
    SPOKEN_LANGUAGES,
    SUPPORTED_LANGUAGES,
    SUPPORTED_VIDEO_EXTENSIONS,
    WHISPER_MODELS,
    normalize_language,
)
from src.core.hardware import get_hardware_info
from src.core.models import GenerationResult
from src.services.audio_extractor import AudioExtractor
from src.services.model_manager import MODEL_SIZES, ModelManager
from src.ui.styles import APP_STYLESHEET
from src.ui.worker import SubtitleWorker
from src.utils.helpers import format_duration, format_file_size


class MainWindow(QMainWindow):
    """Interface utilisateur principale pour la génération de sous-titres."""

    def __init__(self) -> None:
        super().__init__()
        self.video_path: Path | None = None
        self.output_dir: Path = Path.home() / "Videos"
        self.generated_files: list[Path] = []
        self.hardware_info = get_hardware_info()
        self.audio_extractor = AudioExtractor()

        self.thread: QThread | None = None
        self.worker: SubtitleWorker | None = None

        self.setWindowTitle("SubtitleStudio AI - Générateur & Traducteur de Sous-Titres")
        self.resize(950, 720)
        self.setMinimumSize(800, 600)
        self.setStyleSheet(APP_STYLESHEET)

        self._build_ui()

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. En-tête avec Statut Matériel
        header_layout = QHBoxLayout()
        title_label = QLabel("🎬 SubtitleStudio AI")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.badge_hardware = QLabel(f"⚙️ {self.hardware_info['summary']}")
        self.badge_hardware.setObjectName("badge-hardware")
        header_layout.addWidget(self.badge_hardware)
        main_layout.addLayout(header_layout)

        # Séparateur Horizontal supérieur / inférieur
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Panneau supérieur : Configuration
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        # Groupe 1 : Fichier Source (Vidéo / Audio)
        video_group = QGroupBox("1. Sélection de la vidéo / audio")
        video_layout = QVBoxLayout(video_group)

        file_row = QHBoxLayout()
        self.video_path_label = QLabel("Aucun fichier sélectionné (Glissez ou cliquez sur Choisir)")
        self.video_path_label.setStyleSheet("color: #e2e8f0; font-weight: 500;")
        self.video_path_label.setWordWrap(True)

        btn_select_video = QPushButton("📁 Choisir un fichier")
        btn_select_video.clicked.connect(self._select_video)

        file_row.addWidget(self.video_path_label, 1)
        file_row.addWidget(btn_select_video)
        video_layout.addLayout(file_row)

        self.video_info_label = QLabel("Formats pris en charge : MP4, MKV, AVI, MOV, WEBM, TS, MP3, WAV, etc.")
        self.video_info_label.setObjectName("video-info")
        video_layout.addWidget(self.video_info_label)

        top_layout.addWidget(video_group)

        # Groupe 2 : Options de transcription & Langues
        options_group = QGroupBox("2. Langues & Paramètres")
        options_layout = QHBoxLayout()

        # Colonne Langue source & Modèle
        left_col = QVBoxLayout()
        
        lbl_source = QLabel("🗣️ Langue parlée dans la vidéo :")
        lbl_source.setStyleSheet("font-weight: bold;")
        self.combo_source_lang = QComboBox()
        for code, name in SPOKEN_LANGUAGES.items():
            self.combo_source_lang.addItem(f"{name} ({code})", code)
        left_col.addWidget(lbl_source)
        left_col.addWidget(self.combo_source_lang)

        lbl_model = QLabel("🧠 Modèle d'IA (Whisper) :")
        lbl_model.setStyleSheet("font-weight: bold; margin-top: 8px;")
        self.combo_model = QComboBox()
        for m_id, m_data in WHISPER_MODELS.items():
            self.combo_model.addItem(m_data["name"], m_id)
        # Sélectionner DEFAULT_MODEL
        idx = list(WHISPER_MODELS.keys()).index(DEFAULT_MODEL)
        self.combo_model.setCurrentIndex(idx)
        self.combo_model.currentIndexChanged.connect(self._on_model_changed)

        self.model_status_label = QLabel()
        self.model_status_label.setStyleSheet("font-size: 11px; margin-top: 2px;")
        self._update_model_status_label()

        left_col.addWidget(lbl_model)
        left_col.addWidget(self.combo_model)
        left_col.addWidget(self.model_status_label)

        # Dossier de sortie
        lbl_output = QLabel("📂 Dossier d'exportation :")
        lbl_output.setStyleSheet("font-weight: bold; margin-top: 8px;")
        output_row = QHBoxLayout()
        self.output_dir_label = QLabel(str(self.output_dir))
        self.output_dir_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        btn_output_dir = QPushButton("Parcourir")
        btn_output_dir.setObjectName("btn-secondary")
        btn_output_dir.clicked.connect(self._select_output_dir)
        output_row.addWidget(self.output_dir_label, 1)
        output_row.addWidget(btn_output_dir)
        left_col.addWidget(lbl_output)
        left_col.addLayout(output_row)

        options_layout.addLayout(left_col, 1)

        # Colonne Sous-titres cibles à générer
        right_col = QVBoxLayout()
        lbl_target = QLabel("📝 Sous-titres à générer :")
        lbl_target.setStyleSheet("font-weight: bold;")
        right_col.addWidget(lbl_target)

        self.language_list = QListWidget()
        for code, label in SUPPORTED_LANGUAGES.items():
            item = QListWidgetItem(f"{label} ({code})")
            item.setData(Qt.ItemDataRole.UserRole, code)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            # Par défaut, cocher le Français
            item.setCheckState(Qt.CheckState.Checked if code == "fr" else Qt.CheckState.Unchecked)
            self.language_list.addItem(item)

        right_col.addWidget(self.language_list)

        # Raccourcis rapides
        quick_btns_layout = QHBoxLayout()
        btn_quick_fr = QPushButton("🇫🇷 Français")
        btn_quick_fr.setObjectName("btn-secondary")
        btn_quick_fr.clicked.connect(lambda: self._set_quick_lang("fr"))

        btn_quick_en = QPushButton("🇬🇧 Anglais")
        btn_quick_en.setObjectName("btn-secondary")
        btn_quick_en.clicked.connect(lambda: self._set_quick_lang("en"))

        quick_btns_layout.addWidget(btn_quick_fr)
        quick_btns_layout.addWidget(btn_quick_en)
        right_col.addLayout(quick_btns_layout)

        options_layout.addLayout(right_col, 1)

        # Ligne Mots-clés / Vocabulaire d'entités & Contexte IA
        keywords_row = QVBoxLayout()
        lbl_kw = QLabel("💡 Mots-clés & Noms de personnages / Contexte (Logique floue & Prompt IA) :")
        lbl_kw.setStyleSheet("font-weight: bold; margin-top: 6px;")
        
        kw_input_layout = QHBoxLayout()
        self.input_keywords = QLineEdit()
        self.input_keywords.setPlaceholderText("Ex: Ben Tennyson, Gwen, Grandpa Max, Omnitrix, Vilgax, Heatblast, Sauvage, Incassable...")
        self.input_keywords.setText("Ben Tennyson, Gwen, Grandpa Max, Omnitrix, Vilgax, Heatblast, Wildmutt, Diamondhead, XLR8, Four Arms, Ripjaws, Stinkfly, Upgrade, Ghostfreak")
        self.input_keywords.setStyleSheet("padding: 6px; font-size: 12px;")

        btn_kw_ben10 = QPushButton("👽 Ben 10")
        btn_kw_ben10.setObjectName("btn-secondary")
        btn_kw_ben10.clicked.connect(lambda: self.input_keywords.setText(
            "Ben Tennyson, Gwen, Grandpa Max, Omnitrix, Vilgax, Heatblast, Wildmutt, Diamondhead, XLR8, Four Arms, Ripjaws, Stinkfly, Upgrade, Ghostfreak"
        ))

        btn_kw_clear = QPushButton("🧹 Effacer")
        btn_kw_clear.setObjectName("btn-secondary")
        btn_kw_clear.clicked.connect(lambda: self.input_keywords.clear())

        kw_input_layout.addWidget(self.input_keywords, 1)
        kw_input_layout.addWidget(btn_kw_ben10)
        kw_input_layout.addWidget(btn_kw_clear)

        keywords_row.addWidget(lbl_kw)
        keywords_row.addLayout(kw_input_layout)

        # Ajouter au conteneur du groupe 2
        options_container_layout = QVBoxLayout()
        options_container_layout.addLayout(options_layout)
        options_container_layout.addLayout(keywords_row)
        options_group.setLayout(options_container_layout)

        top_layout.addWidget(options_group)

        # Boutons d'Action Principaux
        action_layout = QHBoxLayout()
        self.btn_generate = QPushButton("▶️ Générer les sous-titres")
        self.btn_generate.setStyleSheet("background-color: #059669; font-size: 14px; padding: 10px 20px;")
        self.btn_generate.clicked.connect(self._start_generation)

        self.btn_cancel = QPushButton("⏹️ Annuler")
        self.btn_cancel.setObjectName("btn-cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_generation)

        self.btn_open_file = QPushButton("📄 Ouvrir le fichier généré")
        self.btn_open_file.setObjectName("btn-secondary")
        self.btn_open_file.setEnabled(False)
        self.btn_open_file.clicked.connect(self._open_last_generated_file)

        self.btn_open_folder = QPushButton("📂 Ouvrir le dossier")
        self.btn_open_folder.setObjectName("btn-secondary")
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self._open_output_folder)

        action_layout.addWidget(self.btn_generate, 2)
        action_layout.addWidget(self.btn_cancel, 1)
        action_layout.addWidget(self.btn_open_file, 1)
        action_layout.addWidget(self.btn_open_folder, 1)
        top_layout.addLayout(action_layout)

        # Barre de Progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        top_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Prêt - Choisissez une vidéo pour commencer.")
        self.status_label.setStyleSheet("color: #38bdf8; font-weight: bold;")
        top_layout.addWidget(self.status_label)

        splitter.addWidget(top_container)

        # Panneau inférieur : Logs & Prévisualisation en direct
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 4, 0, 0)

        log_header = QHBoxLayout()
        log_title = QLabel("📟 Journal d'exécution & Transcription en temps réel :")
        log_title.setStyleSheet("font-weight: bold; color: #94a3b8;")
        log_header.addWidget(log_title)
        log_header.addStretch()

        btn_clear_log = QPushButton("Effacer le journal")
        btn_clear_log.setObjectName("btn-secondary")
        btn_clear_log.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        btn_clear_log.clicked.connect(self._clear_logs)
        log_header.addWidget(btn_clear_log)
        bottom_layout.addLayout(log_header)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.append("Bienvenue dans SubtitleStudio AI.\nSélectionnez une vidéo pour générer vos sous-titres .srt.")
        bottom_layout.addWidget(self.log_console)

        splitter.addWidget(bottom_container)
        main_layout.addWidget(splitter)

    def _on_model_changed(self) -> None:
        self._update_model_status_label()

    def _update_model_status_label(self) -> None:
        model_id = self.combo_model.currentData()
        if not model_id:
            return
        is_cached = ModelManager.is_model_cached(model_id)
        if is_cached:
            self.model_status_label.setText("✅ Modèle disponible localement (Prêt immédiatement)")
            self.model_status_label.setStyleSheet("font-size: 11px; color: #4ade80;")
        else:
            size_bytes = MODEL_SIZES.get(model_id, 400 * 1024 * 1024)
            size_str = format_file_size(size_bytes)
            self.model_status_label.setText(f"⏳ Modèle non téléchargé (~{size_str} requis au 1er lancement)")
            self.model_status_label.setStyleSheet("font-size: 11px; color: #facc15;")

    def _set_quick_lang(self, target_code: str) -> None:
        """Coche uniquement la langue demandée pour un flux rapide."""
        for index in range(self.language_list.count()):
            item = self.language_list.item(index)
            code = str(item.data(Qt.ItemDataRole.UserRole))
            if code == target_code:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)

    def _select_video(self) -> None:
        extensions_filter = "Fichiers Multimédia (" + " ".join(SUPPORTED_VIDEO_EXTENSIONS) + ")"
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une vidéo ou un fichier audio",
            str(Path.home()),
            f"{extensions_filter};;Tous les fichiers (*.*)",
        )
        if not file_name:
            return

        self.video_path = Path(file_name)
        file_size = format_file_size(self.video_path.stat().st_size)
        duration_sec = self.audio_extractor.get_media_duration(self.video_path)
        duration_str = format_duration(duration_sec) if duration_sec > 0 else "Durée calculée à l'extraction"

        self.video_path_label.setText(str(self.video_path))
        self.video_info_label.setText(f"📄 Taille : {file_size} | ⏱️ Durée : {duration_str}")
        self.log_console.append(f"\n📂 Fichier sélectionné : {self.video_path.name} ({file_size}, {duration_str})")
        self.status_label.setText("Fichier chargé. Cliquez sur 'Générer les sous-titres' pour démarrer.")

    def _select_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de sortie",
            str(self.output_dir),
        )
        if not directory:
            return
        self.output_dir = Path(directory)
        self.output_dir_label.setText(str(self.output_dir))
        self.log_console.append(f"📁 Dossier de sortie mis à jour : {self.output_dir}")

    def _get_selected_languages(self) -> list[str]:
        selected: list[str] = []
        for index in range(self.language_list.count()):
            item = self.language_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(str(item.data(Qt.ItemDataRole.UserRole)))
        if not selected:
            selected = ["fr"]
        return [normalize_language(c) for c in selected]

    def _clear_logs(self) -> None:
        self.log_console.clear()

    def _start_generation(self) -> None:
        if not self.video_path or not self.video_path.exists():
            QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner un fichier vidéo valide.")
            return

        languages = self._get_selected_languages()
        source_lang = self.combo_source_lang.currentData()
        model_size = self.combo_model.currentData()

        # Réinitialisation de l'interface
        self.generated_files = []
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_generate.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_open_file.setEnabled(False)
        self.btn_open_folder.setEnabled(False)

        self.status_label.setText("Démarrage du traitement en arrière-plan...")
        self.log_console.append(f"\n▶️ Lancement de la génération pour : {self.video_path.name}")
        self.log_console.append(f"   • Modèle : {model_size}")
        self.log_console.append(f"   • Langue source : {source_lang}")
        self.log_console.append(f"   • Langues cibles : {', '.join(languages)}")

        # Création et démarrage du Worker asynchrone sur QThread (Zero blocage UI)
        custom_kw = self.input_keywords.text().strip()
        if custom_kw:
            self.log_console.append(f"   • Mots-clés / Contexte : {custom_kw}")

        self.thread = QThread()
        self.worker = SubtitleWorker(
            video_path=self.video_path,
            output_dir=self.output_dir,
            languages=languages,
            source_language=source_lang,
            model_size=model_size,
            custom_keywords=custom_kw,
        )
        self.worker.moveToThread(self.thread)

        # Connexion des signaux Qt
        self.thread.started.connect(self.worker.run)
        self.worker.progress_updated.connect(self._on_worker_progress)
        self.worker.log_logged.connect(self._on_worker_log)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error_occurred.connect(self._on_worker_error)

        # Nettoyage à la fin
        self.worker.finished.connect(self.thread.quit)
        self.worker.error_occurred.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def _on_worker_progress(self, percentage: int, message: str) -> None:
        self.progress_bar.setValue(percentage)
        self.status_label.setText(message)

    def _on_worker_log(self, text: str) -> None:
        self.log_console.append(text)
        # Défilement automatique vers le bas
        sb = self.log_console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_worker_finished(self, results: list[GenerationResult]) -> None:
        self.btn_generate.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self._update_model_status_label()

        if not results:
            self.status_label.setText("Traitement interrompu ou aucun fichier généré.")
            return

        self.generated_files = [r.subtitle_path for r in results if r.status == "success" and r.subtitle_path.exists()]
        
        if self.generated_files:
            self.btn_open_file.setEnabled(True)
            self.btn_open_folder.setEnabled(True)
            self.status_label.setText("✅ Génération terminée avec succès !")
            self.log_console.append(f"\n🎉 Succès : {len(self.generated_files)} fichier(s) de sous-titres créés.")
            for f in self.generated_files:
                self.log_console.append(f"   ✓ {f}")

            QMessageBox.information(
                self,
                "Sous-titres Générés !",
                f"La génération des sous-titres est terminée avec succès !\n\n"
                f"Fichier(s) créés : {len(self.generated_files)}\n"
                f"Dossier : {self.generated_files[0].parent}",
            )
        else:
            self.status_label.setText("Aucun sous-titre généré.")

    def _on_worker_error(self, error_message: str) -> None:
        self.btn_generate.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self._update_model_status_label()
        self.status_label.setText("❌ Erreur pendant le traitement")
        QMessageBox.critical(self, "Erreur de génération", f"Une erreur est survenue :\n\n{error_message}")

    def _cancel_generation(self) -> None:
        if self.worker:
            self.status_label.setText("Arrêt en cours...")
            self.worker.cancel()

    def closeEvent(self, event) -> None:
        """Assure la fermeture propre du thread sans faire planter Python."""
        if self.thread and self.thread.isRunning():
            if self.worker:
                self.worker.cancel()
            self.thread.quit()
            self.thread.wait(1500)
        event.accept()

    def _open_last_generated_file(self) -> None:
        if not self.generated_files:
            QMessageBox.information(self, "Aucun fichier", "Aucun fichier généré.")
            return

        last_file = self.generated_files[-1]
        if not last_file.exists():
            QMessageBox.warning(self, "Fichier introuvable", f"Le fichier n'existe plus :\n{last_file}")
            return

        self._open_path_with_system(last_file)

    def _open_output_folder(self) -> None:
        folder = self.generated_files[0].parent if self.generated_files else self.output_dir
        if folder.exists():
            self._open_path_with_system(folder)

    @staticmethod
    def _open_path_with_system(path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception:
            pass


def main() -> None:
    """Point d'entrée principal de l'application."""
    import signal
    from PySide6.QtCore import QTimer

    app = QApplication(sys.argv)
    app.setApplicationName("SubtitleStudio AI")

    # Permettre à Python d'intercepter Ctrl+C proprement dans la boucle d'événements Qt
    signal.signal(signal.SIGINT, lambda *args: QApplication.quit())
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


# Alias pour rétrocompatibilité
SubtitleWindow = MainWindow

