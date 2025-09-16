from __future__ import annotations
from typing import Optional, Dict, Any, List, Callable

import os
from pathlib import Path
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QLineEdit, QFileDialog, QTextEdit, QMessageBox,
    QKeySequenceEdit
)

# Log Viewer und Log Pfad
from modules.ui.log_viewer import LogViewer
from modules.utils.logger import get_log_path, get_logger
from modules.utils.i18n import tr, i18n
from modules.utils.config_loader import DEFAULT_SHORTCUTS

# Fenster Spy optional importieren
try:
    from modules.ui.window_spy import WindowSpyDialog  # type: ignore
    _HAVE_SPY = True
except Exception:
    _HAVE_SPY = False

_log = get_logger(__name__)


def _human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(max(0, n))
    idx = 0
    while size >= 1024.0 and idx < len(units) - 1:
        size /= 1024.0
        idx += 1
    if idx == 0:
        return f"{int(size)} {units[idx]}"
    return f"{size:.2f} {units[idx]}"


class LogStatsDialog(QDialog):
    """Live Log Statistik mit Dateigroesse und Level Zaehlern."""
    def __init__(self, log_path: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._path = log_path
        self.setWindowTitle(tr("Log Statistics"))
        self.setModal(False)
        self.setMinimumSize(520, 360)

        layout = QVBoxLayout(self)
        self.lbl_info = QLabel(self)
        layout.addWidget(self.lbl_info)

        self.view = QTextEdit(self)
        self.view.setReadOnly(True)
        layout.addWidget(self.view, 1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_close = QPushButton(tr("Close"), self)
        self.btn_close.clicked.connect(self.close)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

        i18n.language_changed.connect(lambda _l: self._apply_translations())
        self._refresh()

    def _apply_translations(self):
        self.setWindowTitle(tr("Log Statistics"))
        self.btn_close.setText(tr("Close"))

    def closeEvent(self, ev):
        try:
            self._timer.stop()
        except Exception:
            pass
        super().closeEvent(ev)

    def _refresh(self):
        path = self._path
        info = warn = err = dbg = 0
        size = 0
        exists = os.path.isfile(path)
        if exists:
            try:
                size = os.path.getsize(path)
            except Exception:
                size = 0
        try:
            if exists:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        u = line.upper()
                        if " DEBUG " in u or u.startswith("DEBUG") or '"LEVEL": "DEBUG"' in u:
                            dbg += 1
                        elif " INFO " in u or u.startswith("INFO") or '"LEVEL": "INFO"' in u:
                            info += 1
                        elif " WARNING " in u or u.startswith("WARNING") or '"LEVEL": "WARNING"' in u:
                            warn += 1
                        elif " ERROR " in u or u.startswith("ERROR") or '"LEVEL": "ERROR"' in u:
                            err += 1
            total = info + warn + err + dbg
            human = _human_size(size)
            self.lbl_info.setText(f"Datei: {path}")
            text = (
                f"Groesse: {human} ({size} Bytes)\n"
                f"Gesamt:  {total}\n"
                f"Info:    {info}\n"
                f"Warn:    {warn}\n"
                f"Error:   {err}\n"
                f"Debug:   {dbg}"
            )
        except FileNotFoundError:
            self.lbl_info.setText(f"Datei: {path}")
            text = "Keine Logdatei gefunden."
        except Exception as ex:
            self.lbl_info.setText(f"Datei: {path}")
            text = f"Fehler beim Lesen der Logdatei:\n{ex}"

        self.view.setPlainText(text)


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
        self.language_combo.addItem("", "de")
        self.language_combo.addItem("", "en")
        cur_lang = i18n.get_language()
        self.language_combo.setCurrentIndex(0 if cur_lang.startswith("de") else 1)
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
        self.btn_backup = QPushButton("", self)
        self.btn_backup.clicked.connect(self._trigger_backup)
        self.btn_restore = QPushButton("", self)
        self.btn_restore.clicked.connect(self._trigger_restore)
        self.btn_logs = QPushButton("", self)
        self.btn_stats = QPushButton("", self)
        self.btn_spy = QPushButton("", self)
        self.btn_quit = QPushButton("", self)
        self.btn_cancel = QPushButton("", self)
        self.btn_ok = QPushButton("", self)
        footer.addWidget(self.btn_backup)
        footer.addWidget(self.btn_restore)
        footer.addWidget(self.btn_logs)
        footer.addWidget(self.btn_stats)
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
        self.btn_logs.clicked.connect(self._open_logs_window)
        self.btn_stats.clicked.connect(self._open_stats_window)
        self.btn_quit.clicked.connect(self._request_quit)
        self.btn_spy.clicked.connect(self._open_window_spy)

        # Styling
        self._apply_style()

        # Child Fenster Referenzen
        self._child_windows: List[QDialog] = []

        if not self._backup_handler:
            self.btn_backup.setVisible(False)
        if not self._restore_handler:
            self.btn_restore.setVisible(False)

        i18n.language_changed.connect(lambda _l: self._apply_translations())
        self._apply_translations()

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
            "quit_requested": False,
        }
        self.accept()

    def _open_logs_window(self):
        dlg = LogViewer(self)
        dlg.setModal(False)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.show()
        self._child_windows.append(dlg)

    def _open_stats_window(self):
        path = get_log_path()
        dlg = LogStatsDialog(path, self)
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
        self.language_combo.setItemText(0, tr("German"))
        self.language_combo.setItemText(1, tr("English"))
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
        if hasattr(self, "btn_backup"):
            self.btn_backup.setText(tr("Backup config"))
        if hasattr(self, "btn_restore"):
            self.btn_restore.setText(tr("Restore config"))
        self.btn_logs.setText(tr("Logs"))
        self.btn_stats.setText(tr("Log Statistics"))
        self.btn_spy.setText(tr("Window Spy"))
        self.btn_quit.setText(tr("Quit"))
        self.btn_cancel.setText(tr("Cancel"))
        self.btn_ok.setText(tr("Save"))
