from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from clara.web_policy import WebPolicy


class RequestFilter(QWebEngineUrlRequestInterceptor):
    blocked = Signal(str)
    requestBlocked = Signal(str, str)

    def __init__(self, origins, parent, start_url=""):
        super().__init__(parent)
        self.origins = origins
        self.policy = WebPolicy(origins, start_url)
        self.reported = set()

    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        # data: is permitted only for embedded images/fonts/styles, never navigation.
        inline_types = {
            info.ResourceType.ResourceTypeImage,
            info.ResourceType.ResourceTypeFontResource,
            info.ResourceType.ResourceTypeStylesheet,
        }
        if info.requestUrl().scheme() == "data" and info.resourceType() in inline_types:
            return
        first_party = info.firstPartyUrl().toString() if hasattr(info, "firstPartyUrl") else ""
        if not self.policy.resource_allowed(url, info.resourceType().name, first_party):
            info.block(True)
            # Report the origin, never a URL containing form IDs, tokens or answers.
            address = info.requestUrl()
            origin = f"{address.scheme()}://{address.host()}"
            if address.port() != -1:
                origin += f":{address.port()}"
            kind = info.resourceType().name
            description = {"ResourceTypeStylesheet": "estilo", "ResourceTypeScript": "script",
                           "ResourceTypeFontResource": "fonte", "ResourceTypeImage": "imagem"}.get(kind, "recurso")
            if (origin, kind) not in self.reported:
                self.reported.add((origin, kind))
                self.requestBlocked.emit(origin, kind)
                if kind == "ResourceTypeFavicon":
                    return
                self.blocked.emit(f"Bloqueado: {origin} ({description}). Se a página estiver incompleta, informe esse endereço ao responsável.")


class ExamPage(QWebEnginePage):
    blocked = Signal(str)
    navigationBlocked = Signal(str, str)
    returnToFormRequested = Signal()

    def __init__(self, profile, origins, parent, start_url=""):
        super().__init__(profile, parent)
        self.origins = origins
        self.policy = WebPolicy(origins, start_url)
        self.newWindowRequested.connect(self.open_login_window)
        self.webAuthUxRequested.connect(self.cancel_unsupported_passkey)

    def cancel_unsupported_passkey(self, request):
        # No authenticator UI is implemented. Resolve the request instead of
        # leaving Chromium waiting for a PIN/account selection indefinitely.
        request.cancel()
        self.blocked.emit("Chaves de acesso (passkeys) não são suportadas nesta versão. "
                          "No Google, escolha ‘Not now’ (Agora não) ou outro método de login. "
                          "Se a página continuar travada, use ‘Voltar ao formulário’.")

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        current_url = self.url().toString()
        if is_main_frame and self.policy.return_from_account_settings(url.toString(), current_url):
            self.returnToFormRequested.emit()
            return False
        if not is_main_frame and self.policy.login_frame_allowed(url.toString(), current_url):
            return True
        allowed = self.policy.navigation_allowed(url.toString())
        if not allowed:
            origin = f"{url.scheme()}://{url.host()}"
            if url.port() != -1:
                origin += f":{url.port()}"
            self.navigationBlocked.emit(origin, "NavigationMainFrame" if is_main_frame else "NavigationSubFrame")
            self.blocked.emit(f"Redirecionamento bloqueado: {origin}. Informe esse endereço ao responsável.")
        return allowed

    def open_login_window(self, request):
        if self.policy.login_window_allowed(request.requestedUrl().toString(), request.isUserInitiated()):
            # A user-clicked login link stays in the exam view and ephemeral profile.
            self.load(request.requestedUrl())
        else:
            self.blocked.emit("Novas janelas estão desativadas. Peça ajuda ao responsável.")

    def chooseFiles(self, mode, old_files, accepted_mime_types):
        self.blocked.emit("Envio de arquivos está desativado nesta versão.")
        return []


class ExamBrowser(QWebEngineView):
    message = Signal(str)
    loginActive = Signal(bool)

    def __init__(self, exam, parent=None):
        super().__init__(parent)
        self.start_url = exam.start_url
        # An unnamed profile is off the record: it does not reuse the user's browser cookies.
        self.profile = QWebEngineProfile(self)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        self.interceptor = RequestFilter(exam.allowed_origins, self.profile, exam.start_url)
        self.interceptor.blocked.connect(self.message)
        self.profile.setUrlRequestInterceptor(self.interceptor)
        self.exam_page = ExamPage(self.profile, exam.allowed_origins, self, exam.start_url)
        self.exam_page.blocked.connect(self.message)
        self.exam_page.returnToFormRequested.connect(self.schedule_form_return)
        self.setPage(self.exam_page)
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,
                              self.exam_page.policy.google_forms)
        for attribute in (
            QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard,
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            QWebEngineSettings.WebAttribute.FullScreenSupportEnabled,
            QWebEngineSettings.WebAttribute.ScreenCaptureEnabled,
        ):
            settings.setAttribute(attribute, False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.profile.downloadRequested.connect(lambda download: download.cancel())
        self.exam_page.permissionRequested.connect(lambda permission: permission.deny())
        self.loadFinished.connect(self.loaded)
        self.urlChanged.connect(self.login_location_changed)
        self.load(QUrl(exam.start_url))

    def login_location_changed(self, url):
        active = self.exam_page.policy.google_login_allowed(url.toString())
        self.loginActive.emit(active)

    def return_to_form(self):
        # Keep this profile's cookies, but never accept an arbitrary return URL.
        if self.exam_page.policy.google_login_allowed(self.url().toString()):
            self.stop()
            self.load(QUrl(self.start_url))

    def schedule_form_return(self):
        # Defer until acceptNavigationRequest has rejected the settings page.
        QTimer.singleShot(0, self.return_to_form)

    def loaded(self, success):
        if not success:
            self.message.emit("Não foi possível carregar a página. Verifique a conexão e os sites permitidos com o responsável.")

    def dispose(self):
        self.stop()
        # The profile must outlive every page using it.
        self.exam_page.deleteLater()
