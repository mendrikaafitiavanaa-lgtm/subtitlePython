"""UI package containing modern PySide6 views, styles, and background workers."""

from src.ui.main_window import MainWindow, SubtitleWindow, main
from src.ui.styles import APP_STYLESHEET
from src.ui.worker import SubtitleWorker

__all__ = [
    "MainWindow",
    "SubtitleWindow",
    "SubtitleWorker",
    "APP_STYLESHEET",
    "main",
]
