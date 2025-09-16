from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QStyle,
)

from modules.ui.theme import ThemePalette
from modules.utils.i18n import tr, i18n


class Sidebar(QFrame):
    """Modern navigation rail with paging support."""

    view_selected = Signal(int)
    toggle_mode = Signal()
    page_changed = Signal(int)
    request_settings = Signal()
    collapsed_changed = Signal(bool)

    def __init__(
        self,
        titles: List[str],
        width: int = 96,
        orientation: str = "left",
        enable_hamburger: bool = True,
        logo_path: str = "",
        split_enabled: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("NavigationPanel")

        self._orientation = orientation if orientation in {"left", "top"} else "left"
        self._all_titles = titles[:]
        self._base_width = max(160, width)
        self._thickness = self._base_width
        self._page = 0
        self._page_size = 4
        self._collapsed = False
        self._enable_hamburger = enable_hamburger
        self._logo_path = logo_path
        self._split_enabled = split_enabled
        self._palette: Optional[ThemePalette] = None
        self._active_index = 0
        self._suppress_selection_signal = False

        self._build_ui()
        self.set_titles(self._all_titles)
        self._apply_thickness()

        i18n.language_changed.connect(lambda _l: self.retranslate_ui())
        self.retranslate_ui()

    # ------------------------------------------------------------------ UI
    def _clear_layout(self) -> None:
        layout = self.layout()
        if not layout:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        layout.deleteLater()

    def _build_ui(self) -> None:
        self._clear_layout()

        self.setProperty("orientation", self._orientation)

        margins = (18, 24, 18, 18) if self._orientation == "left" else (24, 16, 24, 12)
        spacing = 18 if self._orientation == "left" else 12

        root = QVBoxLayout(self)
        root.setContentsMargins(*margins)
        root.setSpacing(spacing)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)

        self.btn_burger = QToolButton(self)
        self.btn_burger.setObjectName("NavBurger")
        self.btn_burger.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMenuButton))
        self.btn_burger.setIconSize(QSize(18, 18))
        self.btn_burger.clicked.connect(self._on_burger_click)
        self.btn_burger.setVisible(self._enable_hamburger)
        header.addWidget(self.btn_burger)

        self.logo_label = QLabel(self)
        self.logo_label.setObjectName("NavLogo")
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setFixedSize(QSize(48, 48))
        header.addWidget(self.logo_label, 0)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(4)

        self.caption_label = QLabel("", self)
        self.caption_label.setObjectName("NavCaption")
        text_box.addWidget(self.caption_label)

        self.subtitle_label = QLabel("", self)
        self.subtitle_label.setObjectName("NavSubtitle")
        self.subtitle_label.setWordWrap(True)
        text_box.addWidget(self.subtitle_label)

        header.addLayout(text_box, 1)
        root.addLayout(header)

        self.list_widget = QListWidget(self)
        self.list_widget.setObjectName("NavigationList")
        self.list_widget.setFrameShape(QFrame.NoFrame)
        self.list_widget.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self.list_widget, 1)

        self.empty_label = QLabel("", self)
        self.empty_label.setObjectName("NavEmpty")
        self.empty_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.empty_label, 1)

        self.page_widget = QWidget(self)
        page_layout = QHBoxLayout(self.page_widget)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(8)

        self.btn_prev = QToolButton(self.page_widget)
        self.btn_prev.setObjectName("PageButton")
        self.btn_prev.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.btn_prev.clicked.connect(self.prev_page)
        page_layout.addWidget(self.btn_prev)

        self.page_label = QLabel("", self.page_widget)
        self.page_label.setAlignment(Qt.AlignCenter)
        page_layout.addWidget(self.page_label, 1)

        self.btn_next = QToolButton(self.page_widget)
        self.btn_next.setObjectName("PageButton")
        self.btn_next.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.btn_next.clicked.connect(self.next_page)
        page_layout.addWidget(self.btn_next)

        root.addWidget(self.page_widget)

        bottom = QVBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(10)

        self.btn_toggle = QPushButton("", self)
        self.btn_toggle.setProperty("accent", True)
        self.btn_toggle.clicked.connect(self.toggle_mode.emit)
        self.btn_toggle.setVisible(self._split_enabled)
        bottom.addWidget(self.btn_toggle)

        self.btn_settings = QPushButton("", self)
        self.btn_settings.clicked.connect(self.request_settings.emit)
        bottom.addWidget(self.btn_settings)

        root.addLayout(bottom)

        self._apply_orientation_rules()
        self._update_logo()
        self._update_empty_state()
        self._recalculate_thickness()

    def _apply_orientation_rules(self) -> None:
        if self._orientation == "top":
            self.list_widget.setFlow(QListWidget.LeftToRight)
            self.list_widget.setWrapping(True)
            self.list_widget.setSpacing(6)
            self.list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.list_widget.setFixedHeight(110)
        else:
            self.list_widget.setFlow(QListWidget.TopToBottom)
            self.list_widget.setWrapping(False)
            self.list_widget.setSpacing(2)
            self.list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.list_widget.setMaximumHeight(16777215)

    # ---------------------------------------------------------------- config
    def set_titles(self, titles: List[str]) -> None:
        self._all_titles = titles[:]
        self._page = min(self._page, max(0, self.page_count() - 1))

        self._suppress_selection_signal = True
        try:
            self.list_widget.clear()
            for title in self._all_titles:
                item = QListWidgetItem(title)
                item.setSizeHint(QSize(-1, 46))
                self.list_widget.addItem(item)
        finally:
            self._suppress_selection_signal = False

        if self._all_titles:
            target = min(self._active_index, len(self._all_titles) - 1)
            self.set_active_global_index(max(0, target))
        else:
            self._active_index = 0
            self._page = 0
            self.list_widget.clearSelection()

        self._update_logo()
        self._update_page_controls()
        self._update_empty_state()
        self._recalculate_thickness()

    def set_orientation(self, orientation: str) -> None:
        orientation = orientation if orientation in {"left", "top"} else "left"
        if orientation == self._orientation:
            return
        current = self._active_index
        was_collapsed = self._collapsed
        self._orientation = orientation
        self._build_ui()
        self.set_titles(self._all_titles)
        self.set_active_global_index(current)
        self.set_collapsed(was_collapsed)
        self._apply_thickness()
        self._recalculate_thickness()

    def set_hamburger_enabled(self, enabled: bool) -> None:
        self._enable_hamburger = enabled
        if hasattr(self, "btn_burger"):
            self.btn_burger.setVisible(enabled)
        if not enabled and self._collapsed:
            self.set_collapsed(False)
            self.collapsed_changed.emit(False)

    def set_logo(self, path: str) -> None:
        self._logo_path = path
        self._update_logo()

    def apply_palette(self, palette: ThemePalette) -> None:
        self._palette = palette
        self._update_logo()
        self._update_empty_state()

    # ---------------------------------------------------------------- state
    def page_count(self) -> int:
        if not self._all_titles:
            return 1
        return (len(self._all_titles) + self._page_size - 1) // self._page_size

    def set_active_global_index(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._all_titles):
            self._active_index = max(0, min(len(self._all_titles) - 1, idx))
        else:
            self._active_index = idx

        target_page = 0 if len(self._all_titles) == 0 else self._active_index // self._page_size
        if target_page != self._page:
            self._page = target_page
            self._update_page_controls()

        self._suppress_selection_signal = True
        try:
            if 0 <= self._active_index < self.list_widget.count():
                self.list_widget.setCurrentRow(self._active_index)
                item = self.list_widget.item(self._active_index)
                if item:
                    self.list_widget.scrollToItem(item, QAbstractItemView.PositionAtCenter)
            else:
                self.list_widget.clearSelection()
        finally:
            self._suppress_selection_signal = False

        self._update_page_controls()
        self._update_empty_state()

    def next_page(self) -> None:
        if self._page >= self.page_count() - 1:
            return
        self._page += 1
        start = self._page * self._page_size
        if start < len(self._all_titles):
            self.set_active_global_index(start)
            self.view_selected.emit(start)
        self._update_page_controls()
        self.page_changed.emit(self._page)

    def prev_page(self) -> None:
        if self._page <= 0:
            return
        self._page -= 1
        start = self._page * self._page_size
        if start < len(self._all_titles):
            self.set_active_global_index(start)
            self.view_selected.emit(start)
        self._update_page_controls()
        self.page_changed.emit(self._page)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.btn_toggle.setVisible(self._split_enabled and not collapsed)
        self.list_widget.setVisible(not collapsed and bool(self._all_titles))
        self.empty_label.setVisible(not collapsed and not self._all_titles)
        self.page_widget.setVisible(not collapsed and self.page_count() > 1)
        self.btn_settings.setVisible(not collapsed)
        self._apply_thickness()
        self.updateGeometry()
        self._update_page_controls()
        self._update_empty_state()
        if not collapsed:
            self._recalculate_thickness()

    # ---------------------------------------------------------------- events
    def _on_burger_click(self) -> None:
        new_state = not self._collapsed
        self.set_collapsed(new_state)
        self.collapsed_changed.emit(new_state)
        if new_state:
            self._open_overlay_menu()

    def _open_overlay_menu(self) -> None:
        menu = QMenu(self)
        for idx, title in enumerate(self._all_titles):
            act = menu.addAction(title)
            act.triggered.connect(lambda _=False, i=idx: self.view_selected.emit(i))
        if self._all_titles:
            menu.addSeparator()
        act_settings = menu.addAction(tr("Settings"))
        act_settings.triggered.connect(self.request_settings.emit)
        pos = self.btn_burger.mapToGlobal(self.btn_burger.rect().bottomLeft())
        menu.exec(pos)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        if item is None:
            return
        idx = self.list_widget.row(item)
        self._active_index = idx
        self.view_selected.emit(idx)

    # ---------------------------------------------------------------- helpers
    def _apply_thickness(self) -> None:
        if self._orientation == "top":
            height = 64 if self._collapsed else max(96, self.sizeHint().height())
            self.setFixedHeight(height)
        else:
            width = 68 if self._collapsed else self._thickness
            self.setFixedWidth(width)

    def _update_logo(self) -> None:
        pixmap = QPixmap(self._logo_path) if self._logo_path else None
        has_pixmap = bool(pixmap and not pixmap.isNull())
        if has_pixmap:
            size = 48 if self._orientation == "left" else 40
            scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled)
            self.logo_label.setText(" ")
        else:
            self.logo_label.setPixmap(QPixmap())
            fallback = "MSK"
            if self._all_titles:
                fallback = self._all_titles[0][:3].upper()
            self.logo_label.setText(fallback)
        self.logo_label.setProperty("pixmap", has_pixmap)
        self.logo_label.style().unpolish(self.logo_label)
        self.logo_label.style().polish(self.logo_label)

    def _update_page_controls(self) -> None:
        count = self.page_count()
        self.page_label.setText(
            tr("Page {current} / {total}", current=self._page + 1, total=max(1, count))
        )
        self.btn_prev.setEnabled(self._page > 0)
        self.btn_next.setEnabled(self._page < count - 1)
        self.page_widget.setVisible(not self._collapsed and count > 1)

    def _update_empty_state(self) -> None:
        show_list = not self._collapsed and bool(self._all_titles)
        self.list_widget.setVisible(show_list)
        self.empty_label.setVisible(not self._collapsed and not self._all_titles)

    def _recalculate_thickness(self) -> None:
        if self._orientation == "top":
            return
        fm = self.fontMetrics()
        measurements = [fm.horizontalAdvance(title) for title in self._all_titles if title]
        if getattr(self, "btn_toggle", None) and self.btn_toggle.isVisible():
            measurements.append(fm.horizontalAdvance(self.btn_toggle.text()))
        if getattr(self, "btn_settings", None) and self.btn_settings.isVisible():
            measurements.append(fm.horizontalAdvance(self.btn_settings.text()))
        longest = max(measurements, default=0)
        padding = 96
        desired = max(self._base_width, longest + padding)
        if desired != self._thickness:
            self._thickness = desired
        if not self._collapsed:
            self.setFixedWidth(self._thickness)

    # ---------------------------------------------------------------- locale
    def retranslate_ui(self) -> None:
        self.caption_label.setText(tr("Sources"))
        self.subtitle_label.setText(tr("Select a source to display"))
        self.empty_label.setText(tr("No sources configured yet"))
        self.btn_toggle.setText(tr("Switch layout"))
        self.btn_toggle.setToolTip(tr("Toggle between wall and focus view"))
        self.btn_settings.setText(tr("Settings"))
        self.btn_settings.setToolTip(tr("Open settings"))
        self.btn_prev.setToolTip(tr("Previous page"))
        self.btn_next.setToolTip(tr("Next page"))
        self._update_page_controls()
        self._recalculate_thickness()

