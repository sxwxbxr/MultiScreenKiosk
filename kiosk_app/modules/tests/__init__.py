import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
base_str = str(BASE_DIR)
if base_str not in sys.path:
    sys.path.insert(0, base_str)

import types


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


def _dummy_signal_factory(*_args, **_kwargs):  # type: ignore
    return _DummySignal()


def _ensure_signal_aliases(module):
    if not hasattr(module, "pyqtSignal"):
        module.pyqtSignal = _dummy_signal_factory  # type: ignore[attr-defined]
    if not hasattr(module, "Signal"):
        module.Signal = _dummy_signal_factory  # type: ignore[attr-defined]
    return module


def _install_qtcore_stub():
    if "PyQt5.QtCore" in sys.modules:
        return _ensure_signal_aliases(sys.modules["PyQt5.QtCore"])

    qtcore = types.ModuleType("PyQt5.QtCore")

    class QObject:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            pass

    class QTimer:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            self.timeout = _dummy_signal_factory()
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

    qtcore.QObject = QObject
    qtcore.QTimer = QTimer
    qtcore.QUrl = QUrl
    qtcore.__package__ = "PyQt5"
    _ensure_signal_aliases(qtcore)
    sys.modules["PyQt5.QtCore"] = qtcore
    return qtcore


def _install_qtwe_stub():
    if "PyQt5.QtWebEngineWidgets" in sys.modules:
        return sys.modules["PyQt5.QtWebEngineWidgets"]

    qtwe = types.ModuleType("PyQt5.QtWebEngineWidgets")

    class QWebEngineView:  # type: ignore
        def __init__(self):
            core = _install_qtcore_stub()
            self.loadStarted = getattr(core, "Signal", _dummy_signal_factory)()
            self.loadFinished = getattr(core, "Signal", _dummy_signal_factory)()
            self._zoom = 1.0
            self._url = None

        def setZoomFactor(self, value):
            self._zoom = value

        def setUrl(self, url):
            self._url = url

        def reload(self):
            pass

    qtwe.QWebEngineView = QWebEngineView
    qtwe.__package__ = "PyQt5"
    sys.modules["PyQt5.QtWebEngineWidgets"] = qtwe
    return qtwe


try:
    import PyQt5  # type: ignore
except Exception:  # pragma: no cover - provide stub for headless CI
    stub_pkg = types.ModuleType("PyQt5")
    stub_pkg.__path__ = []  # type: ignore[attr-defined]
    stub_pkg.__all__ = ["QtCore", "QtWebEngineWidgets"]
    qtcore = _install_qtcore_stub()
    qtwe = _install_qtwe_stub()
    stub_pkg.QtCore = qtcore
    stub_pkg.QtWebEngineWidgets = qtwe
    sys.modules["PyQt5"] = stub_pkg
else:  # pragma: no cover - augment incomplete Qt installs
    try:
        from PyQt5 import QtCore  # type: ignore
    except Exception:
        PyQt5.QtCore = _install_qtcore_stub()  # type: ignore[attr-defined]
    try:
        from PyQt5 import QtWebEngineWidgets  # type: ignore
    except Exception:
        PyQt5.QtWebEngineWidgets = _install_qtwe_stub()  # type: ignore[attr-defined]
