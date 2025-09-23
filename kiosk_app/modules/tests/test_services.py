from services.browser_service import BrowserService, make_webview
from modules.qt import QtWebEngineWidgets

QWebEngineView = QtWebEngineWidgets.QWebEngineView

def test_webview_factory():
    v = make_webview()
    assert isinstance(v, QWebEngineView)
