"""Styles CSS / QSS pour une interface moderne et élégante."""

APP_STYLESHEET = """
QMainWindow {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: 'Segoe UI', 'Ubuntu', 'Helvetica Neue', sans-serif;
}

QWidget {
    color: #e2e8f0;
    font-size: 13px;
}

/* Cartes et Groupes */
QGroupBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    margin-top: 14px;
    padding: 16px 14px 14px 14px;
    font-weight: bold;
    font-size: 13px;
    color: #38bdf8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    background-color: #0f172a;
    border-radius: 4px;
}

/* Boutons */
QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #3b82f6;
}

QPushButton:pressed {
    background-color: #1d4ed8;
}

QPushButton:disabled {
    background-color: #475569;
    color: #94a3b8;
}

QPushButton#btn-cancel {
    background-color: #dc2626;
}

QPushButton#btn-cancel:hover {
    background-color: #ef4444;
}

QPushButton#btn-secondary {
    background-color: #334155;
    color: #f1f5f9;
}

QPushButton#btn-secondary:hover {
    background-color: #475569;
}

/* Listes et Champs */
QListWidget {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px;
    color: #f8fafc;
}

QListWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
    margin-bottom: 2px;
}

QListWidget::item:hover {
    background-color: #1e293b;
}

QListWidget::item:selected {
    background-color: #1e3a8a;
    color: #93c5fd;
}

QComboBox {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f8fafc;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    border: 1px solid #334155;
    selection-background-color: #2563eb;
    color: #f8fafc;
}

/* Barre de progression */
QProgressBar {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    text-align: center;
    color: #f8fafc;
    font-weight: bold;
    height: 22px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #06b6d4);
    border-radius: 7px;
}

/* Console de Log */
QTextEdit {
    background-color: #090d16;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 10px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    color: #a5f3fc;
}

/* Badges et Info */
QLabel#badge-hardware {
    background-color: #1e293b;
    border: 1px solid #0284c7;
    color: #38bdf8;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: bold;
}

QLabel#video-info {
    color: #94a3b8;
    font-size: 12px;
}
"""
