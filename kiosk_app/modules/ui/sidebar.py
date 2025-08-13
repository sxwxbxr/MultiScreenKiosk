from typing import List
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QPushButton, QFrame, QSizePolicy
)

class Sidebar(QWidget):
    view_selected = Signal(int)     # globaler Index
    toggle_mode = Signal()
    page_changed = Signal(int)

    def __init__(self, titles: List[str], width: int = 80, orientation: str = "left", parent=None):
        super().__init__(parent)
        self._orientation = orientation
        self._all_titles = titles[:]  # beliebige Laenge
        self._thickness = width
        self._page = 0
        self._page_size = 4
        self.setObjectName("Sidebar")
        self._build_ui()
        self._refresh_page_buttons()

    # ------- UI -------
    def _divider(self):
        div = QFrame(self)
        div.setFrameShape(QFrame.HLine if self._orientation == "top" else QFrame.VLine)
        div.setFrameShadow(QFrame.Sunken)
        return div

    def _build_ui(self):
        if self._orientation == "top":
            self.setFixedHeight(self._thickness)
            layout = QHBoxLayout(self)
        else:
            self.setFixedWidth(self._thickness)
            layout = QVBoxLayout(self)

        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        self._layout = layout

        # Pager Kopf
        pager = QHBoxLayout()
        self.btn_prev = QToolButton(self)
        self.btn_prev.setText("◀")
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next = QToolButton(self)
        self.btn_next.setText("▶")
        self.btn_next.clicked.connect(self.next_page)
        pager.addWidget(self.btn_prev)
        pager.addStretch(1)
        pager.addWidget(self.btn_next)
        layout.addLayout(pager)

        # Vier Buttons fuer aktuelle Seite
        self.buttons: List[QToolButton] = []
        for i in range(self._page_size):
            btn = QToolButton(self)
            btn.setText("")
            btn.setToolTip(f"Strg+{i+1}")
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked, pos=i: self._emit_by_pos(pos))
            self.buttons.append(btn)
            layout.addWidget(btn)

        layout.addWidget(self._divider())

        toggle = QPushButton("Modus wechseln", self)
        toggle.setToolTip("Strg+Q")
        toggle.clicked.connect(self.toggle_mode.emit)
        layout.addWidget(toggle)

        if self._orientation == "left":
            layout.addStretch(1)

    # ------- Paging Logik -------
    def _page_count(self) -> int:
        n = max(1, (len(self._all_titles) + self._page_size - 1) // self._page_size)
        return n

    def _refresh_page_buttons(self):
        start = self._page * self._page_size
        for i, btn in enumerate(self.buttons):
            idx = start + i
            if idx < len(self._all_titles):
                btn.setText(f"{i+1}. {self._all_titles[idx]}")
                btn.setEnabled(True)
                btn.show()
            else:
                btn.setText(f"{i+1}. -")
                btn.setEnabled(False)
                btn.show()
        self.btn_prev.setEnabled(self._page > 0)
        self.btn_next.setEnabled(self._page < self._page_count() - 1)
        self._clear_checks()

    def _clear_checks(self):
        for b in self.buttons:
            b.setChecked(False)

    def _emit_by_pos(self, pos: int):
        idx = self._page * self._page_size + pos
        if idx < len(self._all_titles):
            self.view_selected.emit(idx)
            # Button markieren
            self._clear_checks()
            self.buttons[pos].setChecked(True)

    def next_page(self):
        if self._page < self._page_count() - 1:
            self._page += 1
            self._refresh_page_buttons()
            self.page_changed.emit(self._page)

    def prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._refresh_page_buttons()
            self.page_changed.emit(self._page)

    # ------- API -------
    def set_active_global_index(self, idx: int):
        # setzt die Seite passend und markiert Button
        page = idx // self._page_size
        if page != self._page:
            self._page = page
            self._refresh_page_buttons()
        pos = idx % self._page_size
        if 0 <= pos < len(self.buttons):
            self._clear_checks()
            self.buttons[pos].setChecked(True)

    def set_titles(self, titles: List[str]):
        self._all_titles = titles[:]
        self._page = 0
        self._refresh_page_buttons()
