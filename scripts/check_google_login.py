"""Read-only login-page check. Never enters credentials or submits a form."""
import json
import os
from pathlib import Path
from urllib.parse import urlencode

os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

from PySide6.QtCore import QEvent, QEventLoop, QTimer, QUrl, Qt
from PySide6.QtWidgets import QApplication
from clara.browser import ExamBrowser
from clara.models import Exam
from clara.theme import apply_theme


def pause(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main():
    app = QApplication([])
    apply_theme(app)
    form = "https://docs.google.com/forms/d/e/1FAIpQLSccPF-S9sqCjxM0bU5SiBF72NtydiN2n5huZThqDd07Xe01sg/viewform?usp=dialog"
    exam = Exam(title="Validação de login", institution="", instructions="", minutes=30, exit_hash="",
                mode="external", start_url=form,
                allowed_origins=["https://docs.google.com"])
    browser = ExamBrowser(exam)
    browser.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    browser.resize(1100, 800)
    browser.show()
    blocked = []
    browser.interceptor.requestBlocked.connect(lambda origin, kind: blocked.append({"origin": origin, "kind": kind}))
    pause(7000)
    login = "https://accounts.google.com/Login?" + urlencode({"continue": form, "service": "wise"})
    browser.load(QUrl(login))
    pause(10000)
    result = {"origin": browser.url().host(), "path": browser.url().path(), "blocked_resources": blocked}
    loop = QEventLoop()
    def inspected(value):
        result.update(json.loads(value))
        loop.quit()
    browser.page().runJavaScript("""JSON.stringify({
        title: document.title,
        email_input: !!document.querySelector('input#identifierId, input[type=email], input[autocomplete=username]'),
        stylesheet_count: document.styleSheets.length
    })""", inspected)
    QTimer.singleShot(3000, loop.quit)
    loop.exec()
    output = Path("build/google-login")
    output.mkdir(parents=True, exist_ok=True)
    browser.grab().save(str(output / "login.png"))
    (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    # Detach the test interceptor before destroying a profile with live requests.
    browser.stop()
    browser.profile.setUrlRequestInterceptor(None)
    browser.dispose()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    browser.close()
    browser.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.quit()
    print(json.dumps(result, indent=2))
    assert result.get("email_input"), "Google login email field did not load"


if __name__ == "__main__":
    main()
