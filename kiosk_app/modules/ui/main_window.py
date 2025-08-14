from typing import List
import re

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QGridLayout, QLabel, QApplication, QToolButton, QMenu, QMessageBox
)

from modules.ui.app_state import AppState, ViewMode
from modules.ui.sidebar import Sidebar
from modules.ui.settings_dialog import SettingsDialog
from modules.ui.browser_host import BrowserHostWidget
from modules.ui.log_viewer import LogViewer
from modules.services.browser_services import BrowserService, make_webview
from modules.services.local_app_service import LocalAppWidget
from modules.utils.config_loader import Config, SourceSpec, save_config
from modules.utils.logger import get_logger, get_log_path


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.setParent(None)

def _attach(widget: QWidget, host_layout):
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
        self.setWindowTitle("MultiScreen Kiosk")

        self._allow_close = False
        self._sidebar_collapsed = False

        self.sources: List[SourceSpec] = cfg.sources[:] if cfg.sources else []
        self.num_sources = len(self.sources)
        self.current_page = 0
        self.page_size = 4

        self.source_widgets: List[QWidget] = []
        self.browser_services: List[BrowserService | None] = []
        self._create_source_widgets()

        self.single_host = QWidget(self)
        self.single_layout = QVBoxLayout(self.single_host)
        self.single_layout.setContentsMargins(0, 0, 0, 0)
        self.single_layout.setSpacing(0)

        self.grid = QWidget(self)
        self.grid_layout = QGridLayout(self.grid)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(0)

        self.mode_stack = QStackedWidget(self)
        self.mode_stack.addWidget(self.single_host)
        self.mode_stack.addWidget(self.grid)

        self.overlay_burger = QToolButton()
        self.overlay_burger.setObjectName("OverlayBurger")
        self.overlay_burger.setText("☰")
        self.overlay_burger.setToolTip("Menue")
        self.overlay_burger.setCursor(Qt.PointingHandCursor)
        self.overlay_burger.setFixedSize(36, 36)
        self.overlay_burger.setVisible(False)
        self.overlay_burger.clicked.connect(self._open_overlay_menu)

        self._build_root_and_sidebar()
        self.apply_theme(self.cfg.ui.theme)

        for i in range(4):
            sc = QShortcut(QKeySequence(f"Ctrl+{i+1}"), self)
            sc.activated.connect(lambda idx=i: self._select_by_position(idx))
        QShortcut(QKeySequence("Ctrl+Right"), self).activated.connect(lambda: self._page_delta(+1))
        QShortcut(QKeySequence("Ctrl+Left"), self).activated.connect(lambda: self._page_delta(-1))
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.on_toggle_mode)
        QShortcut(QKeySequence("F11"), self).activated.connect(self.toggle_kiosk)

        self._start_services()

        self.apply_mode(self.state.mode)
        self.on_select_view(0 if self.num_sources == 0 else min(self.state.active_index, self.num_sources - 1))

        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setInterval(5000)
        self.reconnect_timer.timeout.connect(self._tick_watchdogs)
        self.reconnect_timer.start()

    # ---------- Root und Sidebar ----------
    def _build_root_and_sidebar(self):
        titles = [s.name for s in self.sources]

        old = self.centralWidget()
        if old:
            old.deleteLater()

        central = QWidget(self)
        if self.cfg.ui.nav_orientation == "top":
            root = QVBoxLayout(central)
        else:
            root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(
            titles=titles,
            width=self.cfg.ui.sidebar_width,
            orientation=self.cfg.ui.nav_orientation,
            enable_hamburger=self.cfg.ui.enable_hamburger,
            logo_path=self.cfg.ui.logo_path
        )
        self.sidebar.view_selected.connect(self.on_select_view)
        self.sidebar.toggle_mode.connect(self.on_toggle_mode)
        self.sidebar.page_changed.connect(self.on_page_changed)
        self.sidebar.request_settings.connect(self.open_settings)
        self.sidebar.collapsed_changed.connect(self.on_sidebar_collapsed_changed)

        root.addWidget(self.sidebar)
        root.addWidget(self.mode_stack, 1)
        self.setCentralWidget(central)

        self.overlay_burger.setParent(central)
        self.overlay_burger.raise_()
        self._place_overlay_burger()
        self._refresh_overlay_visibility()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._place_overlay_burger()

    def _place_overlay_burger(self):
        margin = 12
        cw = self.centralWidget()
        if not cw:
            return
        self.overlay_burger.move(margin, margin)
        self.overlay_burger.raise_()

    def _refresh_overlay_visibility(self):
        self.overlay_burger.setVisible(self._sidebar_collapsed and self.cfg.ui.enable_hamburger)

    def on_sidebar_collapsed_changed(self, collapsed: bool):
        self.set_sidebar_collapsed(collapsed)

    def set_sidebar_collapsed(self, collapsed: bool):
        self._sidebar_collapsed = bool(collapsed)
        if self.sidebar:
            try:
                self.sidebar.set_collapsed(collapsed)
            except Exception:
                pass
            self.sidebar.setVisible(not collapsed)
            self.sidebar.updateGeometry()
            cw = self.centralWidget()
            if cw and cw.layout():
                cw.layout().invalidate()
                cw.layout().activate()
        self._refresh_overlay_visibility()
        self._place_overlay_burger()

    def _open_overlay_menu(self):
        m = QMenu(self)
        for idx, title in enumerate([s.name for s in self.sources]):
            act = m.addAction(title)
            act.triggered.connect(lambda _=False, i=idx: self.on_select_view(i))
        m.addSeparator()
        m.addAction("Leiste anzeigen").triggered.connect(lambda: self.set_sidebar_collapsed(False))
        m.addAction("Switch").triggered.connect(self.on_toggle_mode)
        m.addAction("Einstellungen").triggered.connect(self.open_settings)
        m.addAction("Logs").triggered.connect(self.open_log_viewer)
        m.addAction("Log Statistik").triggered.connect(self._show_log_stats)
        m.addSeparator()
        m.addAction("Beenden").triggered.connect(self._confirm_and_quit)
        pos = self.overlay_burger.mapToGlobal(self.overlay_burger.rect().bottomLeft())
        m.exec(pos)

    # ---------- Erstellung der Quellenwidgets ----------
    def _create_source_widgets(self):
        self.source_widgets.clear()
        self.browser_services.clear()
        for s in self.sources:
            if s.type == "browser":
                view = make_webview()
                host = BrowserHostWidget(
                    placeholder_enabled=self.cfg.ui.placeholder_enabled,
                    gif_path=self.cfg.ui.placeholder_gif_path
                )
                host.set_view(view)
                if self.cfg.ui.placeholder_enabled:
                    host.show_placeholder()
                self.source_widgets.append(host)

                svc = BrowserService(view, s.url, name=f"Browser:{s.name}")
                svc.page_loading.connect(host.show_placeholder)
                svc.page_ready.connect(host.show_view)
                svc.page_error.connect(lambda _msg, h=host: h.show_placeholder())
                self.browser_services.append(svc)
            else:
                # Uebrige Quellen werden als lokale Anwendungen behandelt
                w = LocalAppWidget(s)
                self.source_widgets.append(w)
                self.browser_services.append(None)

    # ---------- Layout Umschaltungen ----------
    def _attach_single(self, idx: int):
        if not (0 <= idx < len(self.source_widgets)):
            return
        _clear_layout(self.single_layout)
        _attach(self.source_widgets[idx], self.single_layout)

    def _attach_quad_page(self, page: int):
        self.current_page = page
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

        for r in range(2):
            self.grid_layout.setRowStretch(r, 0)
        for c in range(2):
            self.grid_layout.setColumnStretch(c, 0)

        if n == 0:
            ph = QLabel("leer", self.grid)
            ph.setAlignment(Qt.AlignCenter)
            ph.setStyleSheet("background:rgba(120,120,120,0.1); color:#808080; border:1px solid rgba(255,255,255,0.06);")
            self.grid_layout.addWidget(ph, 0, 0, 1, 2)
            self.grid_layout.setRowStretch(0, 1)
            self.grid_layout.setColumnStretch(0, 1)
            self.grid_layout.setColumnStretch(1, 1)
            return

        if n == 1:
            self.grid_layout.addWidget(items[0], 0, 0, 2, 2)
        elif n == 2:
            self.grid_layout.addWidget(items[0], 0, 0, 2, 1)
            self.grid_layout.addWidget(items[1], 0, 1, 2, 1)
        elif n == 3:
            self.grid_layout.addWidget(items[0], 0, 0, 1, 1)
            self.grid_layout.addWidget(items[1], 0, 1, 1, 1)
            self.grid_layout.addWidget(items[2], 1, 0, 1, 2)
        else:
            self.grid_layout.addWidget(items[0], 0, 0)
            self.grid_layout.addWidget(items[1], 0, 1)
            self.grid_layout.addWidget(items[2], 1, 0)
            self.grid_layout.addWidget(items[3], 1, 1)

        self.grid_layout.setRowStretch(0, 1)
        self.grid_layout.setRowStretch(1, 1)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)

    # ---------- Einstellungen ----------
    def open_settings(self):
        dlg = SettingsDialog(
            nav_orientation=self.cfg.ui.nav_orientation,
            enable_hamburger=self.cfg.ui.enable_hamburger,
            placeholder_enabled=self.cfg.ui.placeholder_enabled,
            placeholder_gif_path=self.cfg.ui.placeholder_gif_path,
            theme=self.cfg.ui.theme,
            logo_path=self.cfg.ui.logo_path,
            parent=self
        )
        if dlg.exec():
            res = dlg.results()

            if res.get("quit_requested"):
                self._confirm_and_quit()
                return

            self.cfg.ui.theme = res["theme"]
            self.cfg.ui.nav_orientation = res["nav_orientation"]
            self.cfg.ui.enable_hamburger = res["enable_hamburger"]
            self.cfg.ui.placeholder_enabled = res["placeholder_enabled"]
            self.cfg.ui.placeholder_gif_path = res["placeholder_gif_path"]
            self.cfg.ui.logo_path = res["logo_path"]

            self.apply_theme(self.cfg.ui.theme)
            self._build_root_and_sidebar()
            if not self.cfg.ui.enable_hamburger:
                self.set_sidebar_collapsed(False)

            for w in self.source_widgets:
                if isinstance(w, BrowserHostWidget):
                    w.set_placeholder_enabled(self.cfg.ui.placeholder_enabled)
                    w.set_placeholder_gif(self.cfg.ui.placeholder_gif_path)
                    if not self.cfg.ui.placeholder_enabled:
                        w.show_view()

            self.sidebar.set_titles([s.name for s in self.sources])
            self.sidebar.set_active_global_index(self.state.active_index)

            try:
                save_config(self.cfg)  # Standardpfad modules/config.json
            except Exception:
                pass

    def open_log_viewer(self):
        dlg = LogViewer(self)
        dlg.setModal(False)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.show()

    def _show_log_stats(self):
        path = get_log_path()
        lvl_re = re.compile(r"\b(DEBUG|INFO|WARNING|ERROR)\b")
        json_re = re.compile(r'"level"\s*:\s*"(DEBUG|INFO|WARNING|ERROR)"', re.IGNORECASE)

        info = warn = err = dbg = 0
        total_lines = 0
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    total_lines += 1
                    m = lvl_re.search(line)
                    if not m:
                        m = json_re.search(line)
                    if not m:
                        continue
                    lv = m.group(1).upper()
                    if lv == "DEBUG":
                        dbg += 1
                    elif lv == "INFO":
                        info += 1
                    elif lv == "WARNING":
                        warn += 1
                    elif lv == "ERROR":
                        err += 1
        except FileNotFoundError:
            QMessageBox.information(self, "Log Statistik", "Keine Logdatei gefunden.")
            return
        except Exception as ex:
            QMessageBox.warning(self, "Log Statistik", f"Fehler beim Lesen der Logdatei:\n{ex}")
            return

        QMessageBox.information(
            self,
            "Log Statistik",
            f"Datei: {path}\n\n"
            f"Zeilen gesamt: {total_lines}\n"
            f"Info:   {info}\n"
            f"Warn:   {warn}\n"
            f"Error:  {err}\n"
            f"Debug:  {dbg}"
        )

    # ---------- Theme ----------
    def apply_theme(self, theme: str):
        if theme == "light":
            base = """
                QWidget { background: #fbfbfd; color: #1c1c1e; font-size: 13px; }
                QLabel { color: #1c1c1e; }
                QToolButton, QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f2f2f7);
                    border: 1px solid #e5e5ea; border-radius: 10px; padding: 8px 12px;
                }
                QToolButton:hover, QPushButton:hover { border-color: #d1d1d6; }
                QToolButton:pressed, QPushButton:pressed { background: #e5e5ea; }
                QLineEdit { background: #ffffff; border:1px solid #e5e5ea; border-radius: 8px; padding:6px 8px; }
                QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border:1px solid #d1d1d6; background:#fff; }
                QCheckBox::indicator:checked { background:#0a84ff; border:1px solid #0a84ff; }
                #OverlayBurger {
                    background: rgba(255,255,255,0.80);
                    border: 1px solid rgba(0,0,0,0.12);
                    border-radius: 8px; padding: 0;
                    font-size: 18px; min-width: 36px; min-height: 36px;
                }
                #OverlayBurger:hover { background: rgba(255,255,255,0.95); }
                #OverlayBurger:pressed { background: rgba(235,235,235,1.0); }
            """
        else:
            base = """
                QWidget { background: #0f1115; color: #e5e7eb; font-size: 13px; }
                QLabel { color: #e5e7eb; }
                QToolButton, QPushButton {
                    background: #171a21; border: 1px solid #262b36; border-radius: 10px; padding: 8px 12px;
                }
                QToolButton:hover, QPushButton:hover { border-color: #31384a; }
                QToolButton:pressed, QPushButton:pressed { background: #212633; }
                QLineEdit { background: #12151c; border:1px solid #262b36; border-radius: 8px; padding:6px 8px; }
                QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border:1px solid #3a4254; background:#141823; }
                QCheckBox::indicator:checked { background:#3b82f6; border:1px solid #3b82f6; }
                #OverlayBurger {
                    background: rgba(20,22,28,0.92);
                    border: 1px solid rgba(255,255,255,0.10);
                    border-radius: 8px; padding: 0;
                    font-size: 18px; min-width: 36px; min-height: 36px;
                }
                #OverlayBurger:hover { background: rgba(26,29,36,0.98); }
                #OverlayBurger:pressed { background: rgba(33,38,51,1.0); }
            """
        self.setStyleSheet(base)

    # ---------- Paging Helfer ----------
    def _page_delta(self, delta: int):
        if self.sidebar and self.sidebar.isVisible():
            if delta > 0:
                self.sidebar.next_page()
            else:
                self.sidebar.prev_page()
        else:
            max_page = max(0, (self.num_sources - 1) // self.page_size)
            new_page = max(0, min(max_page, self.current_page + delta))
            if new_page != self.current_page:
                self.current_page = new_page
                if self.state.mode == ViewMode.QUAD:
                    self._attach_quad_page(self.current_page)

    # ---------- Slots ----------
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
        if self.sidebar and self.sidebar.isVisible():
            self.sidebar.set_active_global_index(self.state.active_index)

    @Slot(int)
    def on_select_view(self, idx: int):
        if not (0 <= idx < self.num_sources):
            return
        self.state.set_active(idx)
        if self.state.mode == ViewMode.SINGLE:
            self._attach_single(idx)
        if self.sidebar and self.sidebar.isVisible():
            self.sidebar.set_active_global_index(idx)

    # ---------- Window mgmt ----------
    def show_on_monitor(self, monitor_index: int):
        screens = QApplication.screens()
        idx = max(0, min(monitor_index, len(screens) - 1))
        geo = screens[idx].geometry()
        self.setGeometry(geo)

    def _start_services(self):
        for svc in self.browser_services:
            if svc is not None:
                svc.start()
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

    def _confirm_and_quit(self):
        ans = QMessageBox.question(
            self, "Beenden",
            "Kiosk wirklich beenden?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if ans == QMessageBox.Yes:
            self._allow_close = True
            QApplication.instance().quit()

    def closeEvent(self, ev):
        if self.isFullScreen() and not self._allow_close:
            mods = QApplication.keyboardModifiers()
            if not mods & Qt.ShiftModifier:
                ev.ignore()
                return
        for svc in self.browser_services:
            if svc is not None:
                try:
                    svc.stop()
                except Exception:
                    pass
        for w in self.source_widgets:
            if isinstance(w, LocalAppWidget):
                try:
                    w.stop()
                except Exception:
                    pass
        super().closeEvent(ev)
