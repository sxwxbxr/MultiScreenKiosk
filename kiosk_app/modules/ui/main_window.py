from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QGridLayout, QApplication
)

from modules.ui.app_state import AppState, ViewMode
from modules.ui.sidebar import Sidebar
from modules.services.browser_services import BrowserService, make_webview
from modules.services.local_app_service import LocalAppService, LocalAppWidget
from modules.utils.config_loader import Config
from modules.utils.logger import get_logger


class MainWindow(QMainWindow):
    request_quit = Signal()

    def __init__(self, cfg: Config, state: AppState, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.state = state
        self.log = get_logger(__name__)
        self.setObjectName("MainWindow")

        # Sidebar Titel aus Config
        self.sidebar = Sidebar(
            titles=self.cfg.ui.sidebar_titles,
            width=cfg.ui.sidebar_width
        )
        self.sidebar.view_selected.connect(self.on_select_view)
        self.sidebar.toggle_mode.connect(self.on_toggle_mode)

        # Webviews
        self.web_single = [make_webview() for _ in range(3)]
        self.web_quad = [make_webview() for _ in range(3)]

        self.browser_services_single = [
            BrowserService(self.web_single[i], cfg.browser_urls[i], name=f"BrowserA{i}") for i in range(3)
        ]
        self.browser_services_quad = [
            BrowserService(self.web_quad[i], cfg.browser_urls[i], name=f"BrowserQ{i}") for i in range(3)
        ]

        # Lokale App Hosts
        self.local_single = LocalAppWidget(cfg.local_app)
        self.local_quad = LocalAppWidget(cfg.local_app)

        # Ein gemeinsamer LocalAppService
        self.local_shared_service = self.local_single.service
        self.local_quad.service.stop()
        self.local_quad.service = self.local_shared_service

        # Single Stack
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.web_single[0])
        self.stack.addWidget(self.web_single[1])
        self.stack.addWidget(self.web_single[2])
        self.stack.addWidget(self.local_single)

        # Quad Grid
        self.grid = QWidget(self)
        gl = QGridLayout(self.grid)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(0)
        gl.addWidget(self.web_quad[0], 0, 0)
        gl.addWidget(self.web_quad[1], 0, 1)
        gl.addWidget(self.web_quad[2], 1, 0)
        gl.addWidget(self.local_quad, 1, 1)

        # Root Layout
        central = QWidget(self)
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self.sidebar)
        self.mode_stack = QStackedWidget(self)
        self.mode_stack.addWidget(self.stack)   # 0 single
        self.mode_stack.addWidget(self.grid)    # 1 quad
        h.addWidget(self.mode_stack, 1)
        self.setCentralWidget(central)

        # Shortcuts
        for i in range(4):
            sc = QShortcut(QKeySequence(f"Ctrl+{i+1}"), self)
            sc.activated.connect(lambda idx=i: self.on_select_view(idx))
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.on_toggle_mode)
        QShortcut(QKeySequence("F11"), self).activated.connect(self.toggle_kiosk)

        # Start
        self._start_services()
        self.apply_mode(self.state.mode)
        self.on_select_view(self.state.active_index)

        # Watchdog
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setInterval(5000)
        self.reconnect_timer.timeout.connect(self._tick_watchdogs)
        self.reconnect_timer.start()

    def show_on_monitor(self, monitor_index: int):
        screens = QApplication.screens()
        idx = max(0, min(monitor_index, len(screens) - 1))
        geo = screens[idx].geometry()
        self.setGeometry(geo)

    def _start_services(self):
        for s in self.browser_services_single + self.browser_services_quad:
            s.start()
        self.local_single.start()  # shared service, daher nur einmal starten

    @Slot()
    def on_toggle_mode(self):
        self.state.toggle_mode()
        self.apply_mode(self.state.mode)

    def apply_mode(self, mode: ViewMode):
        self.mode_stack.setCurrentIndex(0 if mode == ViewMode.SINGLE else 1)
        host = self.local_single if mode == ViewMode.SINGLE else self.local_quad
        try:
            self.local_shared_service.rebind_host(host)
        except Exception as e:
            self.log.warning("Rebind Host fehlgeschlagen: %s", e)
        self.sidebar.set_active(self.state.active_index)

    @Slot(int)
    def on_select_view(self, idx: int):
        self.state.set_active(idx)
        self.stack.setCurrentIndex(idx)
        self.sidebar.set_active(idx)

    def enter_kiosk(self):
        self.showFullScreen()

    def leave_kiosk(self):
        self.showNormal()

    def toggle_kiosk(self):
        if self.isFullScreen():
            self.leave_kiosk()
        else:
            self.enter_kiosk()

    def closeEvent(self, ev):
        if self.isFullScreen():
            mods = QApplication.keyboardModifiers()
            if not mods & Qt.ShiftModifier:
                ev.ignore()
                return
        for s in self.browser_services_single + self.browser_services_quad:
            s.stop()
        self.local_shared_service.stop()
        super().closeEvent(ev)

    def _tick_watchdogs(self):
        for s in self.browser_services_single + self.browser_services_quad:
            s.heartbeat()
        self.local_shared_service.heartbeat()
