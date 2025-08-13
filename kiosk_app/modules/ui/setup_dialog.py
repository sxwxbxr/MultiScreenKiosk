from __future__ import annotations

import os
import re
from typing import List, Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QComboBox, QCheckBox, QWidget, QMessageBox, QScrollArea
)


class SetupDialog(QDialog):
    """
    Dynamische Setup UI:
    - Anzahl Fenster: 2,4,6,8,10,...
    - Pro Fenster: Typ (Browser/Lokal), Name, URL bzw. EXE und Titel Regex
    - Orientierung: left oder top
    - Optional: Speichern in config.json
    """

    COUNT_CHOICES = [2, 4, 6, 8, 10]

    def __init__(self, parent=None, initial_urls: List[str] | None = None, initial_local_cmd: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Kiosk Setup")
        self.setModal(True)

        self._result_data: dict | None = None
        self.initial_urls = initial_urls or []
        self.initial_local_cmd = initial_local_cmd or ""

        self._build_ui()
        self._rebuild_rows()

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Kopf: Anzahl und Orientierung
        head = QHBoxLayout()
        head.addWidget(QLabel("Anzahl Fenster:", self))
        self.cb_count = QComboBox(self)
        for n in self.COUNT_CHOICES:
            self.cb_count.addItem(str(n), n)
        self.cb_count.currentIndexChanged.connect(self._rebuild_rows)
        head.addWidget(self.cb_count)

        head.addSpacing(20)
        head.addWidget(QLabel("Navigation:", self))
        self.cb_orient = QComboBox(self)
        self.cb_orient.addItems(["left", "top"])
        head.addWidget(self.cb_orient)
        head.addStretch(1)
        root.addLayout(head)

        # Scrollbarer Bereich fuer Fensterzeilen
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.rows_wrap = QWidget(self.scroll)
        self.rows_layout = QGridLayout(self.rows_wrap)
        self.rows_layout.setContentsMargins(8, 8, 8, 8)
        self.rows_layout.setHorizontalSpacing(8)
        self.rows_layout.setVerticalSpacing(6)
        self.scroll.setWidget(self.rows_wrap)
        root.addWidget(self.scroll, 1)

        # Optionen
        opt_row = QHBoxLayout()
        self.cb_save = QCheckBox("Beim Bestaetigen in config.json speichern", self)
        opt_row.addWidget(self.cb_save)
        opt_row.addStretch(1)
        root.addLayout(opt_row)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch(1)
        b_cancel = QPushButton("Abbrechen", self)
        b_ok = QPushButton("Bestaetigen", self)
        b_cancel.clicked.connect(self.reject)
        b_ok.clicked.connect(self._on_accept)
        btns.addWidget(b_cancel)
        btns.addWidget(b_ok)
        root.addLayout(btns)

    def _clear_rows(self):
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _rebuild_rows(self):
        self._clear_rows()
        count = self.cb_count.currentData(Qt.UserRole)
        if count is None:
            count = int(self.cb_count.currentText())

        headers = ["#", "Typ", "Name", "URL", "Exe", "Titel Regex", ""]
        for c, h in enumerate(headers):
            lab = QLabel(f"<b>{h}</b>", self.rows_wrap)
            self.rows_layout.addWidget(lab, 0, c)

        self.row_widgets: List[Dict[str, Any]] = []

        for i in range(count):
            row = {}
            r = i + 1  # Zeilenindex 1-basiert wegen Header

            # Index
            idx_lab = QLabel(str(i + 1), self.rows_wrap)
            self.rows_layout.addWidget(idx_lab, r, 0)

            # Typ
            cb_type = QComboBox(self.rows_wrap)
            cb_type.addItems(["browser", "local"])
            self.rows_layout.addWidget(cb_type, r, 1)
            row["type"] = cb_type

            # Name
            name_edit = QLineEdit(self.rows_wrap)
            # Default Name
            default_name = f"Browser {i+1}" if i < len(self.initial_urls) else "Lokal" if i == len(self.initial_urls) else f"Quelle {i+1}"
            name_edit.setText(default_name)
            self.rows_layout.addWidget(name_edit, r, 2)
            row["name"] = name_edit

            # URL
            url_edit = QLineEdit(self.rows_wrap)
            if i < len(self.initial_urls):
                url_edit.setText(self.initial_urls[i])
            self.rows_layout.addWidget(url_edit, r, 3)
            row["url"] = url_edit

            # Exe + Browse
            exe_wrap = QHBoxLayout()
            exe_edit = QLineEdit(self.initial_local_cmd, self.rows_wrap)
            exe_btn = QPushButton("...", self.rows_wrap)
            exe_btn.setFixedWidth(32)
            def _mk_browse(target_edit=exe_edit):
                def _browse():
                    path, _ = QFileDialog.getOpenFileName(
                        self, "Programm waehlen",
                        os.environ.get("ProgramFiles", "C:\\"),
                        "Programme (*.exe);;Alle Dateien (*.*)"
                    )
                    if path:
                        target_edit.setText(path)
                return _browse
            exe_btn.clicked.connect(_mk_browse(exe_edit))
            exe_w = QWidget(self.rows_wrap)
            hl = QHBoxLayout(exe_w)
            hl.setContentsMargins(0,0,0,0)
            hl.setSpacing(4)
            hl.addWidget(exe_edit, 1)
            hl.addWidget(exe_btn)
            self.rows_layout.addWidget(exe_w, r, 4)
            row["exe"] = exe_edit

            # Titel Regex
            title_edit = QLineEdit(self.rows_wrap)
            self.rows_layout.addWidget(title_edit, r, 5)
            row["title"] = title_edit

            # Aktivierungslogik
            def _apply_enable(_cb=cb_type, _url=url_edit, _exe=exe_edit, _title=title_edit):
                t = _cb.currentText()
                is_browser = t == "browser"
                _url.setEnabled(is_browser)
                _exe.setEnabled(not is_browser)
                _title.setEnabled(not is_browser)
            cb_type.currentIndexChanged.connect(lambda _=None, f=_apply_enable: f())
            _apply_enable()

            self.row_widgets.append(row)

        # Stretch in letzter Spalte
        self.rows_layout.setColumnStretch(2, 1)
        self.rows_layout.setColumnStretch(3, 2)
        self.rows_layout.setColumnStretch(4, 2)
        self.rows_layout.setColumnStretch(5, 2)

    # ---------- Sammeln und Validieren ----------
    def _collect(self) -> dict:
        sources = []
        for row in self.row_widgets:
            typ = row["type"].currentText()
            name = row["name"].text().strip() or "Quelle"
            if typ == "browser":
                url = row["url"].text().strip()
                sources.append({
                    "type": "browser",
                    "name": name,
                    "url": url
                })
            else:
                exe = row["exe"].text().strip()
                title = row["title"].text().strip()
                # fallback regex aus exe name
                if not title and exe:
                    base = os.path.splitext(os.path.basename(exe))[0]
                    title = f".*{re.escape(base)}.*"
                sources.append({
                    "type": "local",
                    "name": name,
                    "launch_cmd": exe,
                    "window_title_pattern": title
                })
        return {
            "sources": sources,
            "orientation": self.cb_orient.currentText(),
            "save_to_file": self.cb_save.isChecked(),
        }

    def _on_accept(self):
        # Validierung
        rows = self._collect()["sources"]
        if len(rows) < 2:
            QMessageBox.warning(self, "Hinweis", "Bitte mindestens zwei Fenster konfigurieren.")
            return

        # Alle Browser URLs pruefen
        for s in rows:
            if s["type"] == "browser":
                u = s.get("url", "")
                if not u or not u.startswith("http"):
                    QMessageBox.warning(self, "Hinweis", "Bitte gueltige Browser Adressen (http oder https) eintragen.")
                    return
            else:
                if not s.get("launch_cmd"):
                    QMessageBox.warning(self, "Hinweis", "Bitte Exe fuer lokale Fenster auswaehlen.")
                    return
        self._result_data = {
            **self._collect()
        }
        self.accept()

    def results(self) -> dict:
        return self._result_data if self._result_data is not None else self._collect()
