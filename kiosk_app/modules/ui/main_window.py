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
    QGridLayout, QLabel, QApplication, QToolButton, QMenu, QMessageBox,
    QFrame, QPushButton
)

from modules.ui.app_state import AppState, ViewMode
from modules.ui.sidebar import Sidebar
from modules.ui.settings_dialog import SettingsDialog
from modules.ui.browser_host import BrowserHostWidget
from modules.ui.window_spy import WindowSpyDialog
from modules.services.auto_update import AutoUpdateService, UpdateResult
from modules.services.browser_services import BrowserService, make_webview
from modules.services.local_app_service import LocalAppWidget
from modules.ui.theme import get_palette, build_application_stylesheet, ThemePalette
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
    initial_load_finished = Signal()

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

        # Initiales Lade-Tracking
        self._initial_loading_flags: List[bool] = []
        self._initial_loading_timer: Optional[QTimer] = None
        self._initial_loading_complete = False
        self._setup_initial_loading_tracker()

        # Container
        self.single_host = QWidget(self)
        self.single_layout = QVBoxLayout(self.single_host)
        self.single_layout.setContentsMargins(0, 0, 0, 0)
        self.single_layout.setSpacing(0)

        self.grid = QWidget(self)
        self.grid_layout = QGridLayout(self.grid)
        self.grid_layout.setContentsMargins(12, 12, 12, 12)
        self.grid_layout.setSpacing(12)

        self.mode_stack = QStackedWidget(self)
        self.mode_stack.addWidget(self.single_host)  # 0
        self.mode_stack.addWidget(self.grid)         # 1

        # Overlay Burger
        self.overlay_burger = QToolButton(self)
        self.overlay_burger.setObjectName("OverlayBurger")
        self.overlay_burger.setText("☰")
        self.overlay_burger.setToolTip("")
        self.overlay_burger.setVisible(False)
        self.overlay_burger.clicked.connect(self._open_overlay_menu)

        # Header references (created in _build_root_and_sidebar)
        self.header_bar: QWidget | None = None
        self.header_title: QLabel | None = None
        self.header_subtitle: QLabel | None = None
        self.mode_badge: QLabel | None = None
        self.kiosk_badge: QLabel | None = None
        self.btn_mode_toggle: QPushButton | None = None
        self.btn_header_settings: QToolButton | None = None
        self.btn_kiosk: QToolButton | None = None
        self.content_card: QFrame | None = None
        self.content_container: QWidget | None = None

        # Theme palette before building the root widgets
        self._palette: ThemePalette = get_palette(self.cfg.ui.theme)

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
    def _build_root_and_sidebar(self) -> None:
        titles = [s.name for s in self.sources]

        old = self.centralWidget()
        if old:
            old.deleteLater()

        orientation = self.cfg.ui.nav_orientation if self.cfg.ui.nav_orientation in {"left", "top"} else "left"

        central = QWidget(self)
        if orientation == "top":
            root = QVBoxLayout(central)
        else:
            root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(
            titles=titles,
            width=self.cfg.ui.sidebar_width,
            orientation=orientation,
            enable_hamburger=self.cfg.ui.enable_hamburger,
            logo_path=self.cfg.ui.logo_path,
            split_enabled=self.cfg.ui.split_enabled,
        )
        self.sidebar.apply_palette(self._palette)
        self.sidebar.view_selected.connect(self.on_select_view)
        self.sidebar.toggle_mode.connect(self.on_toggle_mode)
        self.sidebar.page_changed.connect(self.on_page_changed)
        self.sidebar.request_settings.connect(self.open_settings)
        self.sidebar.collapsed_changed.connect(self.on_sidebar_collapsed_changed)

        if orientation == "top":
            root.addWidget(self.sidebar)
            content = self._build_main_content(orientation)
            root.addWidget(content, 1)
        else:
            root.addWidget(self.sidebar)
            content = self._build_main_content(orientation)
            root.addWidget(content, 1)

        self.content_container = content
        self.setCentralWidget(central)

        if self.num_sources:
            self.sidebar.set_active_global_index(min(self.state.active_index, self.num_sources - 1))

        self._place_overlay_burger()
        self._update_header_info()

    def _build_main_content(self, orientation: str) -> QWidget:
        container = QWidget(self)
        margins = (24, 24, 24, 24) if orientation != "top" else (24, 16, 24, 24)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(*margins)
        layout.setSpacing(18)

        self.header_bar = QWidget(container)
        self.header_bar.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(24, 18, 24, 18)
        header_layout.setSpacing(16)

        header_texts = QVBoxLayout()
        header_texts.setContentsMargins(0, 0, 0, 0)
        header_texts.setSpacing(4)

        self.header_title = QLabel("", self.header_bar)
        self.header_title.setObjectName("HeaderTitle")
        header_texts.addWidget(self.header_title)

        self.header_subtitle = QLabel("", self.header_bar)
        self.header_subtitle.setObjectName("HeaderSubtitle")
        self.header_subtitle.setWordWrap(True)
        header_texts.addWidget(self.header_subtitle)

        header_layout.addLayout(header_texts, 1)

        self.mode_badge = QLabel("", self.header_bar)
        self.mode_badge.setObjectName("ModeBadge")
        header_layout.addWidget(self.mode_badge)

        self.kiosk_badge = QLabel("", self.header_bar)
        self.kiosk_badge.setObjectName("StatusBadge")
        header_layout.addWidget(self.kiosk_badge)

        self.btn_mode_toggle = QPushButton("", self.header_bar)
        self.btn_mode_toggle.setProperty("accent", True)
        self.btn_mode_toggle.clicked.connect(self.on_toggle_mode)
        header_layout.addWidget(self.btn_mode_toggle)
        self.btn_mode_toggle.setVisible(self.cfg.ui.split_enabled)

        self.btn_header_settings = QPushButton("", self.header_bar)
        self.btn_header_settings.clicked.connect(self.open_settings)
        header_layout.addWidget(self.btn_header_settings)

        self.btn_kiosk = QPushButton("", self.header_bar)
        self.btn_kiosk.setProperty("accent", True)
        self.btn_kiosk.clicked.connect(self.toggle_kiosk)
        header_layout.addWidget(self.btn_kiosk)

        layout.addWidget(self.header_bar)

        self.content_card = QFrame(container)
        self.content_card.setObjectName("ContentCard")
        card_layout = QVBoxLayout(self.content_card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)
        card_layout.addWidget(self.mode_stack, 1)

        layout.addWidget(self.content_card, 1)
        return container

    def _update_header_info(self) -> None:
        if not self.header_title or not self.header_subtitle:
            return

        if not self.sources:
            self.header_title.setText(tr("Welcome"))
            self.header_subtitle.setText(tr("Add sources in the setup dialog to get started."))
        else:
            active = self.state.active_index
            if not (0 <= active < len(self.sources)):
                active = 0
            self.header_title.setText(self.sources[active].name)
            if self.state.mode == ViewMode.SINGLE:
                self.header_subtitle.setText(tr("Focused view · showing one source at a time"))
            else:
                total_pages = max(1, (self.num_sources + self.page_size - 1) // self.page_size)
                self.header_subtitle.setText(
                    tr(
                        "Wall view · Page {current}/{total}",
                        current=self.current_page + 1,
                        total=total_pages,
                    )
                )

        if self.mode_badge:
            if self.state.mode == ViewMode.SINGLE:
                self.mode_badge.setText(tr("Focus"))
                self.mode_badge.setProperty("mode", "single")
            else:
                self.mode_badge.setText(tr("Wall"))
                self.mode_badge.setProperty("mode", "wall")
            self.mode_badge.style().unpolish(self.mode_badge)
            self.mode_badge.style().polish(self.mode_badge)

        if self.btn_mode_toggle:
            if not self.cfg.ui.split_enabled:
                self.btn_mode_toggle.hide()
            else:
                self.btn_mode_toggle.show()
                if self.state.mode == ViewMode.SINGLE:
                    self.btn_mode_toggle.setText(tr("Switch to wall view"))
                else:
                    self.btn_mode_toggle.setText(tr("Switch to focus view"))

        if self.kiosk_badge:
            if self.isFullScreen():
                self.kiosk_badge.setText(tr("Kiosk"))
                self.kiosk_badge.setProperty("status", "kiosk")
            else:
                self.kiosk_badge.setText(tr("Windowed"))
                self.kiosk_badge.setProperty("status", "window")
            self.kiosk_badge.style().unpolish(self.kiosk_badge)
            self.kiosk_badge.style().polish(self.kiosk_badge)

        if self.btn_kiosk:
            if self.isFullScreen():
                self.btn_kiosk.setText(tr("Leave kiosk mode"))
            else:
                self.btn_kiosk.setText(tr("Enter kiosk mode"))

        if self.btn_header_settings:
            self.btn_header_settings.setText(tr("Settings"))

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
            act_switch = m.addAction(tr("Switch layout"))
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
        if getattr(self, "_initial_loading_timer", None):
            try:
                self._initial_loading_timer.stop()
                self._initial_loading_timer.deleteLater()
            except Exception:
                pass
            self._initial_loading_timer = None
        self._initial_loading_flags = []
        self._initial_loading_complete = False

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
        self._setup_initial_loading_tracker()
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
            ph = QLabel(tr("No sources configured yet"), self.grid)
            ph.setObjectName("EmptySlot")
            ph.setAlignment(Qt.AlignCenter)
            self.grid_layout.addWidget(ph, 0, 0, 2, 2)
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
        self.overlay_burger.setToolTip(tr("Open navigation"))
        if self.btn_header_settings:
            self.btn_header_settings.setToolTip(tr("Open settings"))
        if self.btn_kiosk:
            self.btn_kiosk.setToolTip(tr("Toggle kiosk mode"))
        if self.btn_mode_toggle:
            self.btn_mode_toggle.setToolTip(tr("Toggle between wall and focus layouts"))
        if getattr(self, "sidebar", None):
            try:
                self.sidebar.retranslate_ui()
            except Exception:
                pass
        self._update_header_info()

    def apply_theme(self, theme: str) -> None:
        self._palette = get_palette(theme)
        self.setStyleSheet(build_application_stylesheet(self._palette))
        if getattr(self, "sidebar", None):
            try:
                self.sidebar.apply_palette(self._palette)
            except Exception:
                pass
        self._update_header_info()

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
        self._update_header_info()

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
        self._update_header_info()

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
        self._update_header_info()

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

    def _setup_initial_loading_tracker(self):
        if getattr(self, "_initial_loading_timer", None):
            try:
                self._initial_loading_timer.stop()
                self._initial_loading_timer.deleteLater()
            except Exception:
                pass
            self._initial_loading_timer = None

        total = len(self.source_widgets)
        self._initial_loading_flags = [False] * total
        self._initial_loading_complete = False

        if total == 0:
            QTimer.singleShot(0, self._emit_initial_loading_complete)
            return

        self._initial_loading_timer = QTimer(self)
        self._initial_loading_timer.setSingleShot(True)
        self._initial_loading_timer.setInterval(45000)
        self._initial_loading_timer.timeout.connect(self._on_initial_loading_timeout)

        for idx, widget in enumerate(self.source_widgets):
            if isinstance(widget, LocalAppWidget):
                widget.ready.connect(lambda i=idx: self._mark_source_ready(i))
            else:
                svc = self.browser_services[idx] if idx < len(self.browser_services) else None
                if svc is not None:
                    svc.page_ready.connect(lambda i=idx: self._mark_source_ready(i))
                else:
                    self._mark_source_ready(idx)

        self._initial_loading_timer.start()

    def _mark_source_ready(self, idx: int):
        if not (0 <= idx < len(self._initial_loading_flags)):
            return
        if self._initial_loading_flags[idx]:
            return
        self._initial_loading_flags[idx] = True
        if all(self._initial_loading_flags):
            self._emit_initial_loading_complete()

    def _emit_initial_loading_complete(self):
        if self._initial_loading_complete:
            return
        self._initial_loading_complete = True
        if getattr(self, "_initial_loading_timer", None):
            try:
                self._initial_loading_timer.stop()
                self._initial_loading_timer.deleteLater()
            except Exception:
                pass
            self._initial_loading_timer = None
        self.log.info("all sources reported ready", extra={"source": "ui"})
        self.initial_load_finished.emit()

    def _on_initial_loading_timeout(self):
        pending = [idx for idx, ready in enumerate(self._initial_loading_flags) if not ready]
        if pending:
            self.log.warning(
                "timeout while waiting for sources to embed; pending indices=%s",
                pending,
                extra={"source": "ui"},
            )
        self._emit_initial_loading_complete()

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
        self._update_header_info()

    def leave_kiosk(self):
        self.showNormal()
        self._update_header_info()

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
