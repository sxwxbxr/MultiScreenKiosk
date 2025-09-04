"""Backward compatible import wrapper.

Historically the browser service module was named ``browser_service``.
The project has since been refactored to ``browser_services`` but parts of
both the code base and external plugins may still import the old name.  This
module re-exports the public API from :mod:`browser_services`.
"""

from .browser_services import BrowserService, make_webview

__all__ = ["BrowserService", "make_webview"]
