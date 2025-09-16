from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import List, Optional

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
from modules.ui.window_spy import WindowSpyDialog
from modules.services.auto_update import AutoUpdateService, UpdateResult
from modules.services.browser_services import BrowserService, make_webview
from modules.services.local_app_service import LocalAppWidget
from modules.utils.config_loader import Config, SourceSpec, save_config, load_config, DEFAULT_SHORTCUTS
from modules.utils.logger import get_logger, init_logging
from modules.utils.i18n import tr, i18n
from modules.version import __version__


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

    def __init__(self, cfg: Config, state: AppState, config_path: Path | None = None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.state = state
        self.log = get_logger(__name__)
        self.setObjectName("MainWindow")
        self._auto_update_service: Optional[AutoUpdateService] = None

        if config_path is not None:
            self.cfg_path = Path(config_path).resolve()
        else:
            self.cfg_path = Path(__file__).resolve().parent / "config.json"

        # Programmgesteuerter Quit Flag fuer closeEvent
        self._programmatic_quit = False

        # Quellen
        self.sources: List[SourceSpec] = cfg.sources[:] if cfg.sources else []
        self.num_sources = len(self.sources)
        self.current_page = 0
        self.page_size = 4
        if not self.cfg.ui.split_enabled:
            self.state.start_mode = "single"

        # Widgets fuer Quellen
        self.source_widgets: List[QWidget] = []
        self.browser_services: List[BrowserService | None] = []
        self._create_source_widgets()

        # Container
        self.single_host = QWidget(self)
        self.single_layout = QVBoxLayout(self.single_host)
        self.single_layout.setContentsMargins(0, 0, 0, 0)
        self.single_layout.setSpacing(0)

        self.grid = QWidget(self)
        self.grid_layout = QGridLayout(self.grid)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(0)

        self.mode_stack = QStackedWidget(self)
        self.mode_stack.addWidget(self.single_host)  # 0
        self.mode_stack.addWidget(self.grid)         # 1

        # Overlay Burger
        self.overlay_burger = QToolButton(self)
        self.overlay_burger.setText("☰")
        self.overlay_burger.setToolTip("")
        self.overlay_burger.setVisible(False)
        self.overlay_burger.clicked.connect(self._open_overlay_menu)

        # Root und Sidebar
        self._build_root_and_sidebar()

        # Theme
        self.apply_theme(self.cfg.ui.theme)
        i18n.language_changed.connect(lambda _l: self.retranslate_ui())
        self.retranslate_ui()

        # Shortcuts
        self._setup_shortcuts()

        # Services
        self._start_services()

        # Startmodus
        self.apply_mode(self.state.mode)
        self.on_select_view(0 if self.num_sources == 0 else min(self.state.active_index, self.num_sources - 1))

        # Watchdog
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setInterval(5000)
        self.reconnect_timer.timeout.connect(self._tick_watchdogs)
        self.reconnect_timer.start()

        # Auto-Update nach dem Start im Hintergrund pruefen
        self._maybe_start_auto_update()

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
            logo_path=self.cfg.ui.logo_path,
            split_enabled=self.cfg.ui.split_enabled
        )
        self.sidebar.view_selected.connect(self.on_select_view)
        self.sidebar.toggle_mode.connect(self.on_toggle_mode)
        self.sidebar.page_changed.connect(self.on_page_changed)
        self.sidebar.request_settings.connect(self.open_settings)
        self.sidebar.collapsed_changed.connect(self.on_sidebar_collapsed_changed)

        root.addWidget(self.sidebar)
        root.addWidget(self.mode_stack, 1)
        self.setCentralWidget(central)

        self._place_overlay_burger()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._place_overlay_burger()

    def _place_overlay_burger(self):
        margin = 8
        self.overlay_burger.move(margin, margin)
        self.overlay_burger.raise_()

    def on_sidebar_collapsed_changed(self, collapsed: bool):
        self.set_sidebar_collapsed(collapsed)

    def set_sidebar_collapsed(self, collapsed: bool):
        """Sidebar wirklich ein bzw. ausklappen und Layout refreshen."""
        if self.sidebar:
            self.sidebar.set_collapsed(collapsed)          # interner Zustand
            self.sidebar.setVisible(not collapsed)         # Widget sichtbar
            self.sidebar.updateGeometry()
            cw = self.centralWidget()
            if cw and cw.layout():
                cw.layout().invalidate()
                cw.layout().activate()
        self.overlay_burger.setVisible(collapsed)
        self._place_overlay_burger()

    def _open_overlay_menu(self):
        m = QMenu(self)
        for idx, title in enumerate([s.name for s in self.sources]):
            act = m.addAction(title)
            act.triggered.connect(lambda _=False, i=idx: self.on_select_view(i))
        m.addSeparator()
        act_show = m.addAction(tr("Show bar"))
        act_show.triggered.connect(lambda: self.set_sidebar_collapsed(False))
        if self.cfg.ui.split_enabled:
            act_switch = m.addAction(tr("Switch"))
            act_switch.triggered.connect(self.on_toggle_mode)
        act_settings = m.addAction(tr("Settings"))
        act_settings.triggered.connect(self.open_settings)
        pos = self.overlay_burger.mapToGlobal(self.overlay_burger.rect().bottomLeft())
        m.exec(pos)

    def _nudge_local_apps(self):
    # nur sichtbare Widgets der aktuellen Ansicht anstossen
        visible_widgets = []
        if self.state.mode == ViewMode.SINGLE:
            idx = self.state.active_index
            if 0 <= idx < len(self.source_widgets):
                visible_widgets.append(self.source_widgets[idx])
        else:
            # Quad Seite
            start = self.current_page * self.page_size
            for i in range(4):
                j = start + i
                if 0 <= j < len(self.source_widgets):
                    visible_widgets.append(self.source_widgets[j])

        for w in visible_widgets:
            if isinstance(w, LocalAppWidget):
                w.force_fit()


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
                # Lokale App Dummy Spec mit allen Feldern
                dummy_spec = type("Tmp", (), {
                    "launch_cmd": s.launch_cmd,
                    "args": getattr(s, "args", "") or "",
                    "embed_mode": "native_window",
                    "window_title_pattern": s.window_title_pattern or ".*",
                    "window_class_pattern": getattr(s, "window_class_pattern", "") or "",
                    "follow_children": bool(getattr(s, "follow_children", True)),
                    "web_url": None
                })()
                w = LocalAppWidget(dummy_spec)
                self.source_widgets.append(w)
                self.browser_services.append(None)

    def _cleanup_sources(self):
        for svc in getattr(self, "browser_services", []):
            if svc is not None:
                try:
                    svc.stop()
                except Exception:
                    pass
        for w in getattr(self, "source_widgets", []):
            try:
                if isinstance(w, LocalAppWidget):
                    w.stop()
            except Exception:
                pass
            try:
                w.setParent(None)
            except Exception:
                pass
            try:
                w.deleteLater()
            except Exception:
                pass
        if hasattr(self, "single_layout"):
            _clear_layout(self.single_layout)
        if hasattr(self, "grid_layout"):
            while self.grid_layout.count():
                it = self.grid_layout.takeAt(0)
                w = it.widget()
                if w:
                    w.setParent(None)
        self.source_widgets = []
        self.browser_services = []

    def _apply_config_object(self, cfg: Config):
        self.cfg = cfg
        self.sources = cfg.sources[:] if cfg.sources else []
        self.num_sources = len(self.sources)
        self.current_page = 0
        self.state.set_active(0 if self.num_sources else 0)

        start_mode = getattr(cfg.ui, "start_mode", "single") or "single"
        if start_mode not in ("single", "quad"):
            start_mode = "single"
        if not cfg.ui.split_enabled:
            start_mode = "single"
        self.state.start_mode = start_mode

        self._create_source_widgets()
        self._build_root_and_sidebar()
        self.apply_theme(cfg.ui.theme)
        try:
            i18n.set_language(cfg.ui.language or i18n.get_language())
        except Exception:
            pass

        if not cfg.ui.enable_hamburger:
            self.set_sidebar_collapsed(False)
        else:
            self._place_overlay_burger()

        if getattr(self, "sidebar", None):
            try:
                self.sidebar.set_titles([s.name for s in self.sources])
                self.sidebar.set_active_global_index(self.state.active_index)
            except Exception:
                pass

        self._setup_shortcuts()
        self.apply_mode(self.state.mode)
        if self.num_sources:
            self.on_select_view(min(self.state.active_index, self.num_sources - 1))
        self._start_services()

    def _backup_config(self, target_path: Path) -> None:
        path = Path(target_path).resolve()
        self.log.info("export config to %s", path, extra={"source": "config"})
        save_config(path, self.cfg)

    def _restore_config(self, source_path: Path) -> Config:
        path = Path(source_path).resolve()
        if not path.exists():
            raise ValueError(tr("Selected file is not a valid configuration."))
        try:
            with path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as ex:
            raise ValueError(tr("Selected file is not a valid configuration.")) from ex

        if not isinstance(raw, dict):
            raise ValueError(tr("Selected file is not a valid configuration."))

        has_sources = bool(raw.get("sources"))
        has_browser = bool(raw.get("browser_urls"))
        has_local = bool(raw.get("local_app"))
        has_count = False
        try:
            has_count = int(raw.get("count", 0)) > 0
        except Exception:
            has_count = False

        if not (has_sources or has_browser or has_local or has_count):
            raise ValueError(tr("Configuration must define at least one source."))

        cfg = load_config(path)
        if not cfg.sources:
            raise ValueError(tr("Configuration must define at least one source."))
        return cfg

    def _apply_restored_config(self, cfg: Config):
        old_cfg = copy.deepcopy(self.cfg)
        try:
            self._cleanup_sources()
            self._apply_config_object(cfg)
        except Exception as ex:
            self.log.error("failed to apply restored config: %s", ex, extra={"source": "config"})
            try:
                self._cleanup_sources()
                self._apply_config_object(old_cfg)
            except Exception:
                self.log.exception("failed to rollback UI after restore error", extra={"source": "config"})
            raise

        try:
            save_config(self.cfg_path, cfg)
        except Exception as ex:
            self.log.error("failed to persist restored config: %s", ex, extra={"source": "config"})
            try:
                save_config(self.cfg_path, old_cfg)
            except Exception:
                self.log.exception("failed to rollback config file after restore error", extra={"source": "config"})
            try:
                self._cleanup_sources()
                self._apply_config_object(old_cfg)
            except Exception:
                self.log.exception("failed to rollback UI after persistence error", extra={"source": "config"})
            raise


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
            ph.setStyleSheet("background:#202020; color:#808080; border:1px solid #2a2a2a;")
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
        logging_cfg = getattr(self.cfg, "logging", None)
        dlg = SettingsDialog(
            nav_orientation=self.cfg.ui.nav_orientation,
            enable_hamburger=self.cfg.ui.enable_hamburger,
            placeholder_enabled=self.cfg.ui.placeholder_enabled,
            placeholder_gif_path=self.cfg.ui.placeholder_gif_path,
            theme=self.cfg.ui.theme,
            logo_path=self.cfg.ui.logo_path,
            split_enabled=self.cfg.ui.split_enabled,
            shortcuts=self.cfg.ui.shortcuts,
            remote_export=logging_cfg.remote_export if logging_cfg else None,
            backup_handler=self._backup_config,
            restore_handler=self._restore_config,
            parent=self
        )
        if dlg.exec():
            res = dlg.results()

            restored_cfg = res.get("restored_config")
            if restored_cfg:
                try:
                    self._apply_restored_config(restored_cfg)
                    self.log.info(
                        "config restored",
                        extra={"source": "config", "path": res.get("restored_from")}
                    )
                except Exception as ex:
                    QMessageBox.critical(self, tr("Restore config"), tr("Restore failed: {ex}", ex=ex))
                return

            # Beenden gewuenscht
            if res.get("quit_requested"):
                # programmgesteuerter Quit erlaubt das Schliessen trotz Fullscreen
                self._programmatic_quit = True
                if self.isFullScreen():
                    self.leave_kiosk()
                # leicht verzoegert schliessen, damit der Dialog sauber weg ist
                QTimer.singleShot(0, self.close)
                return

            self.cfg.ui.theme = res["theme"]
            self.cfg.ui.nav_orientation = res["nav_orientation"]
            self.cfg.ui.enable_hamburger = res["enable_hamburger"]
            self.cfg.ui.placeholder_enabled = res["placeholder_enabled"]
            self.cfg.ui.placeholder_gif_path = res["placeholder_gif_path"]
            self.cfg.ui.language = res["language"]
            self.cfg.ui.logo_path = res["logo_path"]
            self.cfg.ui.shortcuts = res.get("shortcuts", self.cfg.ui.shortcuts)

            remote_export_res = res.get("remote_export")
            if remote_export_res is not None and logging_cfg is not None:
                logging_cfg.remote_export = remote_export_res
                try:
                    init_logging(logging_cfg)
                except Exception as ex:
                    self.log.error(
                        "failed to apply updated logging configuration: %s",
                        ex,
                        extra={"source": "logging"},
                    )

            # Anwenden
            self.apply_theme(self.cfg.ui.theme)
            i18n.set_language(self.cfg.ui.language)
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

            self._setup_shortcuts()

            try:
                save_config(self.cfg_path, self.cfg)
            except Exception as ex:
                self.log.error("failed to persist config update: %s", ex, extra={"source": "config"})

    def _setup_shortcuts(self):
        # vorhandene Shortcuts entfernen
        for sc in getattr(self, "_shortcuts", {}).values():
            try:
                sc.setParent(None)
            except Exception:
                pass
        self._shortcuts = {}

        mapping = DEFAULT_SHORTCUTS.copy()
        try:
            mapping.update({k: v for k, v in self.cfg.ui.shortcuts.items() if v})
        except Exception:
            pass

        def _add(action: str, seq: str | None, handler):
            if not seq:
                return
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(handler)
            self._shortcuts[action] = sc

        for i in range(4):
            _add(f"select_{i+1}", mapping.get(f"select_{i+1}"), lambda i=i: self._select_by_position(i))
        _add("next_page", mapping.get("next_page"), lambda: self._page_delta(+1))
        _add("prev_page", mapping.get("prev_page"), lambda: self._page_delta(-1))
        if self.cfg.ui.split_enabled:
            _add("toggle_mode", mapping.get("toggle_mode"), self.on_toggle_mode)
        _add("toggle_kiosk", mapping.get("toggle_kiosk"), self.toggle_kiosk)

    def retranslate_ui(self):
        self.overlay_burger.setToolTip(tr("Menu"))
        if getattr(self, "sidebar", None):
            try:
                self.sidebar.retranslate_ui()
            except Exception:
                pass

    def apply_theme(self, theme: str):
        if theme == "light":
            self.setStyleSheet("""
                QWidget { background: #f4f4f4; color: #202020; }
                QToolButton, QPushButton { background: #ffffff; border: 1px solid #d0d0d0; padding: 6px; }
                QLineEdit { background: #ffffff; border: 1px solid #d0d0d0; padding: 4px; }
                QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #999; background: #fff; }
                QCheckBox::indicator:checked { background: #0078d4; image: none; }
            """)
        else:
            self.setStyleSheet("""
                QWidget { background: #121212; color: #e0e0e0; }
                QToolButton, QPushButton { background: #1f1f1f; border: 1px solid #2a2a2a; padding: 6px; }
                QLineEdit { background: #1b1b1b; border: 1px solid #2a2a2a; padding: 4px; }
                QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #5a5a5a; background: #2a2a2a; }
                QCheckBox::indicator:checked { background: #3b82f6; image: none; border: 1px solid #3b82f6; }
            """)

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
            # Nach Seitenwechsel hart nachskalieren
            self._nudge_local_apps()

    @Slot()
    def on_toggle_mode(self):
        if not self.cfg.ui.split_enabled:
            return
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
        self._nudge_local_apps()

    @Slot(int)
    def on_select_view(self, idx: int):
        if not (0 <= idx < self.num_sources):
            return
        self.state.set_active(idx)
        if self.state.mode == ViewMode.SINGLE:
            self._attach_single(idx)
            # Sichtbares LocalAppWidget im Single Mode nachskalieren
            w = self.source_widgets[idx]
            if isinstance(w, LocalAppWidget):
                w.force_fit()
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

    def _maybe_start_auto_update(self) -> None:
        settings = getattr(self.cfg, "updates", None)
        if not settings or not getattr(settings, "enabled", False):
            return
        feed_url = getattr(settings, "feed_url", "") or ""
        if not feed_url.strip():
            return

        try:
            install_dir = self._resolve_install_dir()
            service = AutoUpdateService(
                settings=settings,
                install_dir=install_dir,
                current_version=__version__,
                logger=self.log,
            )
        except Exception as ex:
            self.log.error("failed to initialise auto update: %s", ex, extra={"source": "update"})
            return

        self._auto_update_service = service

        def _callback(result: Optional[UpdateResult]) -> None:
            if not result:
                return
            if result.installed and result.release:
                version = result.release.version

                def _notify_success() -> None:
                    QMessageBox.information(
                        self,
                        tr("Update installed"),
                        tr(
                            "MultiScreenKiosk was updated to version {version}. Please restart the application to finish.",
                            version=version,
                        ),
                    )

                QTimer.singleShot(0, _notify_success)
            elif result.error:
                error_text = result.error

                def _notify_failure() -> None:
                    QMessageBox.warning(
                        self,
                        tr("Update failed"),
                        tr("Automatic update failed: {error}", error=error_text),
                    )

                QTimer.singleShot(0, _notify_failure)

        service.run_in_background(_callback)

    def _resolve_install_dir(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[2]

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
        # Schutz vor versehentlichem Alt+F4 nur wenn kein programmgesteuerter Quit
        if self.isFullScreen() and not self._programmatic_quit:
            mods = QApplication.keyboardModifiers()
            if not mods & Qt.ShiftModifier:
                ev.ignore()
                return
        for svc in self.browser_services:
            if svc is not None:
                svc.stop()
        for w in self.source_widgets:
            if isinstance(w, LocalAppWidget):
                w.stop()
        super().closeEvent(ev)

    # ---------- Fenster Spy nur aus Einstellungen ----------
    def _open_window_spy(self):
        idx = self.state.active_index
        if not (0 <= idx < len(self.source_widgets)):
            QMessageBox.information(self, "Fenster Spy", "Kein aktives Widget.")
            return
        w = self.source_widgets[idx]
        if not isinstance(w, LocalAppWidget):
            QMessageBox.information(self, "Fenster Spy", "Der aktive Slot ist keine lokale Anwendung.")
            return

        dlg = WindowSpyDialog(
            title="Fenster Spy",
            pid_root=w._pid,
            attach_callback=w.force_attach,
            parent=self
        )
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.setModal(False)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
