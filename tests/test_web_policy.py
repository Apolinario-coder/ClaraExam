import pytest

from clara.web_policy import WebPolicy, is_google_form

FORM = "https://docs.google.com/forms/d/e/example/viewform"


@pytest.mark.parametrize("origin,kind", [
    ("https://www.gstatic.com", "ResourceTypeStylesheet"),
    ("https://www.gstatic.com", "ResourceTypeScript"),
    ("https://www.gstatic.com", "ResourceTypeXhr"),
    ("https://ssl.gstatic.com", "ResourceTypeFavicon"),
    ("https://ssl.gstatic.com", "ResourceTypeImage"),
    ("https://fonts.googleapis.com", "ResourceTypeStylesheet"),
    ("https://fonts.gstatic.com", "ResourceTypeFontResource"),
    ("https://lh3.googleusercontent.com", "ResourceTypeImage"),
])
def test_forms_assets_allowed_but_not_navigation(origin, kind):
    policy = WebPolicy(["https://docs.google.com"], FORM)
    assert policy.resource_allowed(origin + "/asset", kind, FORM)
    assert not policy.navigation_allowed(origin + "/asset")
    assert not policy.resource_allowed(origin + "/asset", "ResourceTypeSubFrame", FORM)


def test_resource_permissions_are_scoped_to_forms():
    url = "https://www.gstatic.com/script.js"
    policy = WebPolicy(["https://docs.google.com"], FORM)
    assert not policy.resource_allowed(url, "ResourceTypeScript", "https://unrelated.test")
    assert not WebPolicy(["https://school.edu"], "https://school.edu").resource_allowed(url, "ResourceTypeScript", FORM)
    assert not policy.resource_allowed("https://www.gstatic.com.evil.test/style.css", "ResourceTypeStylesheet", FORM)
    assert not policy.resource_allowed("https://lh3.googleusercontent.com/code.js", "ResourceTypeScript", FORM)
    assert not policy.resource_allowed("http://www.gstatic.com/style.css", "ResourceTypeStylesheet", FORM)
    assert not policy.resource_allowed("https://play.google.com/store", "ResourceTypeXhr", FORM)
    assert not policy.navigation_allowed("https://play.google.com")


def test_forms_short_link_redirect():
    policy = WebPolicy(["https://forms.gle"], "https://forms.gle/example")
    assert policy.navigation_allowed(FORM)
    assert policy.resource_allowed(FORM, "ResourceTypeMainFrame", "https://forms.gle/example")
    assert not policy.navigation_allowed("https://docs.google.com/document/d/other")
    assert not is_google_form("https://docs.google.com.evil.test/forms/test")
    assert not is_google_form("https://school.edu/?next=" + FORM)


def test_google_login_and_return_to_short_link_form():
    policy = WebPolicy(["https://forms.gle"], "https://forms.gle/example")
    login = "https://accounts.google.com/ServiceLogin?continue=" + FORM
    assert policy.navigation_allowed(login)
    assert policy.resource_allowed(login, "ResourceTypeMainFrame", FORM)
    assert policy.resource_allowed("https://accounts.google.com/v3/signin/_/AccountsSignInUi/data/batchexecute",
                                   "ResourceTypeXhr", login)
    assert policy.resource_allowed("https://www.gstatic.com/_/mss/boq-identity/_/js/k=example",
                                   "ResourceTypeScript", login)
    assert policy.resource_allowed("https://fonts.gstatic.com/font.woff2", "ResourceTypeFontResource", login)
    assert policy.navigation_allowed(FORM)
    assert policy.resource_allowed(FORM, "ResourceTypeMainFrame", login)
    assert policy.login_window_allowed(login, True)
    assert not policy.login_window_allowed(login, False)


