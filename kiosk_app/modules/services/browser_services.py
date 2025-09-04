import os
import threading
import time
import requests

from PySide6.QtCore import QTimer, QObject, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from modules.utils.logger import get_logger

# When running in headless environments (e.g. unit tests) QtWebEngine normally
# refuses to start as root or without a display server.  The minimal
# environment variables below relax these restrictions so that the web view can
# be instantiated for testing purposes.  They are harmless in regular GUI
# execution where these variables may already be set by the host system.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

def make_webview() -> QWebEngineView:
    # Ensure a QApplication exists.  QtWebEngine widgets require an application
    # instance, but unit tests may call this factory without creating one.
    QApplication.instance() or QApplication([])
    w = QWebEngineView()
    w.setZoomFactor(1.0)
    return w

class BrowserService(QObject):
    page_ready = Signal()
    page_error = Signal(str)
    page_loading = Signal()  # neu

    def __init__(self, view: QWebEngineView, url: str, name: str = "Browser"):
        super().__init__()
        self.view = view
        self.url = url
        self.name = name
        self.log = get_logger(f"{__name__}.{name}")
        self.last_ok = time.time()

        self.view.loadStarted.connect(self._on_load_started)
        self.view.loadFinished.connect(self._on_load_finished)

        self.reload_timer = QTimer(self)
        self.reload_timer.setInterval(30000)
        self.reload_timer.timeout.connect(self._auto_reload)

    def start(self):
        self.log.info("Lade %s", self.url)
        self.view.setUrl(QUrl(self.url))
        self.reload_timer.start()

    def stop(self):
        self.reload_timer.stop()

    def _on_load_started(self):
        self.page_loading.emit()

    def _on_load_finished(self, ok: bool):
        if ok:
            self.last_ok = time.time()
            self.page_ready.emit()
        else:
            self.page_error.emit("Load failed")

    def _auto_reload(self):
        if time.time() - self.last_ok > 60:
            self.log.warning("Reload wegen Timeout")
            self.view.reload()

    def heartbeat(self, timeout_sec: int = 3):
        def ping():
            try:
                requests.get(self.url, timeout=timeout_sec)
                self.last_ok = time.time()
            except Exception as e:
                self.log.warning("Heartbeat fehlgeschlagen: %s", e)
        threading.Thread(target=ping, daemon=True).start()
