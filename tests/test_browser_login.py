from types import SimpleNamespace

import pytest
from PySide6.QtCore import QUrl

from clara.browser import ExamPage, ExamBrowser
from clara.web_policy import WebPolicy


@pytest.mark.parametrize("url,gesture,allowed", [
    ("https://accounts.google.com/Login?continue=https://docs.google.com/forms/", True, True),
    ("https://accounts.google.com/Login", False, False),
    ("https://accounts.google.com.evil.test/Login", True, False),
    ("https://mail.google.com/", True, False),
    ("about:blank", True, False),
])
def test_login_popup_uses_current_page_only_for_user_click(url, gesture, allowed):
    loaded, blocked = [], []
    page = SimpleNamespace(
        policy=WebPolicy(["https://docs.google.com"], "https://docs.google.com/forms/d/test/viewform"),
        load=loaded.append, blocked=SimpleNamespace(emit=blocked.append),
    )
    request = SimpleNamespace(requestedUrl=lambda: QUrl(url), isUserInitiated=lambda: gesture)
    ExamPage.open_login_window(page, request)
    assert bool(loaded) == allowed
    assert bool(blocked) != allowed
    if allowed:
        assert loaded == [QUrl(url)]


def test_unsupported_passkey_is_cancelled_before_showing_help():
    events = []
    page = SimpleNamespace(blocked=SimpleNamespace(emit=lambda message: events.append(message)))
    request = SimpleNamespace(cancel=lambda: events.append("cancelled"))
    ExamPage.cancel_unsupported_passkey(page, request)
    assert events[0] == "cancelled"
    assert "Not now" in events[1]


def test_blocked_redirect_is_reported_without_credentials_or_tokens():
    diagnostic, notices = [], []
    page = SimpleNamespace(
        policy=WebPolicy(["https://docs.google.com"], "https://docs.google.com/forms/d/test/viewform"),
        navigationBlocked=SimpleNamespace(emit=lambda *args: diagnostic.append(args)),
        blocked=SimpleNamespace(emit=notices.append),
        url=lambda: QUrl("https://accounts.google.com/"),
    )
    assert not ExamPage.acceptNavigationRequest(page, QUrl("https://user:secret@blocked.test:8443/path?token=private#value"), None, True)
    assert diagnostic == [("https://blocked.test:8443", "NavigationMainFrame")]
    assert all(secret not in str(diagnostic) + str(notices) for secret in ("secret", "private", "/path", "user"))


@pytest.mark.parametrize("destination,main_frame,accepted,returned", [
    ("https://accounts.youtube.com/accounts/SetSID?token=hidden", False, True, False),
    ("https://accounts.youtube.com/", True, False, False),
    ("https://www.youtube.com/", False, False, False),
    ("https://myaccount.google.com/?continue=https://evil.test", True, False, True),
    ("https://myaccount.google.com/", False, False, False),
    ("https://myaccount.google.com.evil.test/", True, False, False),
])
def test_recorded_login_redirects(destination, main_frame, accepted, returned):
    returns = []
    page = SimpleNamespace(
        policy=WebPolicy(["https://docs.google.com"], "https://docs.google.com/forms/d/test/viewform"),
        url=lambda: QUrl("https://accounts.google.com/v3/signin/"),
        returnToFormRequested=SimpleNamespace(emit=lambda: returns.append(True)),
        navigationBlocked=SimpleNamespace(emit=lambda *args: None),
        blocked=SimpleNamespace(emit=lambda *args: None),
    )
    assert ExamPage.acceptNavigationRequest(page, QUrl(destination), None, main_frame) == accepted
    assert bool(returns) == returned


@pytest.mark.parametrize("current,allowed", [
    ("https://accounts.google.com/signin/passkey", True),
    ("https://docs.google.com/forms/d/example/viewform", False),
    ("https://accounts.google.com.evil.test/", False),
])
def test_return_to_form_keeps_fixed_destination_and_only_runs_during_login(current, allowed):
    form = "https://forms.gle/example"
    actions = []
    browser = SimpleNamespace(
        exam_page=SimpleNamespace(policy=WebPolicy(["https://forms.gle"], form)),
        start_url=form, url=lambda: QUrl(current), stop=lambda: actions.append("stop"),
        load=lambda url: actions.append(url.toString()),
    )
    ExamBrowser.return_to_form(browser)
    assert actions == (["stop", form] if allowed else [])
