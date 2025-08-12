from typing import Callable, List
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFrame, QToolButton, QSizePolicy

class Sidebar(QWidget):
    view_selected = Signal(int)
    toggle_mode = Signal()

    def __init__(self, titles: List[str], width: int = 80, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(width)
        self._build_ui(titles)

    def _build_ui(self, titles: List[str]):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        self.buttons: List[QToolButton] = []
        for i, title in enumerate(titles):
            btn = QToolButton(self)
            btn.setText(f"{i+1}. {title}")
            btn.setToolTip(f"Strg+{i+1}")
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked, idx=i: self.view_selected.emit(idx))
            self.buttons.append(btn)
            layout.addWidget(btn)

        layout.addWidget(self._divider())

        toggle = QPushButton("Modus wechseln", self)
        toggle.setToolTip("Strg+Q")
        toggle.clicked.connect(self.toggle_mode.emit)
        layout.addWidget(toggle)
        layout.addStretch(1)

    def _divider(self):
        div = QFrame(self)
        div.setFrameShape(QFrame.HLine)
        div.setFrameShadow(QFrame.Sunken)
        return div

    def set_active(self, idx: int):
        for i, b in enumerate(self.buttons):
            b.setChecked(i == idx)
