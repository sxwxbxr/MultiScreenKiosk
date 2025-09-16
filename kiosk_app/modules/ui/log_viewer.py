# modules/ui/log_viewer.py
from __future__ import annotations
from typing import Optional, List

import os
import re
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QCheckBox, QPushButton, QTextEdit, QFileDialog, QMessageBox, QWidget
)

from modules.ui.theme import get_palette, build_dialog_stylesheet
from modules.utils.logger import get_log_path, get_log_bridge
from modules.utils.i18n import tr, i18n

_LEVELS = ["ALLE", "DEBUG", "INFO", "WARNING", "ERROR"]


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

    def __init__(self, log_path: str, theme: str | None = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._path = log_path
        self.setWindowTitle(tr("Log Statistics"))
        self.setModal(False)
        self.setMinimumSize(520, 360)

        palette = get_palette(theme)
        self.setStyleSheet(build_dialog_stylesheet(palette))

        layout = QVBoxLayout(self)
        self.lbl_info = QLabel(self)
        layout.addWidget(self.lbl_info)

        self.view = QTextEdit(self)
        self.view.setReadOnly(True)
        layout.addWidget(self.view, 1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_close = QPushButton(tr("Close"), self)
        self.btn_close.setProperty("accent", True)
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


class LogViewer(QDialog):
    """Einfacher Log Viewer mit Filtern und Live Update."""
    def __init__(self, parent: Optional[QWidget] = None, theme: str | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Logs"))
        self.setModal(False)
        self.setMinimumSize(800, 480)

        self._theme = theme or "light"
        self._palette = get_palette(self._theme)
        self.setStyleSheet(build_dialog_stylesheet(self._palette))

        self._path = get_log_path()
        self._buffer: List[str] = []   # Rohzeilen fuer Refilter
        self._file_pos = 0
        self._paused = False

        # Kopfzeile mit Filtern
        top = QHBoxLayout()
        self.lbl_level = QLabel("", self)
        top.addWidget(self.lbl_level)
        self.level_combo = QComboBox(self)
        self.level_combo.addItems(_LEVELS)
        self.level_combo.setCurrentIndex(0)

        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("")

        self.regex_cb = QCheckBox("", self)
        self.case_cb = QCheckBox("", self)

        self.auto_cb = QCheckBox("", self)
        self.auto_cb.setChecked(True)

        self.pause_cb = QCheckBox("", self)

        self.btn_refresh = QPushButton("", self)
        self.btn_clear = QPushButton("", self)
        self.btn_open = QPushButton("", self)
        self.btn_stats = QPushButton("", self)

        for w in [self.level_combo, self.search_edit, self.regex_cb, self.case_cb, self.auto_cb, self.pause_cb]:
            top.addWidget(w)
        top.addStretch(1)
        top.addWidget(self.btn_refresh)
        top.addWidget(self.btn_clear)
        top.addWidget(self.btn_open)
        top.addWidget(self.btn_stats)

        # Textansicht
        self.view = QTextEdit(self)
        self.view.setReadOnly(True)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.view, 1)

        # Events
        self.level_combo.currentIndexChanged.connect(self._apply_filters)
        self.search_edit.textChanged.connect(self._apply_filters)
        self.regex_cb.toggled.connect(self._apply_filters)
        self.case_cb.toggled.connect(self._apply_filters)
        self.auto_cb.toggled.connect(self._toggle_auto)
        self.pause_cb.toggled.connect(self._toggle_pause)
        self.btn_refresh.clicked.connect(self._reload_all)
        self.btn_clear.clicked.connect(self._clear_file)
        self.btn_open.clicked.connect(self._open_external)
        self.btn_stats.clicked.connect(self._open_stats_window)

        i18n.language_changed.connect(lambda _l: self._apply_translations())
        self._apply_translations()

        # Timer Polling
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._poll_append)
        self._timer.start()

        # Live Bridge
        try:
            bridge = get_log_bridge()
            if bridge is not None:
                bridge.lineEmitted.connect(self._on_bridge_line)
        except Exception:
            pass

        # Initial laden
        self._reload_all()

    # ---------- Bedienung ----------
    def _toggle_auto(self, _checked: bool):
        pass  # kein spezielles Verhalten noetig

    def _toggle_pause(self, checked: bool):
        self._paused = bool(checked)

    def _open_external(self):
        path = self._path
        if not os.path.isfile(path):
            QMessageBox.information(self, tr("Info"), tr("No log file found"))
            return
        try:
            # Dateidialog nur zum schnellen Kopieren oeffnen
            QFileDialog.getOpenFileName(self, "Logdatei", path, "Log (*.log *.txt);;Alle Dateien (*)")
        except Exception:
            pass

    def _clear_file(self):
        # Datei wirklich leeren
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                f.write("")
            self._buffer.clear()
            self._file_pos = 0
            self.view.clear()
        except Exception as ex:
            QMessageBox.warning(self, tr("Info"), tr("The log file could not be cleared:\n{ex}", ex=ex))

    def _reload_all(self):
        """Komplette Datei neu laden und anzeigen."""
        self._buffer.clear()
        self._file_pos = 0
        try:
            if os.path.isfile(self._path):
                with open(self._path, "r", encoding="utf-8", errors="ignore") as f:
                    data = f.read()
                self._buffer = data.splitlines()
                self._file_pos = len(data.encode("utf-8", errors="ignore"))
        except Exception:
            pass
        self._render_all()

    def _poll_append(self):
        """Neuen Anhang von der Datei lesen."""
        if self._paused:
            return
        try:
            if not os.path.isfile(self._path):
                return
            with open(self._path, "rb") as f:
                f.seek(self._file_pos)
                chunk = f.read()
                if not chunk:
                    return
                self._file_pos += len(chunk)
                text = chunk.decode("utf-8", errors="ignore")
                new_lines = text.splitlines()
                if not new_lines:
                    return
                self._buffer.extend(new_lines)
                # Nur neue Zeilen reinfiltern und an View anhaengen
                to_add = [ln for ln in new_lines if self._passes_filters(ln)]
                if to_add:
                    cursor = self.view.textCursor()
                    cursor.movePosition(QTextCursor.End)
                    self.view.setTextCursor(cursor)
                    self.view.append("\n".join(to_add))
                    if self.auto_cb.isChecked():
                        cursor = self.view.textCursor()
                        cursor.movePosition(QTextCursor.End)
                        self.view.setTextCursor(cursor)
        except Exception:
            # still sein, Viewer soll robust sein
            pass

    def _on_bridge_line(self, line: str):
        """Live Zeile aus Logger Bridge. Auch in Datei Poll moeglich, daher doppelt egal."""
        if self._paused:
            return
        self._buffer.append(line)
        if self._passes_filters(line):
            cursor = self.view.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.view.setTextCursor(cursor)
            self.view.append(line)
            if self.auto_cb.isChecked():
                cursor = self.view.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.view.setTextCursor(cursor)

    # ---------- Filtern und Rendern ----------
    def _render_all(self):
        filtered = [ln for ln in self._buffer if self._passes_filters(ln)]
        self.view.setPlainText("\n".join(filtered))
        if self.auto_cb.isChecked():
            cursor = self.view.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.view.setTextCursor(cursor)

    def _apply_filters(self):
        self._render_all()

    def _passes_filters(self, line: str) -> bool:
        # Level Filter
        lvl_sel = self.level_combo.currentText().upper()
        if lvl_sel != "ALLE":
            lvl = self._line_level(line)
            # WARNING soll bei Auswahl WARNUNG angezeigt werden
            target = "WARNING" if lvl_sel.startswith("WARN") else lvl_sel
            if lvl != target:
                return False
        # Text Filter
        patt = self.search_edit.text().strip()
        if patt:
            if self.regex_cb.isChecked():
                flags = 0 if self.case_cb.isChecked() else re.IGNORECASE
                try:
                    if not re.search(patt, line, flags=flags):
                        return False
                except re.error:
                    # ungueltige Regex behandelt wie kein Treffer
                    return False
            else:
                hay = line if self.case_cb.isChecked() else line.lower()
                needle = patt if self.case_cb.isChecked() else patt.lower()
                if needle not in hay:
                    return False
        return True

    def _line_level(self, line: str) -> str:
        u = line.upper()
        if '"LEVEL": "DEBUG"' in u or " DEBUG " in u or u.startswith("DEBUG"):
            return "DEBUG"
        if '"LEVEL": "INFO"' in u or " INFO " in u or u.startswith("INFO"):
            return "INFO"
        if '"LEVEL": "WARNING"' in u or " WARNING " in u or u.startswith("WARNING"):
            return "WARNING"
        if '"LEVEL": "ERROR"' in u or " ERROR " in u or u.startswith("ERROR"):
            return "ERROR"
        return "INFO"  # neutrale Vorgabe

    def _apply_translations(self):
        self.setWindowTitle(tr("Logs"))
        self.lbl_level.setText(tr("Level"))
        self.search_edit.setPlaceholderText(tr("Filter text"))
        self.regex_cb.setText(tr("Regex"))
        self.case_cb.setText(tr("Case sensitive"))
        self.auto_cb.setText(tr("Auto Scroll"))
        self.pause_cb.setText(tr("Pause"))
        self.btn_refresh.setText(tr("Reload"))
        self.btn_clear.setText(tr("Clear file"))
        self.btn_open.setText(tr("Open file"))
        self.btn_stats.setText(tr("Log Statistics"))

    def _open_stats_window(self):
        dlg = LogStatsDialog(self._path, self._theme, self)
        dlg.setModal(False)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.show()
