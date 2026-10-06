"""Qt-side filtering shares the native guard's policy for app-local key events."""
from PySide6.QtCore import Qt
from clara._core import shortcut_blocked

KEYS = {
    Qt.Key.Key_Tab: 0x09, Qt.Key.Key_Backtab: 0x09, Qt.Key.Key_Escape: 0x1B,
    Qt.Key.Key_F4: 0x73, Qt.Key.Key_F5: 0x74, Qt.Key.Key_F11: 0x7A,
    Qt.Key.Key_F12: 0x7B, Qt.Key.Key_Print: 0x2C, Qt.Key.Key_Menu: 0x5D,
    Qt.Key.Key_Super_L: 0x5B, Qt.Key.Key_Super_R: 0x5C,
}


def restricted_event(event):
    modifiers = event.modifiers()
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        return True
    key = KEYS.get(event.key(), event.key() if 0 <= event.key() < 256 else 0)
    return shortcut_blocked(key, bool(modifiers & Qt.KeyboardModifier.AltModifier),
                            bool(modifiers & Qt.KeyboardModifier.ControlModifier),
                            bool(modifiers & Qt.KeyboardModifier.ShiftModifier))
