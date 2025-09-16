from __future__ import annotations
from typing import Optional, Dict, Any, List, Callable
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QLineEdit, QFileDialog, QMessageBox,
    QKeySequenceEdit, QMenu
)

# Log Viewer und Log Pfad
from modules.ui.log_viewer import LogViewer
from modules.utils.logger import get_logger
from modules.utils.i18n import tr, i18n, LanguageInfo
from modules.utils.config_loader import DEFAULT_SHORTCUTS, RemoteLogExportSettings
from modules.ui.remote_export_dialog import RemoteExportDialog

# Fenster Spy optional importieren
try:
    from modules.ui.window_spy import WindowSpyDialog  # type: ignore
    _HAVE_SPY = True
except Exception:
    _HAVE_SPY = False

_log = get_logger(__name__)

class SettingsDialog(QDialog):
    """
    Rahmungsloser Settings Dialog.
    results():
      {
        "nav_orientation": str,
        "enable_hamburger": bool,
        "placeholder_enabled": bool,
        "placeholder_gif_path": str,
        "theme": str,
        "logo_path": str,
        "shortcuts": Dict[str, str],
        "remote_export": RemoteLogExportSettings,
        "quit_requested": bool
      }
    """

    def __init__(self,
                 nav_orientation: str,
                 enable_hamburger: bool,
                 placeholder_enabled: bool,
                 placeholder_gif_path: str,
                 theme: str,
                 logo_path: str,
                 split_enabled: bool,
                 shortcuts: Optional[Dict[str, str]] = None,
                 remote_export: Optional[RemoteLogExportSettings] = None,
                 backup_handler: Optional[Callable[[Path], None]] = None,
                 restore_handler: Optional[Callable[[Path], Any]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._drag_pos: Optional[QPoint] = None
        self._result: Dict[str, Any] = {}
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setMinimumSize(640, 380)
        self._backup_handler = backup_handler
        self._restore_handler = restore_handler
        self._remote_export_settings = (
            deepcopy(remote_export) if remote_export is not None else RemoteLogExportSettings()
        )

        # ---------- Titlebar ----------
        bar = QWidget(self)
        bar.setObjectName("titlebar")
        bar_l = QHBoxLayout(bar)
        bar_l.setContentsMargins(12, 8, 12, 8)
        bar_l.setSpacing(8)

        self.title_lbl = QLabel("", bar)
        bar_l.addWidget(self.title_lbl, 1)

        self.btn_close = QPushButton("×", bar)
        self.btn_close.setFixedWidth(28)
        self.btn_close.clicked.connect(self.reject)
        bar_l.addWidget(self.btn_close)

        # ---------- Content ----------
        body = QWidget(self)
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(16, 16, 16, 16)
        body_l.setSpacing(12)

        # Ausrichtung
        row1 = QHBoxLayout()
        self.lbl_orientation = QLabel("", self)
        row1.addWidget(self.lbl_orientation)
        self.nav_combo = QComboBox(self)
        self.nav_combo.addItem("", "left")
        self.nav_combo.addItem("", "top")
        self.nav_combo.setCurrentIndex(0 if (nav_orientation or "left") == "left" else 1)
        row1.addWidget(self.nav_combo, 1)

        # Hamburger
        row2 = QHBoxLayout()
        self.hamburger_cb = QCheckBox("", self)
        self.hamburger_cb.setChecked(bool(enable_hamburger))
        row2.addWidget(self.hamburger_cb, 1)

        # Theme
        row3 = QHBoxLayout()
        self.lbl_theme = QLabel("", self)
        row3.addWidget(self.lbl_theme)
        self.theme_combo = QComboBox(self)
        self.theme_combo.addItem("", "light")
        self.theme_combo.addItem("", "dark")
        self.theme_combo.setCurrentIndex(0 if (theme or "light") == "light" else 1)
        row3.addWidget(self.theme_combo, 1)

        # Language
        row_lang = QHBoxLayout()
        self.lbl_language = QLabel("", self)
        row_lang.addWidget(self.lbl_language)
        self.language_combo = QComboBox(self)
        self._language_options: List[LanguageInfo] = i18n.available_languages()
        for info in self._language_options:
            self.language_combo.addItem("", info.code)
        cur_lang = i18n.get_language()
        try:
            idx = next(i for i, info in enumerate(self._language_options) if info.code == cur_lang)
        except StopIteration:
            idx = 0
        self.language_combo.setCurrentIndex(idx)
        row_lang.addWidget(self.language_combo, 1)

        # Placeholder
        row4 = QHBoxLayout()
        self.placeholder_cb = QCheckBox("", self)
        self.placeholder_cb.setChecked(bool(placeholder_enabled))
        row4.addWidget(self.placeholder_cb)

        self.gif_edit = QLineEdit(self)
        self.gif_edit.setPlaceholderText("")
        self.gif_edit.setText(placeholder_gif_path or "")
        self.btn_browse_gif = QPushButton("", self)
        self.btn_browse_gif.clicked.connect(self._browse_gif)
        row4.addWidget(self.gif_edit, 1)
        row4.addWidget(self.btn_browse_gif)

        # Logo
        row5 = QHBoxLayout()
        self.lbl_logo = QLabel("", self)
        row5.addWidget(self.lbl_logo)
        self.logo_edit = QLineEdit(self)
        self.logo_edit.setPlaceholderText("")
        self.logo_edit.setText(logo_path or "")
        self.btn_browse_logo = QPushButton("", self)
        self.btn_browse_logo.clicked.connect(self._browse_logo)
        row5.addWidget(self.logo_edit, 1)
        row5.addWidget(self.btn_browse_logo)

        # Shortcuts
        self.lbl_shortcuts = QLabel("", self)
        sc_container = QVBoxLayout()
        self.shortcut_edits: Dict[str, QKeySequenceEdit] = {}
        self.shortcut_labels: Dict[str, QLabel] = {}
        sc_data = shortcuts or DEFAULT_SHORTCUTS
        sc_order = [
            "select_1", "select_2", "select_3", "select_4",
            "next_page", "prev_page", "toggle_mode", "toggle_kiosk",
        ]
        for key in sc_order:
            row_sc = QHBoxLayout()
            lbl = QLabel("", self)
            row_sc.addWidget(lbl)
            edit = QKeySequenceEdit(self)
            edit.setKeySequence(QKeySequence(sc_data.get(key, DEFAULT_SHORTCUTS.get(key, ""))))
            row_sc.addWidget(edit, 1)
            sc_container.addLayout(row_sc)
            self.shortcut_edits[key] = edit
            self.shortcut_labels[key] = lbl

        body_l.addLayout(row1)
        body_l.addLayout(row2)
        body_l.addLayout(row3)
        body_l.addLayout(row_lang)
        body_l.addLayout(row4)
        body_l.addLayout(row5)
        body_l.addWidget(self.lbl_shortcuts)
        body_l.addLayout(sc_container)
        self.info_lbl = None
        if not split_enabled:
            self.info_lbl = QLabel("", self)
            self.info_lbl.setWordWrap(True)
            body_l.addWidget(self.info_lbl)

        # ---------- Footer Aktionen ----------
        footer = QHBoxLayout()
        self.btn_config = QPushButton("", self)
        self._config_menu = QMenu(self.btn_config)
        self.action_backup = self._config_menu.addAction("")
        self.action_backup.triggered.connect(self._trigger_backup)
        self.action_restore = self._config_menu.addAction("")
        self.action_restore.triggered.connect(self._trigger_restore)

        self.btn_logs = QPushButton("", self)
        self.btn_remote_export = QPushButton("", self)
        self.btn_spy = QPushButton("", self)
        self.btn_quit = QPushButton("", self)
        self.btn_cancel = QPushButton("", self)
        self.btn_ok = QPushButton("", self)
        footer.addWidget(self.btn_config)
        footer.addWidget(self.btn_logs)
        footer.addWidget(self.btn_remote_export)
        footer.addWidget(self.btn_spy)
        footer.addStretch(1)
        footer.addWidget(self.btn_quit)
        footer.addWidget(self.btn_cancel)
        footer.addWidget(self.btn_ok)

        # Root
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(bar)
        root.addWidget(body, 1)
        root.addLayout(footer)

        # Events
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._accept_save)
        self.btn_config.clicked.connect(self._open_config_menu)
        self.btn_logs.clicked.connect(self._open_logs_window)
        self.btn_remote_export.clicked.connect(self._open_remote_export_dialog)
        self.btn_quit.clicked.connect(self._request_quit)
        self.btn_spy.clicked.connect(self._open_window_spy)

        # Styling
        self._apply_style()

        # Child Fenster Referenzen
        self._child_windows: List[QDialog] = []

        self._refresh_config_actions()

        i18n.language_changed.connect(lambda _l: self._apply_translations())
        self._apply_translations()
        self._update_remote_button_caption()

    # ------- Actions -------
    def _accept_save(self):
        sc_map: Dict[str, str] = {}
        for key, edit in self.shortcut_edits.items():
            seq = edit.keySequence().toString(QKeySequence.NativeText).strip()
            if seq:
                sc_map[key] = seq
        seqs = list(sc_map.values())
        if len(seqs) != len(set(seqs)):
            QMessageBox.warning(self, tr("Shortcut conflict"), tr("Shortcuts must be unique."))
            return

        merged = DEFAULT_SHORTCUTS.copy()
        merged.update(sc_map)

        self._result = {
            "nav_orientation": self.nav_combo.currentData(),
            "enable_hamburger": bool(self.hamburger_cb.isChecked()),
            "placeholder_enabled": bool(self.placeholder_cb.isChecked()),
            "placeholder_gif_path": self.gif_edit.text().strip(),
            "theme": self.theme_combo.currentData(),
            "language": self.language_combo.currentData(),
            "logo_path": self.logo_edit.text().strip(),
            "shortcuts": merged,
            "remote_export": deepcopy(self._remote_export_settings),
            "quit_requested": False,
        }
        self.accept()

    def _update_remote_button_caption(self):
        status = tr("enabled") if getattr(self._remote_export_settings, "enabled", False) else tr("disabled")
        count = len(getattr(self._remote_export_settings, "destinations", []) or [])
        self.btn_remote_export.setText(tr("Remote export ({status})", status=status))
        self.btn_remote_export.setToolTip(tr("{count} destinations configured", count=count))

    def _refresh_config_actions(self):
        have_backup = bool(self._backup_handler)
        have_restore = bool(self._restore_handler)
        if hasattr(self, "action_backup"):
            self.action_backup.setVisible(have_backup)
            self.action_backup.setEnabled(have_backup)
        if hasattr(self, "action_restore"):
            self.action_restore.setVisible(have_restore)
            self.action_restore.setEnabled(have_restore)
        show_button = have_backup or have_restore
        self.btn_config.setVisible(show_button)
        self.btn_config.setEnabled(show_button)

    def _open_config_menu(self):
        actions = [act for act in self._config_menu.actions() if act.isVisible() and act.isEnabled()]
        if not actions:
            return
        if len(actions) == 1:
            actions[0].trigger()
            return
        pos = self.btn_config.mapToGlobal(self.btn_config.rect().bottomLeft())
        self._config_menu.exec(pos)

    def _open_remote_export_dialog(self):
        dlg = RemoteExportDialog(self._remote_export_settings, self)
        if dlg.exec():
            result = dlg.result_settings()
            if result is not None:
                self._remote_export_settings = deepcopy(result)
                self._update_remote_button_caption()

    def _open_logs_window(self):
        dlg = LogViewer(self)
        dlg.setModal(False)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.show()
        self._child_windows.append(dlg)

    def _trigger_backup(self):
        if not self._backup_handler:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Backup config"),
            "",
            tr("JSON files (*.json);;All files (*)")
        )
        if not file_path:
            return
        path = Path(file_path)
        if not path.suffix:
            path = path.with_suffix(".json")
        try:
            self._backup_handler(path)
            _log.info("config backup written to %s", path)
        except Exception as ex:
            _log.error("config backup failed: %s", ex)
            QMessageBox.critical(self, tr("Backup config"), tr("Backup failed: {ex}", ex=ex))
            return
        QMessageBox.information(self, tr("Backup config"), tr("Configuration saved to {path}", path=str(path)))

    def _trigger_restore(self):
        if not self._restore_handler:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Restore config"),
            "",
            tr("JSON files (*.json);;All files (*)")
        )
        if not file_path:
            return
        path = Path(file_path)
        try:
            cfg = self._restore_handler(path)
            _log.info("config restored from %s", path)
        except Exception as ex:
            _log.error("config restore failed: %s", ex)
            QMessageBox.critical(self, tr("Restore config"), tr("Restore failed: {ex}", ex=ex))
            return
        QMessageBox.information(self, tr("Restore config"), tr("Configuration restored from {path}", path=str(path)))
        self._result = {
            "restored_config": cfg,
            "restored_from": str(path),
            "quit_requested": False,
        }
        self.accept()

    # ===== Fenster Spy =====
    def _open_window_spy(self):
        if not _HAVE_SPY:
            QMessageBox.information(
                self,
                tr("Window Spy"),
                tr("Window Spy is not available.\nThe module window_spy could not be loaded.")
            )
            return

        # attach Callback akzeptiert beliebige Argumente, damit wir zu allen Spy Versionen kompatibel sind
        def _on_spy_attach(*args, **kwargs):
            _log.info("Spy Auswahl empfangen args=%s kwargs=%s", args, kwargs, extra={"source": "window_spy"})
            # Nutzerverstaendliche Rueckmeldung
            QMessageBox.information(self,
                                    tr("Window selected"),
                                    tr("The window was recognized. If embedding is intended, the app does this automatically."))
        # Versuche die exakte Signatur aus deinem Screenshot: keyword only
        try:
            dlg = WindowSpyDialog(title="Fenster Spy", pid_root=None, attach_callback=_on_spy_attach, parent=self)  # type: ignore
        except TypeError as ex:
            # Verstaendliche Meldung, plus technische Info klein
            QMessageBox.warning(
                self,
                tr("Window Spy"),
                tr("Window Spy could not be started.\nThis version requires a different start.\n\nTechnical info: {ex}", ex=ex)
            )
            return
        except Exception as ex:
            QMessageBox.warning(
                self,
                tr("Window Spy"),
                tr("Window Spy could not be started.\nTechnical info: {ex}", ex=ex)
            )
            return

        try:
            if not dlg.windowTitle():
                dlg.setWindowTitle(tr("Window Spy"))
            dlg.setModal(False)
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.show()
            self._child_windows.append(dlg)
        except Exception as ex:
            QMessageBox.warning(
                self,
                tr("Window Spy"),
                tr("Window Spy could not be displayed.\nTechnical info: {ex}", ex=ex)
            )

    def _request_quit(self):
        m = QMessageBox(self)
        m.setWindowTitle(tr("Confirm quit"))
        m.setText(tr("Do you want to quit the application"))
        m.setInformativeText(tr("Unsaved changes might get lost."))
        m.setIcon(QMessageBox.Warning)
        m.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        m.setDefaultButton(QMessageBox.No)
        res = m.exec()

        if res == QMessageBox.Yes:
            self._result = {
                "nav_orientation": self.nav_combo.currentData(),
                "enable_hamburger": bool(self.hamburger_cb.isChecked()),
                "placeholder_enabled": bool(self.placeholder_cb.isChecked()),
                "placeholder_gif_path": self.gif_edit.text().strip(),
                "theme": self.theme_combo.currentData(),
                "language": self.language_combo.currentData(),
                "logo_path": self.logo_edit.text().strip(),
                "remote_export": deepcopy(self._remote_export_settings),
                "quit_requested": True,
            }
            self.accept()

    def results(self) -> Dict[str, Any]:
        if self._result:
            return self._result

        sc_map: Dict[str, str] = {}
        for key, edit in self.shortcut_edits.items():
            seq = edit.keySequence().toString(QKeySequence.NativeText).strip()
            if seq:
                sc_map[key] = seq
        merged = DEFAULT_SHORTCUTS.copy()
        merged.update(sc_map)

        return {
            "nav_orientation": self.nav_combo.currentData(),
            "enable_hamburger": bool(self.hamburger_cb.isChecked()),
            "placeholder_enabled": bool(self.placeholder_cb.isChecked()),
            "placeholder_gif_path": self.gif_edit.text().strip(),
            "theme": self.theme_combo.currentData(),
            "language": self.language_combo.currentData(),
            "logo_path": self.logo_edit.text().strip(),
            "shortcuts": merged,
            "remote_export": deepcopy(self._remote_export_settings),
            "quit_requested": False,
        }

    def _browse_gif(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Placeholder GIF"), "", "GIF (*.gif);;All files (*)")
        if path:
            self.gif_edit.setText(path)

    def _browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Logo"), "", "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All files (*)")
        if path:
            self.logo_edit.setText(path)

    # ------- Frameless Drag -------
    def mousePressEvent(self, e):
        w = self.childAt(e.position().toPoint())
        if e.button() == Qt.LeftButton and w and w.objectName() == "titlebar":
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        super().mouseReleaseEvent(e)

    # ------- Style -------
    def _apply_style(self):
        self.setStyleSheet("""
            #titlebar { background: rgba(127,127,127,0.08); }
            QLabel { font-size: 14px; }
            QLineEdit { border: 1px solid rgba(128,128,128,0.35); border-radius: 8px; padding: 6px 8px; }
            QPushButton {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(128,128,128,0.35);
                border-radius: 10px; padding: 8px 12px;
            }
            QPushButton:hover { border-color: rgba(128,128,128,0.55); }
            QPushButton:pressed { background: rgba(255,255,255,0.08); }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border:1px solid rgba(128,128,128,0.45); background: rgba(255,255,255,0.03); }
            QCheckBox::indicator:checked { background:#0a84ff; border-color:#0a84ff; }
        """)

    def _apply_translations(self):
        self.title_lbl.setText(tr("Settings"))
        self.lbl_orientation.setText(tr("Orientation"))
        self.nav_combo.setItemText(0, tr("Left"))
        self.nav_combo.setItemText(1, tr("Top"))
        self.hamburger_cb.setText(tr("Enable hamburger menu"))
        self.lbl_theme.setText(tr("Theme"))
        self.theme_combo.setItemText(0, tr("Light"))
        self.theme_combo.setItemText(1, tr("Dark"))
        self.lbl_language.setText(tr("Language"))
        for idx, info in enumerate(self._language_options):
            if idx < self.language_combo.count():
                translated = tr(info.name)
                if translated == info.name and info.native_name:
                    translated = info.native_name
                self.language_combo.setItemText(idx, translated)
        self.placeholder_cb.setText(tr("Enable placeholder"))
        self.gif_edit.setPlaceholderText(tr("Path to GIF"))
        self.btn_browse_gif.setText(tr("Browse"))
        self.lbl_logo.setText(tr("Logo path"))
        self.logo_edit.setPlaceholderText(tr("Path to logo"))
        self.btn_browse_logo.setText(tr("Browse"))
        self.lbl_shortcuts.setText(tr("Shortcuts"))
        names = {
            "select_1": tr("View 1"),
            "select_2": tr("View 2"),
            "select_3": tr("View 3"),
            "select_4": tr("View 4"),
            "next_page": tr("Next page"),
            "prev_page": tr("Previous page"),
            "toggle_mode": tr("Toggle mode"),
            "toggle_kiosk": tr("Toggle kiosk"),
        }
        for key, lbl in self.shortcut_labels.items():
            lbl.setText(names.get(key, key))
        if self.info_lbl is not None:
            self.info_lbl.setText(tr("Note: Split screen is disabled. Switch via the sidebar, Ctrl+Q is inactive."))
        config_label = tr("Configuration")
        if self._backup_handler and self._restore_handler:
            config_label = tr("Backup / restore config")
        elif self._backup_handler:
            config_label = tr("Backup config")
        elif self._restore_handler:
            config_label = tr("Restore config")
        self.btn_config.setText(config_label)
        self.action_backup.setText(tr("Backup config"))
        self.action_restore.setText(tr("Restore config"))
        self.btn_logs.setText(tr("Logs"))
        self.btn_remote_export.setText(tr("Remote export"))
        self.btn_spy.setText(tr("Window Spy"))
        self.btn_quit.setText(tr("Quit"))
        self.btn_cancel.setText(tr("Cancel"))
        self.btn_ok.setText(tr("Save"))
        self._update_remote_button_caption()
        self._refresh_config_actions()
