from typing import List

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QGridLayout, QLabel, QApplication
)

from modules.ui.app_state import AppState, ViewMode
from modules.ui.sidebar import Sidebar
from modules.services.browser_services import BrowserService, make_webview
from modules.services.local_app_service import LocalAppService, LocalAppWidget
from modules.utils.config_loader import Config, SourceSpec
from modules.utils.logger import get_logger


def _clear_layout(layout):
    """Alle Widgets aus einem Layout loesen, Parent NICHT loeschen."""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.setParent(None)


def _attach(widget: QWidget, host_layout):
    """Widget in Host Layout einhaengen und anzeigen."""
    widget.setParent(host_layout.parentWidget())
    host_layout.addWidget(widget)
    widget.show()


class MainWindow(QMainWindow):
    request_quit = Signal()

    def __init__(self, cfg: Config, state: AppState, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.state = state
        self.log = get_logger(__name__)
        self.setObjectName("MainWindow")

        # Quellen aus Config
        self.sources: List[SourceSpec] = cfg.sources[:] if cfg.sources else []
        self.num_sources = len(self.sources)
        self.current_page = 0      # fuer Quad Paging
        self.page_size = 4         # 2x2 pro Seite

        # Sidebar mit allen Namen
        titles = [s.name for s in self.sources]
        self.sidebar = Sidebar(
            titles=titles,
            width=cfg.ui.sidebar_width,
            orientation=cfg.ui.nav_orientation
        )
        self.sidebar.view_selected.connect(self.on_select_view)
        self.sidebar.toggle_mode.connect(self.on_toggle_mode)
        self.sidebar.page_changed.connect(self.on_page_changed)

        # Widgets fuer alle Quellen erzeugen
        self.source_widgets: List[QWidget] = []
        self.browser_services: List[BrowserService | None] = []
        self._create_source_widgets()

        # Single Host: genau ein aktives Widget
        self.single_host = QWidget(self)
        self.single_layout = QVBoxLayout(self.single_host)
        self.single_layout.setContentsMargins(0, 0, 0, 0)
        self.single_layout.setSpacing(0)

        # Quad Grid: dynamische Anordnung
        self.grid = QWidget(self)
        self.grid_layout = QGridLayout(self.grid)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(0)

        # Root Layout je nach Orientierung
        central = QWidget(self)
        if self.cfg.ui.nav_orientation == "top":
            root = QVBoxLayout(central)
        else:
            root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self.sidebar)

        # Modus Umschalter
        self.mode_stack = QStackedWidget(self)
        self.mode_stack.addWidget(self.single_host)  # 0 single
        self.mode_stack.addWidget(self.grid)         # 1 quad
        root.addWidget(self.mode_stack, 1)
        self.setCentralWidget(central)

        # Shortcuts
        for i in range(4):
            sc = QShortcut(QKeySequence(f"Ctrl+{i+1}"), self)
            sc.activated.connect(lambda idx=i: self._select_by_position(idx))
        QShortcut(QKeySequence("Ctrl+Right"), self).activated.connect(self.sidebar.next_page)
        QShortcut(QKeySequence("Ctrl+Left"), self).activated.connect(self.sidebar.prev_page)
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.on_toggle_mode)
        QShortcut(QKeySequence("F11"), self).activated.connect(self.toggle_kiosk)

        # Start Services
        self._start_services()

        # Startmodus anwenden und erste Auswahl setzen
        self.apply_mode(self.state.mode)
        initial_index = 0 if self.num_sources == 0 else min(self.state.active_index, self.num_sources - 1)
        self.on_select_view(initial_index)

        # Watchdog
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setInterval(5000)
        self.reconnect_timer.timeout.connect(self._tick_watchdogs)
        self.reconnect_timer.start()

    # -------- Widget Erstellung --------
    def _create_source_widgets(self):
        for s in self.sources:
            if s.type == "browser":
                view = make_webview()
                self.source_widgets.append(view)
                self.browser_services.append(BrowserService(view, s.url, name=f"Browser:{s.name}"))
            else:
                # Lokale App Widget
                w = LocalAppWidget(type("Tmp", (), {
                    "launch_cmd": s.launch_cmd,
                    "embed_mode": "native_window",
                    "window_title_pattern": s.window_title_pattern or ".*",
                    "web_url": None
                })())
                self.source_widgets.append(w)
                self.browser_services.append(None)

    # -------- Layout Umschaltungen --------
    def _attach_single(self, idx: int):
        """Aktives Widget in den Single Host haengen."""
        if not (0 <= idx < len(self.source_widgets)):
            return
        _clear_layout(self.single_layout)
        _attach(self.source_widgets[idx], self.single_layout)

    def _attach_quad_page(self, page: int):
        """Dynamische 2x2 Seite aufbauen. Weniger als 4 Fenster werden ohne Platzhalter angezeigt."""
        self.current_page = page
        # Grid leeren
        while self.grid_layout.count():
            it = self.grid_layout.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)

        start = page * self.page_size
        items: List[QWidget] = []
        for i in range(4):
            idx = start + i
            if idx < self.num_sources:
                items.append(self.source_widgets[idx])

        n = len(items)

        # alle Stretches zuruecksetzen
        for r in range(2):
            self.grid_layout.setRowStretch(r, 0)
        for c in range(2):
            self.grid_layout.setColumnStretch(c, 0)

        if n == 0:
            ph = QLabel("leer", self.grid)
            ph.setAlignment(Qt.AlignCenter)
            ph.setStyleSheet("background:#202020; color:#808080; border:1px solid #2a2a2a;")
            self.grid_layout.addWidget(ph, 0, 0, 1, 2)
            self.grid_layout.setRowStretch(0, 1)
            self.grid_layout.setColumnStretch(0, 1)
            self.grid_layout.setColumnStretch(1, 1)
            return

        if n == 1:
            self.grid_layout.addWidget(items[0], 0, 0, 2, 2)  # full area
            self.grid_layout.setRowStretch(0, 1)
            self.grid_layout.setRowStretch(1, 1)
            self.grid_layout.setColumnStretch(0, 1)
            self.grid_layout.setColumnStretch(1, 1)
            return

        if n == 2:
            # 1:1 nebeneinander
            self.grid_layout.addWidget(items[0], 0, 0, 2, 1)
            self.grid_layout.addWidget(items[1], 0, 1, 2, 1)
            self.grid_layout.setRowStretch(0, 1)
            self.grid_layout.setRowStretch(1, 1)
            self.grid_layout.setColumnStretch(0, 1)
            self.grid_layout.setColumnStretch(1, 1)
            return

        if n == 3:
            # oben 2, unten 1 ueber volle Breite
            self.grid_layout.addWidget(items[0], 0, 0, 1, 1)
            self.grid_layout.addWidget(items[1], 0, 1, 1, 1)
            self.grid_layout.addWidget(items[2], 1, 0, 1, 2)
            self.grid_layout.setRowStretch(0, 1)
            self.grid_layout.setRowStretch(1, 1)
            self.grid_layout.setColumnStretch(0, 1)
            self.grid_layout.setColumnStretch(1, 1)
            return

        # n >= 4: klassisch 2x2
        self.grid_layout.addWidget(items[0], 0, 0)
        self.grid_layout.addWidget(items[1], 0, 1)
        self.grid_layout.addWidget(items[2], 1, 0)
        self.grid_layout.addWidget(items[3], 1, 1)
        self.grid_layout.setRowStretch(0, 1)
        self.grid_layout.setRowStretch(1, 1)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)

    # -------- Slots --------
    def _select_by_position(self, pos: int):
        idx = self.current_page * self.page_size + pos
        if 0 <= idx < self.num_sources:
            self.on_select_view(idx)

    @Slot(int)
    def on_page_changed(self, page: int):
        if self.state.mode == ViewMode.QUAD:
            self._attach_quad_page(page)

    @Slot()
    def on_toggle_mode(self):
        self.state.toggle_mode()
        self.apply_mode(self.state.mode)

    def apply_mode(self, mode: ViewMode):
        if mode == ViewMode.SINGLE:
            self.mode_stack.setCurrentIndex(0)
            self._attach_single(self.state.active_index)
        else:
            self.mode_stack.setCurrentIndex(1)
            self._attach_quad_page(self.current_page)
        self.sidebar.set_active_global_index(self.state.active_index)

    @Slot(int)
    def on_select_view(self, idx: int):
        if not (0 <= idx < self.num_sources):
            return
        self.state.set_active(idx)
        if self.state.mode == ViewMode.SINGLE:
            self._attach_single(idx)
        # bei Quad bleibt seitenbasierte Darstellung bestehen
        self.sidebar.set_active_global_index(idx)

    # -------- Window mgmt --------
    def show_on_monitor(self, monitor_index: int):
        screens = QApplication.screens()
        idx = max(0, min(monitor_index, len(screens) - 1))
        geo = screens[idx].geometry()
        self.setGeometry(geo)

    def _start_services(self):
        # Browser starten
        for svc in self.browser_services:
            if svc is not None:
                svc.start()
        # Lokale starten
        for w in self.source_widgets:
            if isinstance(w, LocalAppWidget):
                w.start()

    def _tick_watchdogs(self):
        for svc in self.browser_services:
            if svc is not None:
                svc.heartbeat()
        for w in self.source_widgets:
            if isinstance(w, LocalAppWidget):
                w.heartbeat()

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
        # Schliessen nur mit Shift im Vollbild
        if self.isFullScreen():
            mods = QApplication.keyboardModifiers()
            if not mods & Qt.ShiftModifier:
                ev.ignore()
                return
        # Browser stoppen
        for svc in self.browser_services:
            if svc is not None:
                svc.stop()
        # Lokale stoppen
        for w in self.source_widgets:
            if isinstance(w, LocalAppWidget):
                w.stop()
        super().closeEvent(ev)
