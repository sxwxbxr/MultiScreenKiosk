# modules/ui/setup_dialog.py
from __future__ import annotations
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QLineEdit, QFileDialog, QScrollArea, QMessageBox,
    QSpinBox, QGridLayout
)

from modules.utils.i18n import tr, i18n


# ---------- Hilfs Widgets ----------

class _SourceRow(QWidget):
    """Dynamische Zeile fuer eine Quelle."""
    def __init__(self, idx: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.idx = idx

        grid = QGridLayout(self)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        # Name
        self.lbl_name = QLabel("", self)
        grid.addWidget(self.lbl_name, 0, 0)
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("")
        grid.addWidget(self.name_edit, 0, 1, 1, 3)

        # Typ
        self.lbl_type = QLabel("", self)
        grid.addWidget(self.lbl_type, 1, 0)
        self.type_combo = QComboBox(self)
        self.type_combo.addItem("", "browser")
        self.type_combo.addItem("", "local")
        self.type_combo.currentIndexChanged.connect(lambda idx: self._on_type_change(self.type_combo.itemData(idx)))
        grid.addWidget(self.type_combo, 1, 1)

        # Browser Felder
        self.url_edit = QLineEdit(self)
        self.url_edit.setPlaceholderText("https://example.com")
        self.lbl_url = QLabel("", self)
        grid.addWidget(self.lbl_url, 2, 0)
        grid.addWidget(self.url_edit, 2, 1, 1, 3)

        # Lokale App Felder
        self.exe_edit = QLineEdit(self)
        self.exe_edit.setPlaceholderText("")
        self.exe_btn = QPushButton("", self)
        self.exe_btn.clicked.connect(self._browse_exe)

        self.args_edit = QLineEdit(self)
        self.args_edit.setPlaceholderText("")

        self.title_edit = QLineEdit(self)
        self.title_edit.setPlaceholderText("")

        self.class_edit = QLineEdit(self)
        self.class_edit.setPlaceholderText("")

        self.child_class_edit = QLineEdit(self)
        self.child_class_edit.setPlaceholderText("")

        self.allow_global_cb = QCheckBox("", self)
        self.follow_children_cb = QCheckBox("", self)
        self.follow_children_cb.setChecked(True)

        row = 3
        self.lbl_exe = QLabel("", self)
        grid.addWidget(self.lbl_exe, row, 0)
        grid.addWidget(self.exe_edit, row, 1, 1, 2)
        grid.addWidget(self.exe_btn, row, 3)
        row += 1

        self.lbl_args = QLabel("", self)
        grid.addWidget(self.lbl_args, row, 0)
        grid.addWidget(self.args_edit, row, 1, 1, 3)
        row += 1

        self.lbl_title = QLabel("", self)
        grid.addWidget(self.lbl_title, row, 0)
        grid.addWidget(self.title_edit, row, 1, 1, 3)
        row += 1

        self.lbl_class = QLabel("", self)
        grid.addWidget(self.lbl_class, row, 0)
        grid.addWidget(self.class_edit, row, 1, 1, 3)
        row += 1

        self.lbl_child_class = QLabel("", self)
        grid.addWidget(self.lbl_child_class, row, 0)
        grid.addWidget(self.child_class_edit, row, 1, 1, 3)
        row += 1

        grid.addWidget(self.follow_children_cb, row, 1)
        grid.addWidget(self.allow_global_cb, row, 2)

        self._on_type_change(self.type_combo.itemData(self.type_combo.currentIndex()))
        i18n.language_changed.connect(lambda _l: self.retranslate_ui())
        self.retranslate_ui()

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
        path, _ = QFileDialog.getOpenFileName(self, tr("Path to EXE"), "", "Programme (*.exe);;Alle Dateien (*)")
        if path:
            self.exe_edit.setText(path)

    def retranslate_ui(self):
        self.lbl_name.setText(tr("Name"))
        self.name_edit.setPlaceholderText(tr("Source {num}", num=self.idx + 1))
        self.lbl_type.setText(tr("Type"))
        self.type_combo.setItemText(0, tr("browser"))
        self.type_combo.setItemText(1, tr("local"))
        self.lbl_url.setText(tr("URL"))
        self.lbl_exe.setText(tr("Path to EXE"))
        self.exe_edit.setPlaceholderText(tr("Path to EXE"))
        self.exe_btn.setText(tr("Browse"))
        self.lbl_args.setText(tr("Arguments"))
        self.args_edit.setPlaceholderText(tr("Arguments"))
        self.lbl_title.setText(tr("Title regex"))
        self.title_edit.setPlaceholderText(tr("Title regex"))
        self.lbl_class.setText(tr("Class regex"))
        self.class_edit.setPlaceholderText(tr("Class regex"))
        self.lbl_child_class.setText(tr("Child class regex"))
        self.child_class_edit.setPlaceholderText(tr("Child class regex"))
        self.allow_global_cb.setText(tr("Allow global fallback"))
        self.follow_children_cb.setText(tr("Follow child processes"))

    def to_spec_dict(self) -> Dict[str, Any] | None:
        """Extrahiert die Zeile als SourceSpec dict oder None wenn unvollstaendig."""
        typ = (self.type_combo.currentData() or "browser").strip().lower()
        name = self.name_edit.text().strip() or tr("Source {num}", num=self.idx+1)

        if typ == "browser":
            url = self.url_edit.text().strip()
            if not url:
                return None
            return {
                "type": "browser",
                "name": name,
                "url": url
            }

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


# ---------- Setup Dialog ----------

class SetupDialog(QDialog):
    """
    Ersteinrichtung mit dynamischer Anzahl Quellen.
    results() gibt ein dict zurueck:
      { "config": { .. komplette config .. }, "should_save": bool }
    """
    def __init__(self, cfg, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("")
        self.setModal(True)
        self.setMinimumSize(760, 560)

        self._cfg = cfg
        self._rows: List[_SourceRow] = []

        # Theme aus aktueller App Config uebernehmen
        theme = self._extract_theme_from_cfg(cfg)
        self.apply_theme(theme)

        # Header
        header = QWidget(self)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 12, 12, 6)
        self.lbl_count = QLabel("", self)
        hl.addWidget(self.lbl_count)
        self.count_spin = QSpinBox(self)
        self.count_spin.setRange(1, 20)
        initial_count = 4
        try:
            initial_count = max(1, len(getattr(cfg, "sources", []) or [])) or 4
        except Exception:
            initial_count = 4
        self.count_spin.setValue(initial_count)
        self.count_spin.valueChanged.connect(self._rebuild_rows)
        hl.addWidget(self.count_spin)

        self.split_cb = QCheckBox("", self)
        self.split_cb.setChecked(True)
        hl.addWidget(self.split_cb)
        hl.addStretch(1)

        # Scrollbereich
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

        self.overwrite_cb = QCheckBox("", self)
        self.overwrite_cb.setChecked(True)

        self.cancel_btn = QPushButton("", self)
        self.save_btn = QPushButton("", self)

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

        # Reihen aufbauen und vorbelegen
        self._rebuild_rows(self.count_spin.value())
        self._prefill_from_cfg(cfg)

        self._result: Dict[str, Any] = {}

        i18n.language_changed.connect(lambda _l: self._apply_translations())
        self._apply_translations()

    # -------- Theme --------

    def _extract_theme_from_cfg(self, cfg) -> str:
        """Liest 'light' oder 'dark' robust aus cfg."""
        # cfg kann ein Objekt oder dict sein
        try:
            ui = getattr(cfg, "ui", None)
            if ui is not None:
                val = getattr(ui, "theme", None)
                if val:
                    return str(val)
        except Exception:
            pass
        try:
            val = cfg.get("ui", {}).get("theme")
            if val:
                return str(val)
        except Exception:
            pass
        return "light"

    def apply_theme(self, theme: str):
        """Einfaches hell/dunkel Styling, analog zur Hauptapp."""
        if str(theme).lower() == "dark":
            self.setStyleSheet("""
                QWidget { background: #121212; color: #e0e0e0; }
                QLineEdit, QComboBox { background: #1b1b1b; border: 1px solid #2a2a2a; padding: 6px 8px; border-radius: 8px; }
                QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #5a5a5a; background: #2a2a2a; }
                QCheckBox::indicator:checked { background: #3b82f6; border: 1px solid #3b82f6; }
                QPushButton { background: #1f1f1f; border: 1px solid #2a2a2a; padding: 8px 12px; border-radius: 10px; }
                QPushButton:hover { border-color: #3a3a3a; }
            """)
        else:
            self.setStyleSheet("""
                QWidget { background: #f4f4f4; color: #202020; }
                QLineEdit, QComboBox { background: #ffffff; border: 1px solid #d0d0d0; padding: 6px 8px; border-radius: 8px; }
                QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #999; background: #fff; }
                QCheckBox::indicator:checked { background: #0078d4; border: 1px solid #0078d4; }
                QPushButton { background: #ffffff; border: 1px solid #d0d0d0; padding: 8px 12px; border-radius: 10px; }
                QPushButton:hover { border-color: #bcbcbc; }
            """)

    # -------- Layout Zeilen --------

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
        self._apply_translations()

    def _prefill_from_cfg(self, cfg):
        try:
            ui = getattr(cfg, "ui", None)
            val = getattr(ui, "split_enabled", True) if ui is not None else True
        except Exception:
            try:
                val = cfg.get("ui", {}).get("split_enabled", True)
            except Exception:
                val = True
        self.split_cb.setChecked(bool(val))

        sources = getattr(cfg, "sources", []) or []
        try:
            # falls dict
            if not sources and isinstance(cfg, dict):
                sources = cfg.get("sources", []) or []
        except Exception:
            pass

        if not sources:
            # Defaults fuellen
            if self._rows:
                # erste drei Browser
                for i in range(min(3, len(self._rows))):
                    self._rows[i].type_combo.setCurrentIndex(0)
                    self._rows[i].name_edit.setText(f"{tr('browser').capitalize()} {i+1}")
                    self._rows[i].url_edit.setText("https://www.google.com")
                # ein lokaler Editor
                if len(self._rows) >= 4:
                    r = self._rows[3]
                    r.type_combo.setCurrentIndex(1)
                    r.name_edit.setText(tr('local').capitalize())
                    r.exe_edit.setText("C:\\Windows\\System32\\notepad.exe")
                    r.title_edit.setText(".*(Notepad|Editor).*")
                    r.child_class_edit.setText("Edit")
            return

        m = min(len(sources), len(self._rows))
        for i in range(m):
            try:
                s = sources[i]
                # s kann ein Objekt oder Dict sein
                s_type = getattr(s, "type", None) or s.get("type", "browser")
                s_name = getattr(s, "name", None) or s.get("name", f"Quelle {i+1}")
                r = self._rows[i]
                r.name_edit.setText(s_name)
                if s_type == "browser":
                    r.type_combo.setCurrentIndex(0)
                    url = getattr(s, "url", None) or s.get("url", "")
                    r.url_edit.setText(url)
                else:
                    r.type_combo.setCurrentIndex(1)
                    r.exe_edit.setText(getattr(s, "launch_cmd", None) or s.get("launch_cmd", ""))
                    r.args_edit.setText(getattr(s, "args", None) or s.get("args", ""))
                    r.title_edit.setText(getattr(s, "window_title_pattern", None) or s.get("window_title_pattern", "") or "")
                    r.class_edit.setText(getattr(s, "window_class_pattern", None) or s.get("window_class_pattern", "") or "")
                    r.child_class_edit.setText(getattr(s, "child_window_class_pattern", None) or s.get("child_window_class_pattern", "") or "")
                    r.allow_global_cb.setChecked(bool(getattr(s, "allow_global_fallback", None) or s.get("allow_global_fallback", False)))
                    r.follow_children_cb.setChecked(bool(getattr(s, "follow_children", None) or s.get("follow_children", True)))
            except Exception:
                continue

    def _apply_translations(self):
        self.setWindowTitle(tr("Initial setup"))
        self.lbl_count.setText(tr("Number of windows"))
        self.split_cb.setText(tr("Split screen active"))
        self.overwrite_cb.setText(tr("Overwrite config"))
        self.cancel_btn.setText(tr("Cancel"))
        self.save_btn.setText(tr("Save"))
        for r in self._rows:
            try:
                r.retranslate_ui()
            except Exception:
                pass

    # -------- Speichern --------

    def _on_save_clicked(self):
        specs: List[Dict[str, Any]] = []
        for r in self._rows:
            spec = r.to_spec_dict()
            if spec:
                specs.append(spec)

        if not specs:
            QMessageBox.warning(self, tr("Invalid"), tr("Please provide at least one valid source."))
            return

        # Aktuelle UI und Kiosk Werte aus cfg lesen, robust gegen Dict oder Objekt
        ui = getattr(self._cfg, "ui", None) or {}
        kiosk = getattr(self._cfg, "kiosk", None) or {}

        def _get(section, key, default):
            try:
                return getattr(section, key)
            except Exception:
                try:
                    return section.get(key, default)
                except Exception:
                    return default

        new_cfg: Dict[str, Any] = {
            "sources": specs,
            "ui": {
                "start_mode": "quad" if self.split_cb.isChecked() else "single",
                "split_enabled": bool(self.split_cb.isChecked()),
                "sidebar_width": _get(ui, "sidebar_width", 96),
                "nav_orientation": _get(ui, "nav_orientation", "left"),
                "show_setup_on_start": False,
                "enable_hamburger": _get(ui, "enable_hamburger", True),
                "placeholder_enabled": _get(ui, "placeholder_enabled", True),
                "placeholder_gif_path": _get(ui, "placeholder_gif_path", ""),
                "theme": _get(ui, "theme", "light"),
                "logo_path": _get(ui, "logo_path", "")
            },
            "kiosk": {
                "monitor_index": _get(kiosk, "monitor_index", 0),
                "disable_system_keys": _get(kiosk, "disable_system_keys", True),
                "kiosk_fullscreen": _get(kiosk, "kiosk_fullscreen", True)
            }
        }

        self._result = {
            "config": new_cfg,
            "should_save": bool(self.overwrite_cb.isChecked())
        }
        self.accept()

    def results(self) -> Dict[str, Any]:
        # Rueckgabeformat immer gleich
        return self._result or {"config": {"sources": []}, "should_save": False}
