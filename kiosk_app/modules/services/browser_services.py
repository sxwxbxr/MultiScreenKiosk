import threading
import time
import requests

try:  # pragma: no cover - optional Qt dependency
    from PyQt5.QtCore import QTimer, QObject, pyqtSignal as Signal, QUrl  # type: ignore
    from PyQt5.QtWebEngineWidgets import QWebEngineView  # type: ignore
    _QT_AVAILABLE = True
except Exception:  # pragma: no cover - testing fallback
    _QT_AVAILABLE = False

    class _DummySignal:
        def connect(self, handler):
            self._handler = handler  # type: ignore[attr-defined]

        def emit(self, *args, **kwargs):
            handler = getattr(self, "_handler", None)
            if handler:
                try:
                    handler(*args, **kwargs)
                except Exception:
                    pass

    def Signal(*_args, **_kwargs):  # type: ignore
        return _DummySignal()

    class QObject:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            pass

    class QTimer:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            self.timeout = _DummySignal()
            self._interval = 0

        def setInterval(self, value):
            self._interval = value

        def start(self):
            pass

        def stop(self):
            pass

    class QUrl:  # type: ignore
        def __init__(self, url: str):
            self._url = url

    class QWebEngineView:  # type: ignore
        def __init__(self):
            self._zoom = 1.0
            self._url = None
            self.loadStarted = _DummySignal()
            self.loadFinished = _DummySignal()

        def setZoomFactor(self, value):
            self._zoom = value

        def setUrl(self, url):
            self._url = url

        def reload(self):
            pass

from modules.utils.logger import get_logger

def make_webview() -> QWebEngineView:
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
