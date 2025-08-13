# modules/ui/log_viewer.py
from __future__ import annotations
import os
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QPlainTextEdit,
    QLineEdit, QLabel, QFileDialog, QMessageBox
)

from modules.utils.logger import read_recent_logs, get_log_bridge, get_log_path

class LogViewer(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Logs")
        self.setMinimumSize(900, 600)

        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText("Filter eingeben")
        self.status = QLabel(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Filter:"))
        top.addWidget(self.filter_edit)

        btns = QHBoxLayout()
        self.btn_pause = QPushButton("Pause", self)
        self.btn_clear = QPushButton("Leeren", self)
        self.btn_open = QPushButton("Ordner oeffnen", self)
        self.btn_copy = QPushButton("Pfad kopieren", self)
        self.btn_close = QPushButton("Schliessen", self)
        btns.addWidget(self.btn_pause)
        btns.addWidget(self.btn_clear)
        btns.addWidget(self.btn_open)
        btns.addWidget(self.btn_copy)
        btns.addStretch(1)
        btns.addWidget(self.btn_close)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.text, 1)
        root.addWidget(self.status)
        root.addLayout(btns)

        self.paused = False
        self._connect()
        self._load_initial()

    def _connect(self):
        self.btn_close.clicked.connect(self.accept)
        self.btn_pause.clicked.connect(self._toggle_pause)
        self.btn_clear.clicked.connect(lambda: self.text.setPlainText(""))
        self.btn_open.clicked.connect(self._open_folder)
        self.btn_copy.clicked.connect(self._copy_path)
        self.filter_edit.textChanged.connect(self._apply_filter)

        bridge = get_log_bridge()
        if bridge is not None:
            bridge.lineEmitted.connect(self._on_line)
        else:
            # Fallback Poller
            self._poller = QTimer(self)
            self._poller.setInterval(1000)
            self._poller.timeout.connect(self._poll_tail)
            self._poller.start()

    def _load_initial(self):
        buf = read_recent_logs(1000)
        self.text.setPlainText(buf)
        self.status.setText(f"{len(buf.splitlines())} Zeilen")

    def _apply_filter(self):
        # einfache Filterung auf dem Memory Buffer
        buf = read_recent_logs(2000)
        q = self.filter_edit.text().strip()
        if not q:
            self.text.setPlainText(buf)
        else:
            lines = [l for l in buf.splitlines() if q.lower() in l.lower()]
            self.text.setPlainText("\n".join(lines))
        self.text.moveCursor(self.text.textCursor().End)

    def _toggle_pause(self):
        self.paused = not self.paused
        self.btn_pause.setText("Fortsetzen" if self.paused else "Pause")

    def _on_line(self, line: str):
        if self.paused:
            return
        q = self.filter_edit.text().strip()
        if q and q.lower() not in line.lower():
            return
        self.text.appendPlainText(line)
        self.status.setText(f"{self.text.blockCount()} Zeilen")
        self.text.moveCursor(self.text.textCursor().End)

    def _poll_tail(self):
        if self.paused:
            return
        self._apply_filter()

    def _open_folder(self):
        path = get_log_path()
        folder = os.path.dirname(path)
        QFileDialog.getOpenFileName(self, "Logdatei", folder, "Log (*.log *.txt);;Alle (*)")

    def _copy_path(self):
        path = get_log_path()
        cb = self.clipboard()
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(path)
            QMessageBox.information(self, "Kopiert", f"Pfad kopiert\n{path}")
        except Exception:
            pass
