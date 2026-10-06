from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette


def apply_theme(app):
    """Use the same light palette for styled and native controls on every OS theme."""
    app.setStyle("Fusion")
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    palette = QPalette()
    colors = {
        "Window": "#f4f6f8", "WindowText": "#172d3c",
        "Base": "#ffffff", "AlternateBase": "#edf3f5", "Text": "#172d3c",
        "Button": "#ffffff", "ButtonText": "#172d3c",
        "Highlight": "#087f73", "HighlightedText": "#ffffff",
        "ToolTipBase": "#ffffff", "ToolTipText": "#172d3c",
        "PlaceholderText": "#607281", "Link": "#087f73",
        "LinkVisited": "#06695f", "Light": "#ffffff", "Midlight": "#e0e6ea",
        "Mid": "#a8b8c2", "Dark": "#708791", "Shadow": "#607281",
        "BrightText": "#ffffff", "Accent": "#087f73",
    }
    for role, color in colors.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#81919c"))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)


STYLE = """
QWidget { font-family: 'Segoe UI'; font-size: 14px; color: #172d3c; }
QMainWindow, QWidget#canvas { background: #f4f6f8; }
QWidget#sidebar { background: #142d3d; }
QWidget#sidebar QLabel { color: #e5eef4; background: transparent; }
QLabel#brand { font-size: 29px; font-weight: 700; }
QLabel#heading { font-size: 30px; font-weight: 700; }
QLabel#subheading { font-size: 19px; font-weight: 600; }
QLabel#muted { color: #607281; }
QLabel#eyebrow { color: #13796f; font-size: 12px; font-weight: 700; }
QLabel#notice { background: #fff4d8; color: #745414; padding: 14px; border-radius: 8px; }
QLabel#success { background: #dff3ec; color: #176b58; padding: 14px; border-radius: 8px; }
QFrame#card { background: white; border: 1px solid #e0e6ea; border-radius: 12px; }
QPushButton { background: #ffffff; border: 1px solid #cfd9de; border-radius: 7px; padding: 11px 17px; font-weight: 600; }
QPushButton:hover { background: #e8f3f1; border-color: #14988a; }
QPushButton:disabled { color: #8c9ca6; background: #edf0f2; }
QPushButton#primary { background: #087f73; color: white; border: none; }
QPushButton#primary:hover { background: #06695f; }
QPushButton#nav { text-align: left; background: transparent; color: #e5eef4; border: none; padding: 14px; }
QPushButton#nav:hover { background: #254556; }
QLineEdit, QTextEdit, QSpinBox, QComboBox, QListWidget { background: white; border: 1px solid #ccd7de; border-radius: 6px; padding: 9px; selection-background-color: #087f73; }
QLineEdit:focus, QTextEdit:focus { border: 1px solid #087f73; }
QTabWidget::pane { border: 1px solid #dce4e8; background: white; border-radius: 6px; }
QTabBar::tab { padding: 12px 22px; background: #e8edef; }
QTabBar::tab:selected { background: #d8eee8; color: #096e62; }
QScrollArea { border: none; background: transparent; }
QRadioButton { spacing: 10px; padding: 12px; }
QRadioButton::indicator { width: 18px; height: 18px; border: 1px solid #708791; border-radius: 10px; background: white; }
QRadioButton::indicator:checked { background: #087f73; border: 5px solid #d9eee9; width: 10px; height: 10px; }
QRadioButton::indicator:hover { border-color: #087f73; }
QCheckBox { spacing: 10px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QProgressBar { border: none; background: #e1e9ed; border-radius: 4px; height: 8px; }
QProgressBar::chunk { background: #087f73; border-radius: 4px; }
"""
