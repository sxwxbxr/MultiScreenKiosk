import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
base_str = str(BASE_DIR)
if base_str not in sys.path:
    sys.path.insert(0, base_str)

import types


def _install_qtcore_stub():
    if "PySide6.QtCore" in sys.modules:
        return sys.modules["PySide6.QtCore"]

    qtcore = types.ModuleType("PySide6.QtCore")

    class _DummySignal:
        def __init__(self):
            self._handler = None

        def connect(self, handler):
            self._handler = handler

        def emit(self, *args, **kwargs):
            if self._handler:
                try:
                    self._handler(*args, **kwargs)
                except Exception:
                    pass

    def Signal(*_args, **_kwargs):  # type: ignore
        return _DummySignal()

    class QObject:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            pass

    class QTimer:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            self.timeout = Signal()
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

    qtcore.Signal = Signal
    qtcore.QObject = QObject
    qtcore.QTimer = QTimer
    qtcore.QUrl = QUrl
    qtcore.__package__ = "PySide6"
    sys.modules["PySide6.QtCore"] = qtcore
    return qtcore


def _install_qtwe_stub():
    if "PySide6.QtWebEngineWidgets" in sys.modules:
        return sys.modules["PySide6.QtWebEngineWidgets"]

    qtwe = types.ModuleType("PySide6.QtWebEngineWidgets")

    class QWebEngineView:  # type: ignore
        def __init__(self):
            core = _install_qtcore_stub()
            self.loadStarted = core.Signal()
            self.loadFinished = core.Signal()
            self._zoom = 1.0
            self._url = None

        def setZoomFactor(self, value):
            self._zoom = value

        def setUrl(self, url):
            self._url = url

        def reload(self):
            pass

    qtwe.QWebEngineView = QWebEngineView
    qtwe.__package__ = "PySide6"
    sys.modules["PySide6.QtWebEngineWidgets"] = qtwe
    return qtwe


try:
    import PySide6  # type: ignore
except Exception:  # pragma: no cover - provide stub for headless CI
    stub_pkg = types.ModuleType("PySide6")
    stub_pkg.__path__ = []  # type: ignore[attr-defined]
    stub_pkg.__all__ = ["QtCore", "QtWebEngineWidgets"]
    qtcore = _install_qtcore_stub()
    qtwe = _install_qtwe_stub()
    stub_pkg.QtCore = qtcore
    stub_pkg.QtWebEngineWidgets = qtwe
    sys.modules["PySide6"] = stub_pkg
else:  # pragma: no cover - augment incomplete Qt installs
    try:
        from PySide6 import QtCore  # type: ignore
    except Exception:
        PySide6.QtCore = _install_qtcore_stub()  # type: ignore[attr-defined]
    try:
        from PySide6 import QtWebEngineWidgets  # type: ignore
    except Exception:
        PySide6.QtWebEngineWidgets = _install_qtwe_stub()  # type: ignore[attr-defined]
