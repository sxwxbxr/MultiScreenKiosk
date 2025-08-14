from __future__ import annotations
from typing import Optional, Dict, Any, List

import os
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QLineEdit, QFileDialog, QTextEdit, QMessageBox
)

# Log Viewer und Log Pfad
from modules.ui.log_viewer import LogViewer
from modules.utils.logger import get_log_path, get_logger

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
        self.setWindowTitle("Log Statistik")
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
        self.btn_close = QPushButton("Schliessen", self)
        self.btn_close.clicked.connect(self.close)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

        self._refresh()

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
                 parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._drag_pos: Optional[QPoint] = None
        self._result: Dict[str, Any] = {}
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setMinimumSize(640, 380)

        # ---------- Titlebar ----------
        bar = QWidget(self)
        bar.setObjectName("titlebar")
        bar_l = QHBoxLayout(bar)
        bar_l.setContentsMargins(12, 8, 12, 8)
        bar_l.setSpacing(8)

        self.title_lbl = QLabel("Einstellungen", bar)
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
        row1.addWidget(QLabel("Ausrichtung"))
        self.nav_combo = QComboBox(self)
        self.nav_combo.addItems(["left", "top"])
        self.nav_combo.setCurrentText(nav_orientation or "left")
        row1.addWidget(self.nav_combo, 1)

        # Hamburger
        row2 = QHBoxLayout()
        self.hamburger_cb = QCheckBox("Burgermenue anzeigen ermoeglichen", self)
        self.hamburger_cb.setChecked(bool(enable_hamburger))
        row2.addWidget(self.hamburger_cb, 1)

        # Theme
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Theme"))
        self.theme_combo = QComboBox(self)
        self.theme_combo.addItems(["light", "dark"])
        self.theme_combo.setCurrentText(theme or "light")
        row3.addWidget(self.theme_combo, 1)

        # Placeholder
        row4 = QHBoxLayout()
        self.placeholder_cb = QCheckBox("Placeholder aktiv", self)
        self.placeholder_cb.setChecked(bool(placeholder_enabled))
        row4.addWidget(self.placeholder_cb)

        self.gif_edit = QLineEdit(self)
        self.gif_edit.setPlaceholderText("Pfad zu GIF")
        self.gif_edit.setText(placeholder_gif_path or "")
        btn_browse_gif = QPushButton("Waehlen", self)
        btn_browse_gif.clicked.connect(self._browse_gif)
        row4.addWidget(self.gif_edit, 1)
        row4.addWidget(btn_browse_gif)

        # Logo
        row5 = QHBoxLayout()
        row5.addWidget(QLabel("Logo Pfad"))
        self.logo_edit = QLineEdit(self)
        self.logo_edit.setPlaceholderText("Pfad zum Logo")
        self.logo_edit.setText(logo_path or "")
        btn_browse_logo = QPushButton("Waehlen", self)
        btn_browse_logo.clicked.connect(self._browse_logo)
        row5.addWidget(self.logo_edit, 1)
        row5.addWidget(btn_browse_logo)

        body_l.addLayout(row1)
        body_l.addLayout(row2)
        body_l.addLayout(row3)
        body_l.addLayout(row4)
        body_l.addLayout(row5)

        # ---------- Footer Aktionen ----------
        footer = QHBoxLayout()
        self.btn_logs = QPushButton("Logs", self)
        self.btn_stats = QPushButton("Log Statistik", self)
        self.btn_spy = QPushButton("Fenster Spy", self)
        self.btn_quit = QPushButton("Beenden", self)
        self.btn_cancel = QPushButton("Abbrechen", self)
        self.btn_ok = QPushButton("Speichern", self)
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

    # ------- Actions -------
    def _accept_save(self):
        self._result = {
            "nav_orientation": self.nav_combo.currentText(),
            "enable_hamburger": bool(self.hamburger_cb.isChecked()),
            "placeholder_enabled": bool(self.placeholder_cb.isChecked()),
            "placeholder_gif_path": self.gif_edit.text().strip(),
            "theme": self.theme_combo.currentText(),
            "logo_path": self.logo_edit.text().strip(),
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

    # ===== Fenster Spy =====
    def _open_window_spy(self):
        if not _HAVE_SPY:
            QMessageBox.information(
                self,
                "Fenster Spy",
                "Fenster Spy ist nicht verfuegbar.\nDas Modul window_spy konnte nicht geladen werden."
            )
            return

        # attach Callback akzeptiert beliebige Argumente, damit wir zu allen Spy Versionen kompatibel sind
        def _on_spy_attach(*args, **kwargs):
            _log.info("Spy Auswahl empfangen args=%s kwargs=%s", args, kwargs, extra={"source": "window_spy"})
            # Nutzerverstaendliche Rueckmeldung
            QMessageBox.information(self, "Fenster ausgewaehlt",
                                    "Das Fenster wurde erkannt. Falls Einbettung vorgesehen ist, "
                                    "uebernimmt die App dies automatisch.")
        # Versuche die exakte Signatur aus deinem Screenshot: keyword only
        try:
            dlg = WindowSpyDialog(title="Fenster Spy", pid_root=None, attach_callback=_on_spy_attach, parent=self)  # type: ignore
        except TypeError as ex:
            # Verstaendliche Meldung, plus technische Info klein
            QMessageBox.warning(
                self,
                "Fenster Spy",
                "Fenster Spy konnte nicht gestartet werden.\n"
                "Diese Version benoetigt einen anderen Start.\n\n"
                f"Technische Info: {ex}"
            )
            return
        except Exception as ex:
            QMessageBox.warning(
                self,
                "Fenster Spy",
                "Fenster Spy konnte nicht gestartet werden.\n"
                f"Technische Info: {ex}"
            )
            return

        try:
            if not dlg.windowTitle():
                dlg.setWindowTitle("Fenster Spy")
            dlg.setModal(False)
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.show()
            self._child_windows.append(dlg)
        except Exception as ex:
            QMessageBox.warning(
                self,
                "Fenster Spy",
                "Fenster Spy konnte nicht angezeigt werden.\n"
                f"Technische Info: {ex}"
            )

    def _request_quit(self):
        m = QMessageBox(self)
        m.setWindowTitle("Beenden bestaetigen")
        m.setText("Moechtest du die Anwendung beenden")
        m.setInformativeText("Ungespeicherte Aenderungen gehen moeglicherweise verloren.")
        m.setIcon(QMessageBox.Warning)
        m.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        m.setDefaultButton(QMessageBox.No)
        res = m.exec()

        if res == QMessageBox.Yes:
            self._result = {
                "nav_orientation": self.nav_combo.currentText(),
                "enable_hamburger": bool(self.hamburger_cb.isChecked()),
                "placeholder_enabled": bool(self.placeholder_cb.isChecked()),
                "placeholder_gif_path": self.gif_edit.text().strip(),
                "theme": self.theme_combo.currentText(),
                "logo_path": self.logo_edit.text().strip(),
                "quit_requested": True,
            }
            self.accept()

    def results(self) -> Dict[str, Any]:
        return self._result or {
            "nav_orientation": self.nav_combo.currentText(),
            "enable_hamburger": bool(self.hamburger_cb.isChecked()),
            "placeholder_enabled": bool(self.placeholder_cb.isChecked()),
            "placeholder_gif_path": self.gif_edit.text().strip(),
            "theme": self.theme_combo.currentText(),
            "logo_path": self.logo_edit.text().strip(),
            "quit_requested": False,
        }

    def _browse_gif(self):
        path, _ = QFileDialog.getOpenFileName(self, "Placeholder GIF", "", "GIF (*.gif);;Alle Dateien (*)")
        if path:
            self.gif_edit.setText(path)

    def _browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Logo", "", "Bilder (*.png *.jpg *.jpeg *.bmp *.gif);;Alle Dateien (*)")
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
