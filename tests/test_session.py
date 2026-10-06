import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from clara.app import MainWindow, Session
from clara.models import Exam, Question, password_digest


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def session(app, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    exam = Exam("Teste", "Escola", "", "internal", 1, password_digest("responsavel"), questions=[
        Question("2 + 2", ["1", "2", "3", "4"], 3),
        Question("3 + 3", ["3", "6", "9", "12"], 1),
    ])
    widget = Session(exam, "Aluno")
    yield widget
    widget.timer.stop()
    widget.deleteLater()
    app.processEvents()


def test_answers_persist_and_survive_navigation(session):
    session.answer(3)
    session.navigate(1)
    session.answer(1)
    session.navigate(-1)
    assert session.group.checkedId() == 3
    import json
    saved = json.loads(session.storage.read_text(encoding="utf-8"))
    assert saved["answers"] == {"0": 3, "1": 1}
    assert saved["grade"] is None


def test_browser_diagnostics_do_not_count_as_focus_losses(session):
    session.record_browser_block("https://example.org", "ResourceTypeXhr")
    report = session.report()
    assert report["events"] == []
    assert report["browser_blocks"][0]["origin"] == "https://example.org"
    session.finish("concluida")
    session.record_browser_block("https://other.test", "ResourceTypeScript")
    assert len(session.browser_blocks) == 1


def test_expiration_finishes_once_and_rejects_late_answer(session):
    results = []
    session.completed.connect(results.append)
    session.answer(3)
    session.deadline = time.monotonic() - 1
    session.answer(0)
    session.tick()
    session.finish("concluida")
    assert len(results) == 1
    assert results[0]["status"] == "tempo_encerrado"
    assert results[0]["grade"]["correct"] == 1
    assert session.answers[0] == 3
    assert not session.timer.isActive()


def test_save_failure_is_visible(session, monkeypatch):
    def failure(*args):
        raise OSError("disk full")
    monkeypatch.setattr("clara.app.atomic_json", failure)
    session.answer(3)
    assert session.last_save_error
    assert "Não foi possível salvar" in session.status.text()


def test_focus_event_is_not_a_cheating_verdict(session):
    session.record_focus()
    report = session.report()
    assert len(report["events"]) == 1
    assert report["verified"] is False
    assert "não comprova trapaça" in report["note"]


def test_start_requires_name_and_acknowledgement(app):
    window = MainWindow()
    window.demo()
    assert not window.start_button.isEnabled()
    window.student.setText("Aluno")
    assert not window.start_button.isEnabled()
    window.consent.setChecked(True)
    assert window.start_button.isEnabled()
    window.close()


def test_browser_policy_wiring(app):
    from clara.browser import ExamPage, RequestFilter
    from PySide6.QtCore import QUrl
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInfo
    profile = QWebEngineProfile()
    page = ExamPage(profile, ["https://school.edu"], None)
    kind = QWebEnginePage.NavigationType.NavigationTypeOther
    assert page.acceptNavigationRequest(QUrl("https://school.edu/exam"), kind, True)
    assert not page.acceptNavigationRequest(QUrl("https://school.edu.evil.test"), kind, True)
    assert page.createWindow(QWebEnginePage.WebWindowType.WebBrowserTab) is None
    assert page.chooseFiles(None, [], []) == []
    interceptor = RequestFilter(["https://school.edu"], profile)

    class Info:
        ResourceType = QWebEngineUrlRequestInfo.ResourceType

        def __init__(self, url, kind):
            self.url, self.kind, self.blocked = url, kind, False

        def requestUrl(self):
            return QUrl(self.url)

        def resourceType(self):
            return self.kind

        def block(self, value):
            self.blocked = value

    for url, kind, blocked in [
        ("https://evil.test/x.js", Info.ResourceType.ResourceTypeScript, True),
        ("https://school.edu/x.js", Info.ResourceType.ResourceTypeScript, False),
        ("data:text/html,hello", Info.ResourceType.ResourceTypeMainFrame, True),
        ("data:image/png;base64,abc", Info.ResourceType.ResourceTypeImage, False),
    ]:
        info = Info(url, kind)
        interceptor.interceptRequest(info)
        assert info.blocked is blocked
    # Destroy page before profile, as required by Qt WebEngine.
    import shiboken6
    shiboken6.delete(page)
    shiboken6.delete(profile)
