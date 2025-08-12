from services.browser_service import BrowserService, make_webview
from PySide6.QtWebEngineWidgets import QWebEngineView

def test_webview_factory():
    v = make_webview()
    assert isinstance(v, QWebEngineView)
