from typing import List, Optional

from PySide6.QtCore import QSize, Qt, QRectF, Signal
from PySide6.QtGui import QPixmap, QPainter, QTransform
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QToolButton, QPushButton,
    QFrame, QSizePolicy, QMenu
)


class RotatableLogoWidget(QWidget):
    """Logo Widget. Dreht das Bild bei Ausrichtung 'left' um 90 Grad.
    Skaliert proportional mit Antialiasing fuer gute Lesbarkeit."""
    def __init__(self, path: str = "", orientation: str = "left", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._pix: Optional[QPixmap] = None
        self._orientation = orientation  # "left" oder "top"
        self.set_logo(path)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_logo(self, path: str):
        self._pix = QPixmap(path) if path else None
        self.updateGeometry()
        self.update()

    def set_orientation(self, orientation: str):
        self._orientation = orientation
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        if self._orientation == "top":
            h = 24
            if self._pix and not self._pix.isNull():
                ar = self._pix.width() / max(1, self._pix.height())
                return QSize(int(h * ar), h)
            return QSize(96, h)
        else:
            w = 48
            if self._pix and not self._pix.isNull():
                ar = self._pix.height() / max(1, self._pix.width())  # wegen Rotation
                return QSize(w, int(max(120, w * ar)))
            return QSize(w, 140)

    def minimumSizeHint(self) -> QSize:
        return QSize(24, 24)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self._pix or self._pix.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        rect = self.rect()

        pix = self._pix
        if self._orientation == "left":
            tr = QTransform()
            tr.rotate(-90)
            pix = self._pix.transformed(tr, Qt.SmoothTransformation)

        margin = 6
        target = QRectF(rect.adjusted(margin, margin, -margin, -margin))
        pr = pix.rect()
        pr_ar = pr.width() / max(1, pr.height())
        tr_ar = target.width() / max(1.0, target.height())

        if pr_ar > tr_ar:
            w = target.width()
            h = w / pr_ar
            x = target.left()
            y = target.top() + (target.height() - h) / 2
        else:
            h = target.height()
            w = h * pr_ar
            x = target.left() + (target.width() - w) / 2
            y = target.top()
        p.drawPixmap(QRectF(x, y, w, h), pix, pix.rect())
        p.end()


class Sidebar(QWidget):
    view_selected = Signal(int)       # globaler Index
    toggle_mode = Signal()
    page_changed = Signal(int)
    request_settings = Signal()
    collapsed_changed = Signal(bool)  # true = eingeklappt

    def __init__(self, titles: List[str], width: int = 96, orientation: str = "left",
                 enable_hamburger: bool = True, logo_path: str = "", split_enabled: bool = True, parent=None):
        super().__init__(parent)
        self._orientation = orientation  # "left" oder "top"
        self._all_titles = titles[:]
        self._thickness = max(64, width)
        self._page = 0
        self._page_size = 4
        self._collapsed = False
        self._enable_hamburger = enable_hamburger
        self._logo_path = logo_path
        self._split_enabled = split_enabled

        self.setObjectName("Sidebar")
        self._build_ui()
        self._refresh_page_buttons()

    # ---------- interne Helfer ----------
    def _divider(self):
        div = QFrame(self)
        div.setFrameShape(QFrame.HLine if self._orientation == "top" else QFrame.VLine)
        div.setFrameShadow(QFrame.Sunken)
        return div

    def _apply_thickness(self):
        """Links feste Breite, Top dynamische Hoehe anhand sizeHint."""
        if self._orientation == "top":
            if self._collapsed:
                h = 40
            else:
                h = max(40, self.sizeHint().height())
            self.setFixedHeight(h)
        else:
            self.setFixedWidth(48 if self._collapsed else self._thickness)

    # ---------- Aufbau ----------
    def _build_ui(self):
        if self._orientation == "top":
            self._build_top_ui()
        else:
            self._build_left_ui()
        self._apply_thickness()

    def _build_top_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        # Zeile 1: Burger | Logo | Stretch | Settings
        header = QHBoxLayout()
        header.setSpacing(6)

        self.btn_burger = QToolButton(self)
        self.btn_burger.setText("☰")
        self.btn_burger.setToolTip("Menue")
        self.btn_burger.clicked.connect(self._on_burger_click)
        self.btn_burger.setVisible(self._enable_hamburger)
        header.addWidget(self.btn_burger)

        self.logo = RotatableLogoWidget(self._logo_path, "top", self)
        self.logo.setFixedHeight(24)
        header.addWidget(self.logo)

        header.addStretch(1)

        self.btn_settings = QToolButton(self)
        self.btn_settings.setText("⚙")
        self.btn_settings.setToolTip("Einstellungen")
        self.btn_settings.clicked.connect(self.request_settings.emit)
        header.addWidget(self.btn_settings)

        root.addLayout(header)

        root.addWidget(self._divider())

        # Zeile 2: Prev | Buttons (breit) | Next
        row_buttons = QHBoxLayout()
        row_buttons.setSpacing(6)

        self.btn_prev = QToolButton(self)
        self.btn_prev.setText("◀")
        self.btn_prev.clicked.connect(self.prev_page)
        row_buttons.addWidget(self.btn_prev)

        self.buttons_wrap = QWidget(self)
        self.buttons_layout = QHBoxLayout(self.buttons_wrap)
        self.buttons_layout.setSpacing(6)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)

        self.buttons: List[QToolButton] = []
        for i in range(self._page_size):
            btn = QToolButton(self.buttons_wrap)
            btn.setText("")
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # gleichmaessige Breite
            btn.clicked.connect(lambda checked, pos=i: self._emit_by_pos(pos))
            self.buttons.append(btn)
            self.buttons_layout.addWidget(btn, 1)  # Stretch=1 fuer gleiches Verteilen
        row_buttons.addWidget(self.buttons_wrap, 1)

        self.btn_next = QToolButton(self)
        self.btn_next.setText("▶")
        self.btn_next.clicked.connect(self.next_page)
        row_buttons.addWidget(self.btn_next)

        root.addLayout(row_buttons)

        # Zeile 3: Switch vollbreit
        self.btn_toggle = QPushButton("Switch", self)
        self.btn_toggle.setToolTip("Strg+Q")
        self.btn_toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_toggle.clicked.connect(self.toggle_mode.emit)
        root.addWidget(self.btn_toggle)
        self.btn_toggle.setVisible(self._split_enabled)

        self._layout = root

    def _build_left_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Kopfzeile
        header = QHBoxLayout()
        header.setSpacing(6)

        self.btn_burger = QToolButton(self)
        self.btn_burger.setText("☰")
        self.btn_burger.setToolTip("Menue")
        self.btn_burger.clicked.connect(self._on_burger_click)
        self.btn_burger.setVisible(self._enable_hamburger)
        header.addWidget(self.btn_burger)

        header.addStretch(1)

        self.btn_settings = QToolButton(self)
        self.btn_settings.setText("⚙")
        self.btn_settings.setToolTip("Einstellungen")
        self.btn_settings.clicked.connect(self.request_settings.emit)
        header.addWidget(self.btn_settings)

        layout.addLayout(header)

        # Pager
        pager = QHBoxLayout()
        pager.setSpacing(4)
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

        # Buttons oberhalb Logo
        layout.addWidget(self._divider())

        self.buttons_wrap = QWidget(self)
        self.buttons_layout = QVBoxLayout(self.buttons_wrap)
        self.buttons_layout.setSpacing(8)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)

        self.buttons: List[QToolButton] = []
        for i in range(self._page_size):
            btn = QToolButton(self.buttons_wrap)
            btn.setText("")                 # nur Name
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked, pos=i: self._emit_by_pos(pos))
            self.buttons.append(btn)
            self.buttons_layout.addWidget(btn)
        layout.addWidget(self.buttons_wrap)

        self.btn_toggle = QPushButton("Switch", self)
        self.btn_toggle.setToolTip("Strg+Q")
        self.btn_toggle.clicked.connect(self.toggle_mode.emit)
        layout.addWidget(self.btn_toggle)
        self.btn_toggle.setVisible(self._split_enabled)

        # Freie Flaeche mit grossem Logo
        layout.addStretch(1)
        self.logo = RotatableLogoWidget(self._logo_path, "left", self)
        self.logo.setMinimumHeight(140)
        layout.addWidget(self.logo, 0, Qt.AlignHCenter)
        layout.addStretch(1)

        self._layout = layout

    # ---------- Burger Logik ----------
    def _on_burger_click(self):
        new_state = not self._collapsed
        self.set_collapsed(new_state)
        self.collapsed_changed.emit(new_state)
        if new_state:
            m = QMenu(self)
            for idx, title in enumerate(self._all_titles):
                act = m.addAction(title)
                act.triggered.connect(lambda _=False, i=idx: self.view_selected.emit(i))
            m.addSeparator()
            act_settings = m.addAction("Einstellungen")
            act_settings.triggered.connect(self.request_settings.emit)
            m.exec(self.mapToGlobal(self.btn_burger.geometry().bottomLeft()))

    def set_collapsed(self, collapsed: bool):
        self._collapsed = collapsed
        # Sichtbarkeit aller variablen Teile
        self.buttons_wrap.setVisible(not collapsed)
        self.btn_prev.setVisible(not collapsed)
        self.btn_next.setVisible(not collapsed)
        self.btn_toggle.setVisible(self._split_enabled and not collapsed)
        if hasattr(self, "logo"):
            self.logo.setVisible(not collapsed)
        self._apply_thickness()
        self.updateGeometry()

    def set_hamburger_enabled(self, enabled: bool):
        self._enable_hamburger = enabled
        self.btn_burger.setVisible(enabled)
        if not enabled and self._collapsed:
            self.set_collapsed(False)
            self.collapsed_changed.emit(False)

    def set_logo(self, path: str):
        self._logo_path = path
        if hasattr(self, "logo"):
            self.logo.set_logo(path)
        self.updateGeometry()

    # ---------- Paging ----------
    def _page_count(self) -> int:
        return max(1, (len(self._all_titles) + self._page_size - 1) // self._page_size)

    def _refresh_page_buttons(self):
        start = self._page * self._page_size
        for i, btn in enumerate(self.buttons):
            idx = start + i
            if idx < len(self._all_titles):
                btn.setText(self._all_titles[idx])
                btn.setEnabled(True)
            else:
                btn.setText("-")
                btn.setEnabled(False)
        if hasattr(self, "btn_prev"):
            self.btn_prev.setEnabled(self._page > 0)
        if hasattr(self, "btn_next"):
            self.btn_next.setEnabled(self._page < self._page_count() - 1)
        self._clear_checks()
        self._apply_thickness()  # Top Hoehe ggf. neu berechnen

    def _clear_checks(self):
        for b in self.buttons:
            b.setChecked(False)

    def _emit_by_pos(self, pos: int):
        if self._collapsed:
            return
        idx = self._page * self._page_size + pos
        if idx < len(self._all_titles):
            self.view_selected.emit(idx)
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

    # ---------- API ----------
    def set_active_global_index(self, idx: int):
        page = idx // self._page_size
        if page != self._page:
            self._page = page
            self._refresh_page_buttons()
        pos = idx % self._page_size
        if 0 <= pos < len(self.buttons) and not self._collapsed:
            self._clear_checks()
            self.buttons[pos].setChecked(True)

    def set_titles(self, titles: List[str]):
        self._all_titles = titles[:]
        self._page = 0
        self._refresh_page_buttons()

    def set_orientation(self, orientation: str):
        # Layout komplett neu aufbauen, da Top und Left stark abweichen
        self._orientation = orientation
        # alles loeschen
        while self.layout() and self.layout().count():
            it = self.layout().takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
        if self.layout():
            self.layout().deleteLater()

        # neu bauen
        self._build_ui()
        # Titel wieder setzen
        self.set_titles(self._all_titles)
        self.updateGeometry()
