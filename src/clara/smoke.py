"""Opt-in executable validation. Writes only to the specified output directory."""
import json
import os
import sys
import traceback
from pathlib import Path


def main():
    output = Path(sys.argv[sys.argv.index("--smoke-test") + 1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    native_theme_test = "--native-theme-test" in sys.argv
    os.environ["QT_QPA_PLATFORM"] = "windows" if native_theme_test else "offscreen"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
    os.environ["LOCALAPPDATA"] = str(output / "data")
    window = None
    try:
        from PySide6.QtCore import QEventLoop, QTimer, QUrl, Qt
        from PySide6.QtGui import QColor, QFontDatabase, QPalette
        from PySide6.QtWidgets import QApplication
        from clara.app import MainWindow
        from clara.browser import ExamBrowser
        from clara.models import Exam
        from clara.theme import apply_theme
        from clara._core import https_origin, is_allowed

        app = QApplication([])
        # The offscreen Qt platform does not discover Windows system fonts itself.
        for font in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
            QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / font))
        # Reproduce a dark inherited palette; the production initializer must override it.
        dark = QPalette()
        dark.setColor(QPalette.ColorRole.Window, QColor("#202020"))
        dark.setColor(QPalette.ColorRole.Base, QColor("#181818"))
        dark.setColor(QPalette.ColorRole.Button, QColor("#303030"))
        app.setPalette(dark)
        apply_theme(app)
        assert app.palette().color(QPalette.ColorRole.Window).name() == "#f4f6f8"
        assert app.palette().color(QPalette.ColorRole.Base).name() == "#ffffff"
        window = MainWindow()
        if native_theme_test:
            window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        window.show()
        app.processEvents()
        window.grab().save(str(output / "01-inicio.png"))
        window.stack.setCurrentWidget(window.teacher)
        app.processEvents()
        window.grab().save(str(output / "02-professor.png"))
        window.demo()
        window.exam.save(output / "exemplo.clara.json")
        assert Exam.load(output / "exemplo.clara.json") == window.exam
        window.student.setText("Aluno de demonstração")
        window.consent.setChecked(True)
        app.processEvents()
        window.grab().save(str(output / "03-instrucoes.png"))
        window.start_button.click()
        window.resize(1180, 820)
        app.processEvents()
        session = window.session
        assert window.keyboard_guard and window.keyboard_guard.active
        session.group.button(2).click()
        session.next.click()
        session.group.button(1).click()
        session.next.click()
        session.group.button(1).click()
        app.processEvents()
        window.grab().save(str(output / "04-avaliacao.png"))
        session.finish("concluida")
        assert window.keyboard_guard is None
        app.processEvents()
        window.grab().save(str(output / "05-resultado.png"))
        assert window.session is None
        assert is_allowed("https://example.com/exam", ["https://example.com"])
        assert not is_allowed("https://example.com.evil.test", ["https://example.com"])

        if "--local-only" in sys.argv:
            result = {"native_core": True, "internal_flow": True,
                      "keyboard_guard_installed_and_released": True,
                      "light_theme_overrides_dark_palette": True,
                      "packaged": getattr(sys, "frozen", False), "network_tested": False}
            window.close()
            (output / "smoke-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            return

        exam = window.exam
        exam.mode = "external"
        exam.start_url = sys.argv[sys.argv.index("--external-url") + 1] if "--external-url" in sys.argv else "https://example.com"
        exam.allowed_origins = [https_origin(exam.start_url)]
        browser = ExamBrowser(exam)
        blocked_resources = []
        blocked_resource_types = []
        browser.message.connect(blocked_resources.append)
        browser.interceptor.requestBlocked.connect(lambda origin, kind: blocked_resource_types.append({"origin": origin, "type": kind}))
        if native_theme_test:
            browser.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        browser.resize(1000, 700)
        browser.show()
        loop = QEventLoop()
        loaded = []
        browser.loadFinished.connect(lambda ok: (loaded.append(ok), loop.quit()))
        QTimer.singleShot(20000, loop.quit)
        loop.exec()
        paint = QEventLoop()
        QTimer.singleShot(2000, paint.quit)
        paint.exec()
        page_text = []
        read = QEventLoop()
        browser.page().toPlainText(lambda value: (page_text.append(value), read.quit()))
        QTimer.singleShot(3000, read.quit)
        read.exec()
        browser.grab().save(str(output / "06-navegador.png"))
        result = {"native_core": True, "internal_flow": True, "browser_created": True,
                  "external_page_loaded": bool(loaded and loaded[-1]), "packaged": getattr(sys, "frozen", False)}
        result["light_theme_overrides_dark_palette"] = True
        result["native_windows_theme_test"] = native_theme_test
        result["external_content_verified"] = bool(page_text and len(page_text[0]) > 50 and "documentation" in page_text[0].lower())
        if "--external-url" in sys.argv:
            result["external_content_verified"] = bool(page_text and len(page_text[0]) > 50)
        diagnostics = []
        inspect = QEventLoop()
        browser.page().runJavaScript("""JSON.stringify({
            title: document.title,
            stylesheetCount: document.styleSheets.length,
            linkedStyles: Array.from(document.querySelectorAll('link[rel=stylesheet]')).map(e => ({origin: new URL(e.href).origin, loaded: !!e.sheet})),
            bodyFont: getComputedStyle(document.body).fontFamily,
            scriptCount: document.scripts.length,
            forms: document.forms.length,
            loadedResourceOrigins: [...new Set(performance.getEntriesByType('resource').filter(e => e.duration > 0).map(e => new URL(e.name).origin))]
        })""", lambda value: (diagnostics.append(value), inspect.quit()))
        QTimer.singleShot(3000, inspect.quit)
        inspect.exec()
        result["page_diagnostics"] = json.loads(diagnostics[0]) if diagnostics and diagnostics[0] else {}
        result["blocked_resource_messages"] = list(blocked_resources)
        result["blocked_resource_types"] = list(blocked_resource_types)
        (output / "page-diagnostics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if browser.interceptor.policy.google_forms:
            details = result["page_diagnostics"]
            assert details.get("forms", 0) > 0, "The Forms page did not load a form"
            assert details.get("linkedStyles") and all(s["loaded"] for s in details["linkedStyles"]), "A form stylesheet failed to load"
            critical = {"ResourceTypeStylesheet", "ResourceTypeScript", "ResourceTypeFontResource"}
            assert not any(r["type"] in critical for r in blocked_resource_types), "A form dependency was blocked"
            result["google_forms_dependencies_verified"] = True
        # Check the actual browser rejects an unlisted host without relying only on the Rust unit test.
        blocked = []
        browser.exam_page.blocked.connect(blocked.append)
        browser.load(QUrl("https://example.org"))
        wait = QEventLoop()
        QTimer.singleShot(500, wait.quit)
        wait.exec()
        assert blocked, "Browser did not report blocked navigation"
        result["browser_rejected_unlisted_host"] = True
        browser.dispose()
        browser.close()
        browser.deleteLater()
        window.close()
        app.processEvents()
        (output / "smoke-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception:
        (output / "smoke-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        if window is not None:
            window.release_keyboard_guard()
