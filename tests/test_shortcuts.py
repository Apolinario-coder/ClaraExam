import gc
import os
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QInputDialog

from clara._core import start_keyboard_guard
from clara.app import MainWindow
from clara.shortcuts import restricted_event


def test_native_hook_install_release_and_restart():
    guard = start_keyboard_guard()
    try:
        assert guard.active
        with pytest.raises(RuntimeError, match="já está ativo"):
            start_keyboard_guard()
    finally:
        guard.stop()
    assert not guard.active
    guard.stop()
    again = start_keyboard_guard()
    assert again.active
    del again
    gc.collect()
    final = start_keyboard_guard()
    try:
        assert final.active
    finally:
        final.stop()


@pytest.mark.parametrize("key,modifiers,blocked", [
    (Qt.Key.Key_F11, Qt.KeyboardModifier.NoModifier, True),
    (Qt.Key.Key_F12, Qt.KeyboardModifier.NoModifier, True),
    (Qt.Key.Key_Tab, Qt.KeyboardModifier.AltModifier, True),
    (Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier, True),
    (Qt.Key.Key_J, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier, True),
    (Qt.Key.Key_U, Qt.KeyboardModifier.ControlModifier, True),
    (Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier, False),
    (Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier, False),
    (Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier, False),
])
def test_qt_filter_matches_native_policy(key, modifiers, blocked):
    event = QKeyEvent(QEvent.Type.KeyPress, key, modifiers)
    assert restricted_event(event) is blocked


@pytest.fixture
def window(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    class Guard:
        active = True
        stopped = 0

        def stop(self):
            self.active = False
            self.stopped += 1

    guard = Guard()
    monkeypatch.setattr("clara.app.start_keyboard_guard", lambda: guard)
    widget = MainWindow()
    widget.demo()
    widget.student.setText("Teste")
    widget.consent.setChecked(True)
    yield widget, guard, app
    if widget.session and not widget.session.finished:
        widget.session.finish("interrompida_pelo_responsavel")
    widget.close()
    widget.deleteLater()
    app.processEvents()


@pytest.mark.parametrize("reason", ["concluida", "tempo_encerrado", "interrompida_pelo_responsavel"])
def test_session_termination_releases_before_saving_result(window, reason, monkeypatch):
    widget, guard, app = window
    widget.start_session()
    session = widget.session
    original = session.persist

    def persist(status):
        assert not guard.active
        return original(status)

    monkeypatch.setattr(session, "persist", persist)
    session.finish(reason)
    assert widget.session is None
    assert widget.keyboard_guard is None
    assert guard.stopped == 1


def test_startup_failure_releases_guard(window, monkeypatch):
    widget, guard, app = window
    errors = []
    monkeypatch.setattr("clara.app.show_error", lambda parent, error: errors.append(str(error)))

    def broken(*args):
        raise RuntimeError("construction failed")

    monkeypatch.setattr("clara.app.Session", broken)
    widget.start_session()
    assert widget.session is None
    assert not guard.active
    assert errors == ["construction failed"]


def test_guard_failure_prevents_session(window, monkeypatch):
    widget, guard, app = window
    errors = []
    monkeypatch.setattr("clara.app.show_error", lambda parent, error: errors.append(str(error)))

    def unavailable():
        raise RuntimeError("hook unavailable")

    monkeypatch.setattr("clara.app.start_keyboard_guard", unavailable)
    widget.start_session()
    assert widget.session is None
    assert errors == ["hook unavailable"]


def test_wrong_exit_password_keeps_guard(window, monkeypatch):
    widget, guard, app = window
    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("incorrect", True))
    monkeypatch.setattr("clara.app.show_error", lambda *args: None)
    widget.start_session()
    widget.session.request_exit()
    assert guard.active
    assert not widget.session.finished


def test_guard_stopped_unexpectedly_ends_session(window):
    widget, guard, app = window
    widget.start_session()
    guard.active = False
    widget.check_protection()
    assert widget.session is None


def test_window_cannot_remain_outside_fullscreen(window):
    widget, guard, app = window
    widget.start_session()
    widget.showNormal()
    app.processEvents()
    assert widget.isFullScreen()
