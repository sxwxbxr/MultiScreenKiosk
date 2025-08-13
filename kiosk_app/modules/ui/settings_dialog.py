from __future__ import annotations
import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QLineEdit,
    QPushButton, QFileDialog, QMessageBox
)

class SettingsDialog(QDialog):
    def __init__(self,
                 nav_orientation: str,
                 enable_hamburger: bool,
                 placeholder_enabled: bool,
                 placeholder_gif_path: str,
                 theme: str,
                 logo_path: str,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setModal(True)
        self._quit_requested = False
        self._build_ui(nav_orientation, enable_hamburger, placeholder_enabled, placeholder_gif_path, theme, logo_path)

    def _build_ui(self, nav_orientation, enable_hamburger, placeholder_enabled, placeholder_gif_path, theme, logo_path):
        root = QVBoxLayout(self)
        root.setContentsMargins(12,12,12,12)
        root.setSpacing(10)

        row_theme = QHBoxLayout()
        row_theme.addWidget(QLabel("Farbschema:", self))
        self.cb_theme = QComboBox(self)
        self.cb_theme.addItems(["dark", "light"])
        self.cb_theme.setCurrentText(theme)
        row_theme.addWidget(self.cb_theme)
        root.addLayout(row_theme)

        row_or = QHBoxLayout()
        row_or.addWidget(QLabel("Sidebarausrichtung:", self))
        self.cb_orient = QComboBox(self)
        self.cb_orient.addItems(["left", "top"])
        self.cb_orient.setCurrentText(nav_orientation)
        row_or.addWidget(self.cb_orient)
        root.addLayout(row_or)

        self.cb_hamburger = QCheckBox("Burgermenue aktivieren", self)
        self.cb_hamburger.setChecked(enable_hamburger)
        root.addWidget(self.cb_hamburger)

        self.cb_placeholder = QCheckBox("Platzhalter fuer Browser anzeigen", self)
        self.cb_placeholder.setChecked(placeholder_enabled)
        root.addWidget(self.cb_placeholder)

        row_gif = QHBoxLayout()
        row_gif.addWidget(QLabel("Platzhalter GIF:", self))
        self.le_gif = QLineEdit(placeholder_gif_path, self)
        btn_gif = QPushButton("...", self)
        btn_gif.setFixedWidth(32)
        btn_gif.clicked.connect(self._pick_gif)
        row_gif.addWidget(self.le_gif, 1)
        row_gif.addWidget(btn_gif)
        root.addLayout(row_gif)

        row_logo = QHBoxLayout()
        row_logo.addWidget(QLabel("Logo Bild:", self))
        self.le_logo = QLineEdit(logo_path, self)
        btn_logo = QPushButton("...", self)
        btn_logo.setFixedWidth(32)
        btn_logo.clicked.connect(self._pick_logo)
        row_logo.addWidget(self.le_logo, 1)
        row_logo.addWidget(btn_logo)
        root.addLayout(row_logo)

        # Buttons
        row_btn = QHBoxLayout()
        row_btn.addStretch(1)
        b_quit = QPushButton("Beenden", self)
        b_cancel = QPushButton("Abbrechen", self)
        b_ok = QPushButton("Uebernehmen", self)
        b_quit.clicked.connect(self._confirm_quit)
        b_cancel.clicked.connect(self.reject)
        b_ok.clicked.connect(self.accept)
        row_btn.addWidget(b_quit)
        row_btn.addWidget(b_cancel)
        row_btn.addWidget(b_ok)
        root.addLayout(row_btn)

    def _pick_gif(self):
        path, _ = QFileDialog.getOpenFileName(self, "GIF waehlen", os.getcwd(), "GIF (*.gif);;Alle Dateien (*.*)")
        if path:
            self.le_gif.setText(path)

    def _pick_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Logo waehlen", os.getcwd(), "Bilder (*.png *.jpg *.jpeg *.bmp *.gif);;Alle Dateien (*.*)")
        if path:
            self.le_logo.setText(path)

    def _confirm_quit(self):
        res = QMessageBox.question(
            self,
            "Beenden",
            "Kiosk Anwendung wirklich beenden",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if res == QMessageBox.Yes:
            # zweite Rueckfrage
            res2 = QMessageBox.question(
                self,
                "Bestaetigung",
                "Sicher beenden",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if res2 == QMessageBox.Yes:
                self._quit_requested = True
                self.accept()

    def results(self) -> dict:
        return {
            "theme": self.cb_theme.currentText(),
            "nav_orientation": self.cb_orient.currentText(),
            "enable_hamburger": self.cb_hamburger.isChecked(),
            "placeholder_enabled": self.cb_placeholder.isChecked(),
            "placeholder_gif_path": self.le_gif.text().strip(),
            "logo_path": self.le_logo.text().strip(),
            "quit_requested": self._quit_requested,
        }
