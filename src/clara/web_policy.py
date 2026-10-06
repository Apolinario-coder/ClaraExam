"""Platform resource permissions never become navigation permissions."""
from urllib.parse import urlsplit

from clara._core import is_allowed


def is_google_form(url: str) -> bool:
    if is_allowed(url, ["https://forms.gle"]):
        return True
    return is_allowed(url, ["https://docs.google.com"]) and urlsplit(url).path.startswith("/forms/")


class WebPolicy:
    def __init__(self, origins, start_url=""):
        self.origins = list(origins)
        self.google_forms = is_google_form(start_url)

    def navigation_allowed(self, url):
        return (is_allowed(url, self.origins)
                or (self.google_forms and is_google_form(url))
                or self.google_login_allowed(url))

    def google_login_allowed(self, url):
        # Exact HTTPS origin: this does not open Google Search, Gmail or Drive.
        return self.google_forms and is_allowed(url, ["https://accounts.google.com"])

    def login_window_allowed(self, url, user_initiated):
        return user_initiated and self.google_login_allowed(url)

    def login_frame_allowed(self, url, first_party):
        return (self.google_login_allowed(first_party)
                and is_allowed(url, ["https://accounts.youtube.com"]))

    def return_from_account_settings(self, url, current_url):
        return (self.google_login_allowed(current_url)
                and is_allowed(url, ["https://myaccount.google.com"]))

    def resource_allowed(self, url, kind, first_party):
        if self.login_frame_allowed(url, first_party) and kind in {
            "ResourceTypeSubFrame", "ResourceTypeScript", "ResourceTypeStylesheet",
            "ResourceTypeImage", "ResourceTypeXhr", "ResourceTypeFontResource",
        }:
            return True
        if kind in ("ResourceTypeMainFrame", "ResourceTypeSubFrame"):
            return self.navigation_allowed(url)
        if is_allowed(url, self.origins):
            return True
        if self.google_forms and (is_google_form(first_party) or self.google_login_allowed(first_party)):
            # Observed in actual login/form sessions. Keep these exceptions
            # restricted to background requests, never top-level navigation.
            if (kind in {"ResourceTypeXhr", "ResourceTypePing"}
                    and is_allowed(url, ["https://play.google.com"])
                    and urlsplit(url).path == "/log"):
                return True
            if kind == "ResourceTypeXhr" and is_allowed(url, ["https://signaler-pa.googleapis.com"]):
                return True
            if self.google_login_allowed(url):
                return True
            # Short forms.gle links redirect to docs.google.com/forms/.
            if is_allowed(url, ["https://docs.google.com"]):
                return True
            if kind in {"ResourceTypeScript", "ResourceTypeStylesheet", "ResourceTypeImage",
                        "ResourceTypeFontResource", "ResourceTypeXhr", "ResourceTypeFavicon"}:
                if is_allowed(url, ["https://www.gstatic.com", "https://ssl.gstatic.com"]):
                    return True
            if kind == "ResourceTypeStylesheet" and is_allowed(url, ["https://fonts.googleapis.com"]):
                return True
            if kind == "ResourceTypeFontResource" and is_allowed(url, ["https://fonts.gstatic.com"]):
                return True
            if kind == "ResourceTypeImage" and is_allowed(url, [
                "https://lh3.googleusercontent.com", "https://lh4.googleusercontent.com",
                "https://lh5.googleusercontent.com", "https://lh6.googleusercontent.com",
            ]):
                return True
        return False
