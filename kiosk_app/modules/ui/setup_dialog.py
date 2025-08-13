# modules/ui/setup_dialog.py
from __future__ import annotations
from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QFileDialog, QCheckBox, QSpinBox, QMessageBox, QGroupBox
)

from modules.utils.config_loader import Config, SourceSpec
from modules.utils.logger import get_logger


class SetupDialog(QDialog):
    """
    Einfacher Setup Dialog:
      - Anzahl Fenster: 2 4 6 8 10
      - pro Fenster: Typ Browser oder Lokal, Name, URL oder Pfad mit Browse, optionale Patterns
      - UI Einstellungen: Ausrichtung, Sidebar Breite, Hamburger, Theme, Startmodus
    Rueckgabe via results() als Dict mit keys "sources" und "ui".
    """

    def __init__(self, cfg: Config, parent: Optional[QWidget] = None):
        super().__init__(parent)  # <-- richtig, parent ist ein QWidget
        self.setWindowTitle("Setup")
        self.setModal(True)
        self.log = get_logger(__name__)
        self.cfg = cfg

        self._rows: List[Dict[str, Any]] = []       # pro Fenster die Widgets
        self._result: Optional[Dict[str, Any]] = None

        root = QVBoxLayout(self)

        # Abschnitt Fenster Anzahl
        top_box = QGroupBox("Fenster")
        top_lay = QHBoxLayout(top_box)
        top_lay.addWidget(QLabel("Anzahl"))
        self.count_combo = QComboBox(self)
        for n in (2, 4, 6, 8, 10):
            self.count_combo.addItem(str(n), n)
        # Vorbelegung aus cfg
        preset = max(2, len(cfg.sources)) if cfg.sources else 2
        if preset not in (2, 4, 6, 8, 10):
            preset = 2
        self.count_combo.setCurrentIndex((preset // 2) - 1)  # 2->0 4->1
        self.count_combo.currentIndexChanged.connect(self._rebuild_rows)
        top_lay.addWidget(self.count_combo)
        top_lay.addStretch(1)
        root.addWidget(top_box)

        # Grid fuer die Fenstertabellen
        self.rows_box = QGroupBox("Quellen konfigurieren")
        self.rows_grid = QGridLayout(self.rows_box)
        self.rows_grid.setColumnStretch(5, 1)
        root.addWidget(self.rows_box, 1)

        # UI Einstellungen
        ui_box = QGroupBox("UI Einstellungen")
        ui_lay = QGridLayout(ui_box)

        ui_lay.addWidget(QLabel("Ausrichtung"), 0, 0)
        self.nav_combo = QComboBox(self)
        self.nav_combo.addItems(["left", "top"])
        self.nav_combo.setCurrentText(self.cfg.ui.nav_orientation or "left")
        ui_lay.addWidget(self.nav_combo, 0, 1)

        ui_lay.addWidget(QLabel("Sidebar Breite"), 0, 2)
        self.sidebar_spin = QSpinBox(self)
        self.sidebar_spin.setRange(48, 400)
        self.sidebar_spin.setValue(int(self.cfg.ui.sidebar_width or 96))
        ui_lay.addWidget(self.sidebar_spin, 0, 3)

        self.hamburger_cb = QCheckBox("Burger Menue erlauben", self)
        self.hamburger_cb.setChecked(bool(self.cfg.ui.enable_hamburger))
        ui_lay.addWidget(self.hamburger_cb, 1, 0, 1, 2)

        ui_lay.addWidget(QLabel("Theme"), 1, 2)
        self.theme_combo = QComboBox(self)
        self.theme_combo.addItems(["light", "dark"])
        self.theme_combo.setCurrentText(self.cfg.ui.theme or "light")
        ui_lay.addWidget(self.theme_combo, 1, 3)

        ui_lay.addWidget(QLabel("Startmodus"), 2, 0)
        self.startmode_combo = QComboBox(self)
        self.startmode_combo.addItems(["single", "quad"])
        self.startmode_combo.setCurrentText(self.cfg.ui.start_mode or "quad")
        ui_lay.addWidget(self.startmode_combo, 2, 1)

        root.addWidget(ui_box)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_cancel = QPushButton("Abbrechen", self)
        self.btn_ok = QPushButton("Speichern", self)
        self.btn_ok.setDefault(True)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_ok)
        root.addLayout(btns)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self.accept)

        # initiale Rows
        self._rebuild_rows()

        # falls cfg bereits Quellen hat, fuellen
        if self.cfg.sources:
            self._apply_from_cfg()

    # ---------- Rows aufbauen ----------
    def _clear_rows(self):
        # Widgets aus dem Grid entfernen
        for i in reversed(range(self.rows_grid.count())):
            item = self.rows_grid.itemAt(i)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self._rows.clear()

    def _rebuild_rows(self):
        self._clear_rows()

        count = int(self.count_combo.currentData())
        # Header
        headers = ["Typ", "Name", "URL", "Pfad", "", "Muster Titel", "Muster Klasse", "nur Muster"]
        for c, h in enumerate(headers):
            lbl = QLabel(f"<b>{h}</b>", self)
            self.rows_grid.addWidget(lbl, 0, c)

        for r in range(1, count + 1):
            row: Dict[str, Any] = {}

            # Typ
            type_combo = QComboBox(self)
            type_combo.addItems(["browser", "local"])
            self.rows_grid.addWidget(type_combo, r, 0)
            row["type"] = type_combo

            # Name
            name_edit = QLineEdit(self)
            name_edit.setPlaceholderText(f"Quelle {r}")
            self.rows_grid.addWidget(name_edit, r, 1)
            row["name"] = name_edit

            # URL
            url_edit = QLineEdit(self)
            url_edit.setPlaceholderText("https://...")
            self.rows_grid.addWidget(url_edit, r, 2)
            row["url"] = url_edit

            # Pfad und Browse
            path_edit = QLineEdit(self)
            path_edit.setPlaceholderText(r"C:\Pfad\zur\App.exe")
            browse = QPushButton("Waehlen", self)

            def _mk_browse(pe: QLineEdit):
                def _do():
                    file, _ = QFileDialog.getOpenFileName(self, "Programm auswaehlen", "", "Programme (*.exe);;Alle Dateien (*)")
                    if file:
                        pe.setText(file)
                return _do

            browse.clicked.connect(_mk_browse(path_edit))
            self.rows_grid.addWidget(path_edit, r, 3)
            self.rows_grid.addWidget(browse, r, 4)
            row["path"] = path_edit
            row["browse"] = browse

            # Patterns
            title_edit = QLineEdit(self)
            title_edit.setPlaceholderText("Regex fuer Fenstertitel")
            class_edit = QLineEdit(self)
            class_edit.setPlaceholderText("Regex fuer Fensterklasse zB XLMAIN")
            self.rows_grid.addWidget(title_edit, r, 5)
            self.rows_grid.addWidget(class_edit, r, 6)
            row["title"] = title_edit
            row["class"] = class_edit

            force_cb = QCheckBox("", self)
            self.rows_grid.addWidget(force_cb, r, 7, alignment=Qt.AlignCenter)
            row["force"] = force_cb

            # Sichtbarkeit initial nach Typ
            def _on_type_change(idx: int, rr=row):
                t = rr["type"].currentText()
                browser = (t == "browser")
                rr["url"].setEnabled(browser)
                rr["path"].setEnabled(not browser)
                rr["browse"].setEnabled(not browser)
            type_combo.currentIndexChanged.connect(_on_type_change)
            _on_type_change(type_combo.currentIndex())

            self._rows.append(row)

    def _apply_from_cfg(self):
        # Fuellt vorhandene Quellen in die Row Widgets
        items = self.cfg.sources[:len(self._rows)]
        for i, spec in enumerate(items):
            r = self._rows[i]
            r["type"].setCurrentText(spec.type or "browser")
            r["name"].setText(spec.name or f"Quelle {i+1}")
            if spec.type == "browser":
                r["url"].setText(spec.url or "")
            else:
                r["path"].setText(spec.launch_cmd or "")
            if getattr(spec, "window_title_pattern", ""):
                r["title"].setText(spec.window_title_pattern)
            if getattr(spec, "window_class_pattern", ""):
                r["class"].setText(spec.window_class_pattern)
            r["force"].setChecked(bool(getattr(spec, "force_pattern_only", False)))

    # ---------- Dialogsteuerung ----------
    def accept(self) -> None:
        # Werte einsammeln bevor das QDialog Objekt zerstoert wird
        try:
            sources: List[SourceSpec] = []
            for r in self._rows:
                typ = r["type"].currentText()
                name = r["name"].text().strip() or "Quelle"
                if typ == "browser":
                    url = r["url"].text().strip()
                    if not url:
                        QMessageBox.warning(self, "Eingabe fehlt", f"Bitte URL fuer {name} angeben")
                        return
                    sources.append(SourceSpec(
                        type="browser", name=name, url=url
                    ))
                else:
                    path = r["path"].text().strip()
                    if not path:
                        QMessageBox.warning(self, "Eingabe fehlt", f"Bitte Pfad fuer {name} auswaehlen")
                        return
                    sources.append(SourceSpec(
                        type="local",
                        name=name,
                        launch_cmd=path,
                        embed_mode="native_window",
                        window_title_pattern=r["title"].text().strip(),
                        window_class_pattern=r["class"].text().strip(),
                        force_pattern_only=bool(r["force"].isChecked()),
                    ))

            ui_block = {
                "nav_orientation": self.nav_combo.currentText(),
                "sidebar_width": int(self.sidebar_spin.value()),
                "enable_hamburger": bool(self.hamburger_cb.isChecked()),
                "theme": self.theme_combo.currentText(),
                "start_mode": self.startmode_combo.currentText(),
            }

            self._result = {"sources": sources, "ui": ui_block}
        except Exception as ex:
            self.log.error("setup collect failed: %s", ex, extra={"source": "setup"})
            QMessageBox.critical(self, "Fehler", f"Fehler beim Sammeln der Eingaben\n{ex}")
            return
        super().accept()

    def results(self) -> Dict[str, Any]:
        # Sicherstellen, dass wir auch ohne accept() etwas liefern
        return self._result or {"sources": [], "ui": {}}