@pytest.mark.parametrize("url", [
    "http://accounts.google.com/Login", "https://accounts.google.com.evil.test/Login",
    "https://accounts.google.com@evil.test/Login", "https://accounts.google.com:444/Login",
    "https://www.google.com/search?q=test", "https://mail.google.com/",
    "https://drive.google.com/", "https://myaccount.google.com/", "javascript:alert(1)",
])
def test_login_does_not_open_other_sites(url):
    policy = WebPolicy(["https://forms.gle"], "https://forms.gle/example")
    assert not policy.navigation_allowed(url)
    assert not policy.login_window_allowed(url, True)
    assert not policy.resource_allowed(url, "ResourceTypeMainFrame", "https://accounts.google.com/")


def test_login_exception_is_only_for_google_forms():
    policy = WebPolicy(["https://school.edu"], "https://school.edu/exam")
    assert not policy.navigation_allowed("https://accounts.google.com/Login")
    assert not policy.login_window_allowed("https://accounts.google.com/Login", True)
    assert not policy.resource_allowed("https://www.gstatic.com/script.js", "ResourceTypeScript",
                                       "https://accounts.google.com/Login")
    forms = WebPolicy(["https://docs.google.com"], FORM)
    assert not forms.resource_allowed("https://accounts.google.com/api", "ResourceTypeXhr", "https://evil.test")


@pytest.mark.parametrize("url,kind", [
    ("https://play.google.com/log?format=json", "ResourceTypeXhr"),
    ("https://play.google.com/log", "ResourceTypePing"),
    ("https://signaler-pa.googleapis.com/punctual/multi-watch/channel", "ResourceTypeXhr"),
])
def test_login_background_dependencies_do_not_expand_navigation(url, kind):
    policy = WebPolicy(["https://docs.google.com"], FORM)
    for source in (FORM, "https://accounts.google.com/v3/signin/identifier"):
        assert policy.resource_allowed(url, kind, source)
        assert not policy.resource_allowed(url, "ResourceTypeMainFrame", source)
        assert not policy.resource_allowed(url, "ResourceTypeSubFrame", source)
        assert not policy.resource_allowed(url, "ResourceTypeScript", source)
    assert not policy.navigation_allowed(url)
    assert not policy.resource_allowed(url, kind, "https://unrelated.test")
    assert not WebPolicy(["https://school.edu"], "https://school.edu/exam").resource_allowed(url, kind, FORM)


@pytest.mark.parametrize("url", [
    "http://play.google.com/log", "https://play.google.com:444/log",
    "https://play.google.com/log/other", "https://play.google.com.evil.test/log",
    "https://signaler-pa.googleapis.com.evil.test/channel",
])
def test_google_background_exceptions_require_exact_addresses(url):
    assert not WebPolicy(["https://docs.google.com"], FORM).resource_allowed(url, "ResourceTypeXhr", FORM)


def test_embedded_google_account_sync_is_scoped_to_login():
    policy = WebPolicy(["https://docs.google.com"], FORM)
    url = "https://accounts.youtube.com/accounts/SetSID?token=example"
    assert policy.resource_allowed(url, "ResourceTypeSubFrame", "https://accounts.google.com/")
    assert not policy.resource_allowed(url, "ResourceTypeMainFrame", "https://accounts.google.com/")
    assert not policy.resource_allowed(url, "ResourceTypeSubFrame", FORM)
    assert not policy.resource_allowed(url, "ResourceTypeSubFrame", "https://evil.test")
    assert not policy.resource_allowed("https://accounts.youtube.com.evil.test/", "ResourceTypeSubFrame", "https://accounts.google.com/")
    assert not policy.resource_allowed("http://accounts.youtube.com/", "ResourceTypeSubFrame", "https://accounts.google.com/")
    assert not policy.resource_allowed("https://accounts.youtube.com:444/", "ResourceTypeSubFrame", "https://accounts.google.com/")
    assert not policy.return_from_account_settings("https://myaccount.google.com/", FORM)
    assert not policy.navigation_allowed("https://myaccount.google.com/")
    assert not WebPolicy(["https://school.edu"], "https://school.edu/exam").login_frame_allowed(url, "https://accounts.google.com/")
