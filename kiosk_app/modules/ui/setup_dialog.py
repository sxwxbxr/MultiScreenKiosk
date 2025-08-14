# modules/ui/setup_dialog.py
from __future__ import annotations
from typing import List, Dict, Any, Optional

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QLineEdit, QFileDialog, QScrollArea, QMessageBox,
    QSpinBox, QGridLayout
)

from modules.utils.config_loader import Config, SourceSpec, UIConfig, KioskConfig


class _SourceRow(QWidget):
    """Eine dynamische Zeile fuer eine Quelle."""
    def __init__(self, idx: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.idx = idx

        grid = QGridLayout(self)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        # Name
        grid.addWidget(QLabel("Name"), 0, 0)
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText(f"Quelle {idx+1}")
        grid.addWidget(self.name_edit, 0, 1, 1, 3)

        # Typ
        grid.addWidget(QLabel("Typ"), 1, 0)
        self.type_combo = QComboBox(self)
        self.type_combo.addItems(["browser", "local"])
        self.type_combo.currentTextChanged.connect(self._on_type_change)
        grid.addWidget(self.type_combo, 1, 1)

        # Browser Felder
        self.url_edit = QLineEdit(self)
        self.url_edit.setPlaceholderText("https://example.com")
        grid.addWidget(QLabel("URL"), 2, 0)
        grid.addWidget(self.url_edit, 2, 1, 1, 3)

        # Lokale App Felder
        self.exe_edit = QLineEdit(self)
        self.exe_edit.setPlaceholderText("Pfad zur EXE")
        self.exe_btn = QPushButton("Waehlen", self)
        self.exe_btn.clicked.connect(self._browse_exe)

        self.args_edit = QLineEdit(self)
        self.args_edit.setPlaceholderText("Optionale Argumente zB /safe oder -n 1")

        self.title_edit = QLineEdit(self)
        self.title_edit.setPlaceholderText("Regex zB .*Notepad.*")

        self.class_edit = QLineEdit(self)
        self.class_edit.setPlaceholderText("Regex zB XLMAIN")

        self.child_class_edit = QLineEdit(self)
        self.child_class_edit.setPlaceholderText("Regex fuer Child zB Edit")

        self.allow_global_cb = QCheckBox("Globalen Fallback erlauben", self)
        self.follow_children_cb = QCheckBox("Kindprozesse folgen", self)
        self.follow_children_cb.setChecked(True)

        # Lokale App Zeilen platzieren
        row = 3
        grid.addWidget(QLabel("EXE"), row, 0)
        grid.addWidget(self.exe_edit, row, 1, 1, 2)
        grid.addWidget(self.exe_btn, row, 3)
        row += 1

        grid.addWidget(QLabel("Argumente"), row, 0)
        grid.addWidget(self.args_edit, row, 1, 1, 3)
        row += 1

        grid.addWidget(QLabel("Titel Regex"), row, 0)
        grid.addWidget(self.title_edit, row, 1, 1, 3)
        row += 1

        grid.addWidget(QLabel("Klasse Regex"), row, 0)
        grid.addWidget(self.class_edit, row, 1, 1, 3)
        row += 1

        grid.addWidget(QLabel("Child Klasse Regex"), row, 0)
        grid.addWidget(self.child_class_edit, row, 1, 1, 3)
        row += 1

        grid.addWidget(self.follow_children_cb, row, 1)
        grid.addWidget(self.allow_global_cb, row, 2)
        row += 1

        self._on_type_change(self.type_combo.currentText())

    def _on_type_change(self, typ: str):
        is_browser = typ == "browser"
        # Browser Felder
        self.url_edit.setEnabled(is_browser)
        self.url_edit.setVisible(is_browser)
        # Lokale Felder
        for w in [
            self.exe_edit, self.exe_btn, self.args_edit,
            self.title_edit, self.class_edit, self.child_class_edit,
            self.allow_global_cb, self.follow_children_cb
        ]:
            w.setEnabled(not is_browser)
            w.setVisible(not is_browser)

    def _browse_exe(self):
        path, _ = QFileDialog.getOpenFileName(self, "EXE auswaehlen", "", "Programme (*.exe);;Alle Dateien (*)")
        if path:
            self.exe_edit.setText(path)

    # ---- Daten extrahieren ----
    def to_spec_dict(self) -> Dict[str, Any] | None:
        typ = self.type_combo.currentText().strip().lower()
        name = self.name_edit.text().strip() or f"Quelle {self.idx+1}"

        if typ == "browser":
            url = self.url_edit.text().strip()
            if not url:
                return None
            return {
                "type": "browser",
                "name": name,
                "url": url
            }

        # local
        exe = self.exe_edit.text().strip()
        if not exe:
            return None
        args = self.args_edit.text().strip()
        title = self.title_edit.text().strip()
        klass = self.class_edit.text().strip()
        child_class = self.child_class_edit.text().strip()
        allow_global = bool(self.allow_global_cb.isChecked())
        follow_children = bool(self.follow_children_cb.isChecked())
        return {
            "type": "local",
            "name": name,
            "launch_cmd": exe,
            "args": args,
            "embed_mode": "native_window",
            "window_title_pattern": title or None,
            "window_class_pattern": klass or None,
            "child_window_class_pattern": child_class or None,
            "follow_children": follow_children,
            "allow_global_fallback": allow_global
        }


class SetupDialog(QDialog):
    """
    Einfache Ersteinrichtung mit dynamischer Anzahl an Quellen.
    results() liefert ein dict mit kompletter Config zurueck.
    """
    def __init__(self, cfg: Config, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Ersteinrichtung")
        self.setModal(True)
        self.setMinimumSize(720, 520)

        self._cfg = cfg
        self._rows: List[_SourceRow] = []

        # Header
        header = QWidget(self)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 12, 12, 6)
        hl.addWidget(QLabel("Anzahl Fenster"))
        self.count_spin = QSpinBox(self)
        self.count_spin.setRange(1, 20)
        self.count_spin.setValue(max(1, len(cfg.sources) or 4))
        self.count_spin.valueChanged.connect(self._rebuild_rows)
        hl.addWidget(self.count_spin)
        hl.addStretch(1)

        # Scroll Bereich fuer Zeilen
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self.rows_host = QWidget(scroll)
        self.rows_layout = QVBoxLayout(self.rows_host)
        self.rows_layout.setContentsMargins(8, 8, 8, 8)
        self.rows_layout.setSpacing(6)
        scroll.setWidget(self.rows_host)

        # Footer
        footer = QWidget(self)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(12, 6, 12, 12)

        self.overwrite_cb = QCheckBox("Config ueberschreiben", self)
        self.overwrite_cb.setChecked(True)

        self.cancel_btn = QPushButton("Abbrechen", self)
        self.save_btn = QPushButton("Speichern", self)

        fl.addWidget(self.overwrite_cb)
        fl.addStretch(1)
        fl.addWidget(self.cancel_btn)
        fl.addWidget(self.save_btn)

        # Root
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(header)
        root.addWidget(scroll, 1)
        root.addWidget(footer)

        # Events
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._on_save_clicked)

        # Styling
        self.setStyleSheet("""
            QLabel { font-size: 14px; }
            QLineEdit { padding: 6px 8px; border:1px solid rgba(128,128,128,0.35); border-radius: 8px; }
            QPushButton { padding: 8px 12px; border:1px solid rgba(128,128,128,0.35); border-radius: 10px; }
            QPushButton:hover { border-color: rgba(128,128,128,0.55); }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border:1px solid rgba(128,128,128,0.45); background: rgba(255,255,255,0.03); }
            QCheckBox::indicator:checked { background:#0a84ff; border-color:#0a84ff; }
        """)

        # Reihen initial aufbauen
        self._rebuild_rows(self.count_spin.value())
        # Vorbelegen aus vorhandener Config
        self._prefill_from_cfg(cfg)

        self._result: Dict[str, Any] = {}

    # ------- Aufbau -------

    def _clear_rows(self):
        for r in self._rows:
            r.setParent(None)
            r.deleteLater()
        self._rows.clear()

    def _rebuild_rows(self, n: int):
        self._clear_rows()
        for i in range(n):
            row = _SourceRow(i, self)
            self._rows.append(row)
            self.rows_layout.addWidget(row)
        self.rows_layout.addStretch(1)

    def _prefill_from_cfg(self, cfg: Config):
        if not cfg.sources:
            # Beispiel fuellen
            if self._rows:
                # erste drei Browser
                for i in range(min(3, len(self._rows))):
                    self._rows[i].type_combo.setCurrentText("browser")
                    self._rows[i].name_edit.setText(f"Browser {i+1}")
                    self._rows[i].url_edit.setText("https://www.google.com")
                # ein lokaler Editor
                if len(self._rows) >= 4:
                    r = self._rows[3]
                    r.type_combo.setCurrentText("local")
                    r.name_edit.setText("Editor")
                    r.exe_edit.setText("C:\\Windows\\System32\\notepad.exe")
                    r.title_edit.setText(".*(Notepad|Editor).*")
                    r.child_class_edit.setText("Edit")
            return

        m = min(len(cfg.sources), len(self._rows))
        for i in range(m):
            s = cfg.sources[i]
            r = self._rows[i]
            r.name_edit.setText(s.name or f"Quelle {i+1}")
            if s.type == "browser":
                r.type_combo.setCurrentText("browser")
                r.url_edit.setText(s.url or "")
            else:
                r.type_combo.setCurrentText("local")
                r.exe_edit.setText(s.launch_cmd or "")
                r.args_edit.setText(s.args or "")
                r.title_edit.setText(s.window_title_pattern or "")
                r.class_edit.setText(s.window_class_pattern or "")
                r.child_class_edit.setText(s.child_window_class_pattern or "")
                r.allow_global_cb.setChecked(bool(s.allow_global_fallback))
                r.follow_children_cb.setChecked(bool(s.follow_children))

    # ------- Speichern -------

    def _on_save_clicked(self):
        specs: List[Dict[str, Any]] = []
        for r in self._rows:
            spec = r.to_spec_dict()
            if spec:
                specs.append(spec)

        if not specs:
            QMessageBox.warning(self, "Ungueltig", "Bitte mindestens eine gueltige Quelle angeben.")
            return

        # Minimale neue Config bauen, bestehende UI und Kiosk uebernehmen
        new_cfg: Dict[str, Any] = {
            "sources": specs,
            "ui": {
                "start_mode": self._cfg.ui.start_mode,
                "sidebar_width": self._cfg.ui.sidebar_width,
                "nav_orientation": self._cfg.ui.nav_orientation,
                "show_setup_on_start": False,
                "enable_hamburger": self._cfg.ui.enable_hamburger,
                "placeholder_enabled": self._cfg.ui.placeholder_enabled,
                "placeholder_gif_path": self._cfg.ui.placeholder_gif_path,
                "theme": self._cfg.ui.theme,
                "logo_path": self._cfg.ui.logo_path,
            },
            "kiosk": {
                "monitor_index": self._cfg.kiosk.monitor_index,
                "disable_system_keys": self._cfg.kiosk.disable_system_keys,
                "kiosk_fullscreen": self._cfg.kiosk.kiosk_fullscreen,
            }
        }

        self._result = {
            "config": new_cfg,
            "should_save": bool(self.overwrite_cb.isChecked())
        }
        self.accept()

    def results(self) -> Dict[str, Any]:
        # Rueckgabe immer ein dict:
        # { "config": {...}, "should_save": True|False }
        return self._result or {
            "config": {
                "sources": [],
                "ui": {
                    "start_mode": self._cfg.ui.start_mode,
                    "sidebar_width": self._cfg.ui.sidebar_width,
                    "nav_orientation": self._cfg.ui.nav_orientation,
                    "show_setup_on_start": False,
                    "enable_hamburger": self._cfg.ui.enable_hamburger,
                    "placeholder_enabled": self._cfg.ui.placeholder_enabled,
                    "placeholder_gif_path": self._cfg.ui.placeholder_gif_path,
                    "theme": self._cfg.ui.theme,
                    "logo_path": self._cfg.ui.logo_path,
                },
                "kiosk": {
                    "monitor_index": self._cfg.kiosk.monitor_index,
                    "disable_system_keys": self._cfg.kiosk.disable_system_keys,
                    "kiosk_fullscreen": self._cfg.kiosk.kiosk_fullscreen,
                }
            },
            "should_save": False
        }
