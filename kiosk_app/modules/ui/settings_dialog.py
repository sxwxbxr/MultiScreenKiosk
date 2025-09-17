from __future__ import annotations

from typing import Optional, Dict, Any, List, Callable, Set
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import Qt, QPoint, Signal, QTime
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QLineEdit, QFileDialog, QMessageBox,
    QKeySequenceEdit, QMenu, QGridLayout, QSpinBox, QTableWidget,
    QAbstractItemView, QHeaderView, QTabWidget, QTimeEdit, QSizePolicy,
    QAbstractSpinBox
)

# Log Viewer und Log Pfad
from modules.ui.log_viewer import LogViewer
from modules.utils.logger import get_logger
from modules.utils.i18n import tr, i18n, LanguageInfo
from modules.utils.config_loader import DEFAULT_SHORTCUTS, RemoteLogExportSettings
from modules.ui.remote_export_dialog import RemoteExportDialog

# Fenster Spy optional importieren
try:
    from modules.ui.window_spy import WindowSpyDialog  # type: ignore
    _HAVE_SPY = True
except Exception:
    _HAVE_SPY = False

_log = get_logger(__name__)


def _parse_time_string(value: str) -> Optional[QTime]:
    try:
        parts = value.split(":", 1)
        if len(parts) != 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
        if 0 <= hour < 24 and 0 <= minute < 60:
            return QTime(hour, minute)
    except Exception:
        return None
    return None


class SchedulePaneWidget(QWidget):
    changed = Signal()

    def __init__(self, source_names: Optional[List[str]] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._source_names: List[str] = list(source_names or [])

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        form = QGridLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)

        self.pane_label = QLabel("", self)
        form.addWidget(self.pane_label, 0, 0)

        self.pane_spin = QSpinBox(self)
        self.pane_spin.setRange(0, 99)
        form.addWidget(self.pane_spin, 0, 1)

        self.default_label = QLabel("", self)
        form.addWidget(self.default_label, 1, 0)

        self.default_combo = QComboBox(self)
        self.default_combo.setEditable(True)
        self.default_combo.setInsertPolicy(QComboBox.NoInsert)
        self.default_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        form.addWidget(self.default_combo, 1, 1)

        layout.addLayout(form)

        self.blocks_table = QTableWidget(0, 3, self)
        self.blocks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.blocks_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.blocks_table.verticalHeader().setVisible(False)
        self.blocks_table.setMinimumHeight(140)
        header = self.blocks_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.blocks_table, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        self.btn_add_block = QPushButton("", self)
        self.btn_remove_block = QPushButton("", self)
        button_row.addWidget(self.btn_add_block)
        button_row.addWidget(self.btn_remove_block)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.btn_add_block.clicked.connect(self._add_block_row)
        self.btn_remove_block.clicked.connect(self._remove_selected_block)
        self.blocks_table.itemSelectionChanged.connect(self._update_block_actions)
        self.pane_spin.valueChanged.connect(self.changed)
        self.default_combo.editTextChanged.connect(self.changed)

        self._refresh_default_combo()
        self._update_block_actions()

    def apply_translations(self) -> None:
        self.pane_label.setText(tr("Pane index"))
        self.default_label.setText(tr("Default source"))
        self.btn_add_block.setText(tr("Add time block"))
        self.btn_remove_block.setText(tr("Remove time block"))
        self.blocks_table.setHorizontalHeaderLabels([
            tr("Start time"),
            tr("End time"),
            tr("Source"),
        ])
        if self.default_combo.isEditable() and self.default_combo.lineEdit() is not None:
            self.default_combo.lineEdit().setPlaceholderText(tr("Optional default source"))
        for row in range(self.blocks_table.rowCount()):
            combo = self._block_source_combo(row)
            if combo is not None and combo.isEditable() and combo.lineEdit() is not None:
                combo.lineEdit().setPlaceholderText(tr("Source name"))

    def set_source_names(self, names: List[str]) -> None:
        self._source_names = list(names)
        self._refresh_default_combo()
        for row in range(self.blocks_table.rowCount()):
            combo = self._block_source_combo(row)
            if combo is not None:
                self._refresh_source_combo(combo)

    def set_pane_index(self, index: int) -> None:
        self.pane_spin.setValue(max(0, index))

    def pane_index(self) -> int:
        return self.pane_spin.value()

    def default_text(self) -> str:
        return self.default_combo.currentText().strip()

    def load_entry(self, data: Dict[str, Any]) -> None:
        try:
            pane = int(data.get("pane", 0))
        except Exception:
            pane = 0
        self.pane_spin.setValue(max(0, pane))
        default = data.get("default_source")
        if isinstance(default, str):
            default_text = default
        else:
            default_text = ""
        self._refresh_default_combo(default_text)
        self.blocks_table.setRowCount(0)
        blocks = data.get("blocks") or []
        if isinstance(blocks, list):
            for block in blocks:
                if isinstance(block, dict):
                    self._add_block_row(block)
        self._update_block_actions()

    def to_payload(self) -> Optional[Dict[str, Any]]:
        default_source = self.default_text()
        if not default_source:
            default_value: Optional[str] = None
        else:
            default_value = default_source

        blocks: List[Dict[str, str]] = []
        for row in range(self.blocks_table.rowCount()):
            start_edit = self._time_edit(row, 0)
            end_edit = self._time_edit(row, 1)
            combo = self._block_source_combo(row)
            if start_edit is None or end_edit is None or combo is None:
                continue
            start_str = start_edit.time().toString("HH:mm")
            end_str = end_edit.time().toString("HH:mm")
            source = combo.currentText().strip()
            is_empty = not source and start_str == "00:00" and end_str == "00:00"
            if is_empty:
                continue
            if not source:
                raise ValueError(tr("Please complete or remove empty schedule rows."))
            blocks.append({"start": start_str, "end": end_str, "source": source})

        if not blocks and default_value is None:
            return None

        return {
            "pane": self.pane_spin.value(),
            "blocks": blocks,
            "default_source": default_value,
        }

    def _refresh_default_combo(self, selected: Optional[str] = None) -> None:
        text = selected if selected is not None else self.default_combo.currentText()
        self.default_combo.blockSignals(True)
        self.default_combo.clear()
        self.default_combo.addItem("")
        for name in self._source_names:
            self.default_combo.addItem(name)
        if text:
            idx = self.default_combo.findText(text, Qt.MatchExactly)
            if idx >= 0:
                self.default_combo.setCurrentIndex(idx)
            else:
                self.default_combo.setEditText(text)
        else:
            self.default_combo.setCurrentIndex(0)
        self.default_combo.blockSignals(False)

    def _create_time_edit(self, value: Optional[str] = None) -> QTimeEdit:
        edit = QTimeEdit(self)
        edit.setDisplayFormat("HH:mm")
        edit.setAlignment(Qt.AlignCenter)
        edit.setButtonSymbols(QAbstractSpinBox.NoButtons)
        if value:
            parsed = _parse_time_string(value)
            if parsed is not None:
                edit.setTime(parsed)
        return edit

    def _create_source_combo(self, value: Optional[str] = None) -> QComboBox:
        combo = QComboBox(self)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._refresh_source_combo(combo, value)
        return combo

    def _refresh_source_combo(self, combo: QComboBox, selected: Optional[str] = None) -> None:
        text = selected if selected is not None else combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("")
        for name in self._source_names:
            combo.addItem(name)
        if text:
            idx = combo.findText(text, Qt.MatchExactly)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(text)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _time_edit(self, row: int, column: int) -> Optional[QTimeEdit]:
        widget = self.blocks_table.cellWidget(row, column)
        return widget if isinstance(widget, QTimeEdit) else None

    def _block_source_combo(self, row: int) -> Optional[QComboBox]:
        widget = self.blocks_table.cellWidget(row, 2)
        return widget if isinstance(widget, QComboBox) else None

    def _add_block_row(self, block: Optional[Dict[str, Any]] = None) -> None:
        row = self.blocks_table.rowCount()
        self.blocks_table.insertRow(row)
        start = self._create_time_edit(block.get("start") if block else None)
        end = self._create_time_edit(block.get("end") if block else None)
        source = self._create_source_combo(block.get("source") if block else None)
        self.blocks_table.setCellWidget(row, 0, start)
        self.blocks_table.setCellWidget(row, 1, end)
        self.blocks_table.setCellWidget(row, 2, source)
        self.blocks_table.setCurrentCell(row, 0)
        start.timeChanged.connect(self.changed)
        end.timeChanged.connect(self.changed)
        source.currentTextChanged.connect(self.changed)
        self._update_block_actions()

    def _remove_selected_block(self) -> None:
        row = self.blocks_table.currentRow()
        if row >= 0:
            self.blocks_table.removeRow(row)
            self._update_block_actions()
            self.changed.emit()

    def _update_block_actions(self) -> None:
        has_rows = self.blocks_table.rowCount() > 0
        has_selection = bool(self.blocks_table.selectionModel() and self.blocks_table.selectionModel().hasSelection())
        self.btn_remove_block.setEnabled(has_rows and has_selection)


class ScheduleEditorWidget(QWidget):
    def __init__(
        self,
        schedule_data: Optional[List[Dict[str, Any]]] = None,
        source_names: Optional[List[str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._source_names: List[str] = list(source_names or [])
        self._pane_widgets: List[SchedulePaneWidget] = []

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.tabs = QTabWidget(self)
        self.tabs.setTabBarAutoHide(True)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        layout.addWidget(self.tabs, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        self.btn_add_pane = QPushButton("", self)
        self.btn_remove_pane = QPushButton("", self)
        button_row.addWidget(self.btn_add_pane)
        button_row.addWidget(self.btn_remove_pane)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.btn_add_pane.clicked.connect(self._on_add_pane)
        self.btn_remove_pane.clicked.connect(self._remove_current_pane)
        self.tabs.currentChanged.connect(lambda _idx: self._update_actions())

        for entry in schedule_data or []:
            if isinstance(entry, dict):
                self._add_pane(entry)

        if not self._pane_widgets:
            self._add_pane()

        self._update_actions()

    def apply_translations(self) -> None:
        self.btn_add_pane.setText(tr("Add pane"))
        self.btn_remove_pane.setText(tr("Remove pane"))
        self._update_tab_captions()
        for widget in self._pane_widgets:
            widget.apply_translations()

    def set_source_names(self, names: List[str]) -> None:
        self._source_names = list(names)
        for widget in self._pane_widgets:
            widget.set_source_names(self._source_names)

    def to_payload(self) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        seen: Set[int] = set()
        for widget in self._pane_widgets:
            data = widget.to_payload()
            if not data:
                continue
            pane = int(data.get("pane", 0))
            if pane in seen:
                raise ValueError(tr("Each pane can only have one schedule entry."))
            seen.add(pane)
            entries.append(data)
        return entries

    def _on_add_pane(self) -> None:
        self._add_pane()

    def _add_pane(self, data: Optional[Dict[str, Any]] = None) -> None:
        widget = SchedulePaneWidget(self._source_names, self)
        widget.changed.connect(self._update_tab_captions)
        if data:
            widget.load_entry(data)
        else:
            widget.set_pane_index(self._next_free_pane_index())
        widget.apply_translations()
        index = self.tabs.addTab(widget, "")
        self._pane_widgets.append(widget)
        self.tabs.setCurrentIndex(index)
        self._update_tab_captions()
        self._update_actions()

    def _remove_current_pane(self) -> None:
        idx = self.tabs.currentIndex()
        if idx < 0:
            return
        widget = self.tabs.widget(idx)
        self.tabs.removeTab(idx)
        if 0 <= idx < len(self._pane_widgets):
            removed = self._pane_widgets.pop(idx)
            removed.deleteLater()
        else:
            widget.deleteLater()
        self._update_tab_captions()
        self._update_actions()

    def _update_tab_captions(self) -> None:
        for idx, widget in enumerate(self._pane_widgets):
            pane_label = tr("Pane {index}", index=widget.pane_index() + 1)
            default_text = widget.default_text()
            if default_text:
                pane_label = f"{pane_label} • {default_text}"
            self.tabs.setTabText(idx, pane_label)

    def _update_actions(self) -> None:
        self.btn_remove_pane.setEnabled(self.tabs.count() > 0 and self.tabs.currentIndex() >= 0)

    def _next_free_pane_index(self) -> int:
        used = {widget.pane_index() for widget in self._pane_widgets}
        candidate = 0
        while candidate in used:
            candidate += 1
        return candidate


class ScheduleEditorDialog(QDialog):
    def __init__(
        self,
        schedule_data: Optional[List[Dict[str, Any]]] = None,
        source_names: Optional[List[str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._result: List[Dict[str, Any]] = deepcopy(schedule_data) if schedule_data is not None else []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.editor = ScheduleEditorWidget(self._result, source_names, self)
        self.editor.setMinimumHeight(260)
        layout.addWidget(self.editor, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.btn_cancel = QPushButton("", self)
        self.btn_ok = QPushButton("", self)
        button_row.addWidget(self.btn_cancel)
        button_row.addWidget(self.btn_ok)
        layout.addLayout(button_row)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._accept)

        i18n.language_changed.connect(self._apply_translations)
        self._apply_translations()

    def _accept(self) -> None:
        try:
            payload = self.editor.to_payload()
        except ValueError as ex:
            QMessageBox.warning(self, tr("Invalid schedule"), str(ex))
            return
        self._result = payload
        self.accept()

    def result_schedule(self) -> List[Dict[str, Any]]:
        return deepcopy(self._result)

    def _apply_translations(self) -> None:
        self.setWindowTitle(tr("Content schedule"))
        self.btn_cancel.setText(tr("Cancel"))
        self.btn_ok.setText(tr("Save"))
        self.editor.apply_translations()


class ShortcutEditorDialog(QDialog):
    def __init__(
        self,
        shortcuts: Optional[Dict[str, str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._result: Optional[Dict[str, str]] = None

        base_map: Dict[str, str] = DEFAULT_SHORTCUTS.copy()
        if shortcuts:
            for key, seq in shortcuts.items():
                if seq:
                    base_map[key] = seq
        self._initial_map = base_map

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._order = [
            "select_1",
            "select_2",
            "select_3",
            "select_4",
            "next_page",
            "prev_page",
            "toggle_mode",
            "toggle_kiosk",
        ]
        self._labels: Dict[str, QLabel] = {}
        self._edits: Dict[str, QKeySequenceEdit] = {}

        for key in self._order:
            row = QHBoxLayout()
            lbl = QLabel("", self)
            row.addWidget(lbl)
            edit = QKeySequenceEdit(self)
            edit.setKeySequence(QKeySequence(base_map.get(key, DEFAULT_SHORTCUTS.get(key, ""))))
            row.addWidget(edit, 1)
            layout.addLayout(row)
            self._labels[key] = lbl
            self._edits[key] = edit

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.btn_cancel = QPushButton("", self)
        self.btn_ok = QPushButton("", self)
        button_row.addWidget(self.btn_cancel)
        button_row.addWidget(self.btn_ok)
        layout.addLayout(button_row)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._accept)

        i18n.language_changed.connect(self._apply_translations)
        self._apply_translations()

    def _accept(self) -> None:
        overrides: Dict[str, str] = {}
        for key, edit in self._edits.items():
            seq = edit.keySequence().toString(QKeySequence.NativeText).strip()
            if seq:
                overrides[key] = seq
        sequences = list(overrides.values())
        if len(sequences) != len(set(sequences)):
            QMessageBox.warning(self, tr("Shortcut conflict"), tr("Shortcuts must be unique."))
            return
        result = DEFAULT_SHORTCUTS.copy()
        result.update(overrides)
        self._result = result
        self.accept()

    def result_shortcuts(self) -> Dict[str, str]:
        if self._result is not None:
            return deepcopy(self._result)
        return deepcopy(self._initial_map)

    def _apply_translations(self) -> None:
        self.setWindowTitle(tr("Shortcut editor"))
        names = {
            "select_1": tr("View 1"),
            "select_2": tr("View 2"),
            "select_3": tr("View 3"),
            "select_4": tr("View 4"),
            "next_page": tr("Next page"),
            "prev_page": tr("Previous page"),
            "toggle_mode": tr("Toggle mode"),
            "toggle_kiosk": tr("Toggle kiosk"),
        }
        for key, lbl in self._labels.items():
            lbl.setText(names.get(key, key))
        self.btn_cancel.setText(tr("Cancel"))
        self.btn_ok.setText(tr("Save"))

class SettingsDialog(QDialog):
    """
    Rahmungsloser Settings Dialog.
    results():
      {
        "nav_orientation": str,
        "enable_hamburger": bool,
        "placeholder_enabled": bool,
        "placeholder_gif_path": str,
        "theme": str,
        "logo_path": str,
        "shortcuts": Dict[str, str],
        "remote_export": RemoteLogExportSettings,
        "quit_requested": bool
      }
    """

    def __init__(self,
                 nav_orientation: str,
                 enable_hamburger: bool,
                 placeholder_enabled: bool,
                 placeholder_gif_path: str,
                 theme: str,
                 logo_path: str,
                 split_enabled: bool,
                 shortcuts: Optional[Dict[str, str]] = None,
                 remote_export: Optional[RemoteLogExportSettings] = None,
                 schedule_data: Optional[List[Dict[str, Any]]] = None,
                 source_names: Optional[List[str]] = None,
                 backup_handler: Optional[Callable[[Path], None]] = None,
                 restore_handler: Optional[Callable[[Path], Any]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._drag_pos: Optional[QPoint] = None
        self._result: Dict[str, Any] = {}
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setMinimumSize(640, 380)
        self._backup_handler = backup_handler
        self._restore_handler = restore_handler
        self._remote_export_settings = (
            deepcopy(remote_export) if remote_export is not None else RemoteLogExportSettings()
        )
        self._initial_schedule_payload = deepcopy(schedule_data) if schedule_data is not None else []
        self._source_names: List[str] = list(source_names or [])
        self._schedule_payload: List[Dict[str, Any]] = deepcopy(self._initial_schedule_payload)
        self._shortcut_map: Dict[str, str] = DEFAULT_SHORTCUTS.copy()
        if shortcuts:
            for key, seq in shortcuts.items():
                if seq:
                    self._shortcut_map[key] = seq
        self._shortcut_order = [
            "select_1",
            "select_2",
            "select_3",
            "select_4",
            "next_page",
            "prev_page",
            "toggle_mode",
            "toggle_kiosk",
        ]

        # ---------- Titlebar ----------
        bar = QWidget(self)
        bar.setObjectName("titlebar")
        bar_l = QHBoxLayout(bar)
        bar_l.setContentsMargins(12, 8, 12, 8)
        bar_l.setSpacing(8)

        self.title_lbl = QLabel("", bar)
        bar_l.addWidget(self.title_lbl, 1)

        self.btn_close = QPushButton("×", bar)
        self.btn_close.setFixedWidth(28)
        self.btn_close.clicked.connect(self.reject)
        bar_l.addWidget(self.btn_close)

        # ---------- Content ----------
        body = QWidget(self)
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(16, 16, 16, 16)
        body_l.setSpacing(12)

        # Ausrichtung
        row1 = QHBoxLayout()
        self.lbl_orientation = QLabel("", self)
        row1.addWidget(self.lbl_orientation)
        self.nav_combo = QComboBox(self)
        self.nav_combo.addItem("", "left")
        self.nav_combo.addItem("", "top")
        self.nav_combo.setCurrentIndex(0 if (nav_orientation or "left") == "left" else 1)
        row1.addWidget(self.nav_combo, 1)

        # Hamburger
        row2 = QHBoxLayout()
        self.hamburger_cb = QCheckBox("", self)
        self.hamburger_cb.setChecked(bool(enable_hamburger))
        row2.addWidget(self.hamburger_cb, 1)

        # Theme
        row3 = QHBoxLayout()
        self.lbl_theme = QLabel("", self)
        row3.addWidget(self.lbl_theme)
        self.theme_combo = QComboBox(self)
        self.theme_combo.addItem("", "light")
        self.theme_combo.addItem("", "dark")
        self.theme_combo.setCurrentIndex(0 if (theme or "light") == "light" else 1)
        row3.addWidget(self.theme_combo, 1)

        # Language
        row_lang = QHBoxLayout()
        self.lbl_language = QLabel("", self)
        row_lang.addWidget(self.lbl_language)
        self.language_combo = QComboBox(self)
        self._language_options: List[LanguageInfo] = i18n.available_languages()
        for info in self._language_options:
            self.language_combo.addItem("", info.code)
        cur_lang = i18n.get_language()
        try:
            idx = next(i for i, info in enumerate(self._language_options) if info.code == cur_lang)
        except StopIteration:
            idx = 0
        self.language_combo.setCurrentIndex(idx)
        row_lang.addWidget(self.language_combo, 1)

        # Placeholder
        row4 = QHBoxLayout()
        self.placeholder_cb = QCheckBox("", self)
        self.placeholder_cb.setChecked(bool(placeholder_enabled))
        row4.addWidget(self.placeholder_cb)

        self.gif_edit = QLineEdit(self)
        self.gif_edit.setPlaceholderText("")
        self.gif_edit.setText(placeholder_gif_path or "")
        self.btn_browse_gif = QPushButton("", self)
        self.btn_browse_gif.clicked.connect(self._browse_gif)
        row4.addWidget(self.gif_edit, 1)
        row4.addWidget(self.btn_browse_gif)

        # Logo
        row5 = QHBoxLayout()
        self.lbl_logo = QLabel("", self)
        row5.addWidget(self.lbl_logo)
        self.logo_edit = QLineEdit(self)
        self.logo_edit.setPlaceholderText("")
        self.logo_edit.setText(logo_path or "")
        self.btn_browse_logo = QPushButton("", self)
        self.btn_browse_logo.clicked.connect(self._browse_logo)
        row5.addWidget(self.logo_edit, 1)
        row5.addWidget(self.btn_browse_logo)

        # Schedule editor launcher
        schedule_row = QHBoxLayout()
        self.lbl_schedule = QLabel("", self)
        schedule_row.addWidget(self.lbl_schedule)
        self.schedule_summary_lbl = QLabel("", self)
        self.schedule_summary_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        schedule_row.addWidget(self.schedule_summary_lbl, 1)
        self.btn_open_schedule = QPushButton("", self)
        self.btn_open_schedule.clicked.connect(self._open_schedule_dialog)
        schedule_row.addWidget(self.btn_open_schedule)

        # Shortcut editor launcher
        shortcuts_row = QHBoxLayout()
        self.lbl_shortcuts = QLabel("", self)
        shortcuts_row.addWidget(self.lbl_shortcuts)
        self.shortcut_summary_lbl = QLabel("", self)
        self.shortcut_summary_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        shortcuts_row.addWidget(self.shortcut_summary_lbl, 1)
        self.btn_open_shortcuts = QPushButton("", self)
        self.btn_open_shortcuts.clicked.connect(self._open_shortcut_dialog)
        shortcuts_row.addWidget(self.btn_open_shortcuts)

        body_l.addLayout(row1)
        body_l.addLayout(row2)
        body_l.addLayout(row3)
        body_l.addLayout(row_lang)
        body_l.addLayout(row4)
        body_l.addLayout(row5)
        body_l.addLayout(schedule_row)
        body_l.addLayout(shortcuts_row)
        self.info_lbl = None
        if not split_enabled:
            self.info_lbl = QLabel("", self)
            self.info_lbl.setWordWrap(True)
            body_l.addWidget(self.info_lbl)

        # ---------- Footer Aktionen ----------
        footer = QHBoxLayout()
        self.btn_config = QPushButton("", self)
        self._config_menu = QMenu(self.btn_config)
        self.action_backup = self._config_menu.addAction("")
        self.action_backup.triggered.connect(self._trigger_backup)
        self.action_restore = self._config_menu.addAction("")
        self.action_restore.triggered.connect(self._trigger_restore)

        self.btn_logs = QPushButton("", self)
        self.btn_remote_export = QPushButton("", self)
        self.btn_spy = QPushButton("", self)
        self.btn_quit = QPushButton("", self)
        self.btn_cancel = QPushButton("", self)
        self.btn_ok = QPushButton("", self)
        footer.addWidget(self.btn_config)
        footer.addWidget(self.btn_logs)
        footer.addWidget(self.btn_remote_export)
        footer.addWidget(self.btn_spy)
        footer.addStretch(1)
        footer.addWidget(self.btn_quit)
        footer.addWidget(self.btn_cancel)
        footer.addWidget(self.btn_ok)

        # Root
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(bar)
        root.addWidget(body, 1)
        root.addLayout(footer)

        # Events
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._accept_save)
        self.btn_config.clicked.connect(self._open_config_menu)
        self.btn_logs.clicked.connect(self._open_logs_window)
        self.btn_remote_export.clicked.connect(self._open_remote_export_dialog)
        self.btn_quit.clicked.connect(self._request_quit)
        self.btn_spy.clicked.connect(self._open_window_spy)

        # Styling
        self._apply_style()

        # Child Fenster Referenzen
        self._child_windows: List[QDialog] = []

        self._refresh_config_actions()

        i18n.language_changed.connect(self._on_language_changed)
        self._apply_translations()
        self._update_remote_button_caption()

    # ------- Actions -------
    def _accept_save(self):
        schedule_payload = deepcopy(self._schedule_payload or [])

        sequences = [seq for seq in self._shortcut_map.values() if seq]
        if len(sequences) != len(set(sequences)):
            QMessageBox.warning(self, tr("Shortcut conflict"), tr("Shortcuts must be unique."))
            return

        merged = DEFAULT_SHORTCUTS.copy()
        for key, seq in self._shortcut_map.items():
            if seq:
                merged[key] = seq

        self._result = {
            "nav_orientation": self.nav_combo.currentData(),
            "enable_hamburger": bool(self.hamburger_cb.isChecked()),
            "placeholder_enabled": bool(self.placeholder_cb.isChecked()),
            "placeholder_gif_path": self.gif_edit.text().strip(),
            "theme": self.theme_combo.currentData(),
            "language": self.language_combo.currentData(),
            "logo_path": self.logo_edit.text().strip(),
            "shortcuts": merged,
            "remote_export": deepcopy(self._remote_export_settings),
            "quit_requested": False,
            "schedule": schedule_payload,
        }
        self.accept()

    def _update_remote_button_caption(self):
        status = tr("enabled") if getattr(self._remote_export_settings, "enabled", False) else tr("disabled")
        count = len(getattr(self._remote_export_settings, "destinations", []) or [])
        self.btn_remote_export.setText(tr("Remote export ({status})", status=status))
        self.btn_remote_export.setToolTip(tr("{count} destinations configured", count=count))

    def _update_schedule_summary(self) -> None:
        count = len(self._schedule_payload or [])
        if count == 0:
            summary = tr("No schedule configured")
        else:
            summary = tr("Panes scheduled: {count}", count=count)
        self.schedule_summary_lbl.setText(summary)

    def _update_shortcut_summary(self) -> None:
        custom = 0
        for key in self._shortcut_order:
            seq = self._shortcut_map.get(key)
            if seq and seq != DEFAULT_SHORTCUTS.get(key):
                custom += 1
        if custom == 0:
            summary = tr("Using default shortcuts")
        else:
            summary = tr("Custom shortcuts: {count}", count=custom)
        self.shortcut_summary_lbl.setText(summary)

    def _refresh_config_actions(self):
        have_backup = bool(self._backup_handler)
        have_restore = bool(self._restore_handler)
        if hasattr(self, "action_backup"):
            self.action_backup.setVisible(have_backup)
            self.action_backup.setEnabled(have_backup)
        if hasattr(self, "action_restore"):
            self.action_restore.setVisible(have_restore)
            self.action_restore.setEnabled(have_restore)
        show_button = have_backup or have_restore
        self.btn_config.setVisible(show_button)
        self.btn_config.setEnabled(show_button)

    def _open_config_menu(self):
        actions = [act for act in self._config_menu.actions() if act.isVisible() and act.isEnabled()]
        if not actions:
            return
        if len(actions) == 1:
            actions[0].trigger()
            return
        pos = self.btn_config.mapToGlobal(self.btn_config.rect().bottomLeft())
        self._config_menu.exec(pos)

    def _open_remote_export_dialog(self):
        dlg = RemoteExportDialog(self._remote_export_settings, self)
        if dlg.exec():
            result = dlg.result_settings()
            if result is not None:
                self._remote_export_settings = deepcopy(result)
                self._update_remote_button_caption()

    def _open_schedule_dialog(self) -> None:
        dlg = ScheduleEditorDialog(self._schedule_payload, self._source_names, self)
        if dlg.exec():
            self._schedule_payload = dlg.result_schedule()
            self._update_schedule_summary()

    def _open_shortcut_dialog(self) -> None:
        dlg = ShortcutEditorDialog(self._shortcut_map, self)
        if dlg.exec():
            self._shortcut_map = dlg.result_shortcuts()
            self._update_shortcut_summary()

    def _open_logs_window(self):
        dlg = LogViewer(self)
        dlg.setModal(False)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.show()
        self._child_windows.append(dlg)

    def _trigger_backup(self):
        if not self._backup_handler:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Backup config"),
            "",
            tr("JSON files (*.json);;All files (*)")
        )
        if not file_path:
            return
        path = Path(file_path)
        if not path.suffix:
            path = path.with_suffix(".json")
        try:
            self._backup_handler(path)
            _log.info("config backup written to %s", path)
        except Exception as ex:
            _log.error("config backup failed: %s", ex)
            QMessageBox.critical(self, tr("Backup config"), tr("Backup failed: {ex}", ex=ex))
            return
        QMessageBox.information(self, tr("Backup config"), tr("Configuration saved to {path}", path=str(path)))

    def _trigger_restore(self):
        if not self._restore_handler:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Restore config"),
            "",
            tr("JSON files (*.json);;All files (*)")
        )
        if not file_path:
            return
        path = Path(file_path)
        try:
            cfg = self._restore_handler(path)
            _log.info("config restored from %s", path)
        except Exception as ex:
            _log.error("config restore failed: %s", ex)
            QMessageBox.critical(self, tr("Restore config"), tr("Restore failed: {ex}", ex=ex))
            return
        QMessageBox.information(self, tr("Restore config"), tr("Configuration restored from {path}", path=str(path)))
        self._result = {
            "restored_config": cfg,
            "restored_from": str(path),
            "quit_requested": False,
        }
        self.accept()

    # ===== Fenster Spy =====
    def _open_window_spy(self):
        if not _HAVE_SPY:
            QMessageBox.information(
                self,
                tr("Window Spy"),
                tr("Window Spy is not available.\nThe module window_spy could not be loaded.")
            )
            return

        # attach Callback akzeptiert beliebige Argumente, damit wir zu allen Spy Versionen kompatibel sind
        def _on_spy_attach(*args, **kwargs):
            _log.info("Spy Auswahl empfangen args=%s kwargs=%s", args, kwargs, extra={"source": "window_spy"})
            # Nutzerverstaendliche Rueckmeldung
            QMessageBox.information(self,
                                    tr("Window selected"),
                                    tr("The window was recognized. If embedding is intended, the app does this automatically."))
        # Versuche die exakte Signatur aus deinem Screenshot: keyword only
        try:
            dlg = WindowSpyDialog(title="Fenster Spy", pid_root=None, attach_callback=_on_spy_attach, parent=self)  # type: ignore
        except TypeError as ex:
            # Verstaendliche Meldung, plus technische Info klein
            QMessageBox.warning(
                self,
                tr("Window Spy"),
                tr("Window Spy could not be started.\nThis version requires a different start.\n\nTechnical info: {ex}", ex=ex)
            )
            return
        except Exception as ex:
            QMessageBox.warning(
                self,
                tr("Window Spy"),
                tr("Window Spy could not be started.\nTechnical info: {ex}", ex=ex)
            )
            return

        try:
            if not dlg.windowTitle():
                dlg.setWindowTitle(tr("Window Spy"))
            dlg.setModal(False)
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.show()
            self._child_windows.append(dlg)
        except Exception as ex:
            QMessageBox.warning(
                self,
                tr("Window Spy"),
                tr("Window Spy could not be displayed.\nTechnical info: {ex}", ex=ex)
            )

    def _request_quit(self):
        m = QMessageBox(self)
        m.setWindowTitle(tr("Confirm quit"))
        m.setText(tr("Do you want to quit the application"))
        m.setInformativeText(tr("Unsaved changes might get lost."))
        m.setIcon(QMessageBox.Warning)
        m.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        m.setDefaultButton(QMessageBox.No)
        res = m.exec()

        if res == QMessageBox.Yes:
            self._result = {
                "nav_orientation": self.nav_combo.currentData(),
                "enable_hamburger": bool(self.hamburger_cb.isChecked()),
                "placeholder_enabled": bool(self.placeholder_cb.isChecked()),
                "placeholder_gif_path": self.gif_edit.text().strip(),
                "theme": self.theme_combo.currentData(),
                "language": self.language_combo.currentData(),
                "logo_path": self.logo_edit.text().strip(),
                "remote_export": deepcopy(self._remote_export_settings),
                "quit_requested": True,
            }
            self.accept()

    def results(self) -> Dict[str, Any]:
        if self._result:
            return self._result

        schedule_payload = deepcopy(self._schedule_payload or [])

        merged = DEFAULT_SHORTCUTS.copy()
        for key, seq in self._shortcut_map.items():
            if seq:
                merged[key] = seq

        return {
            "nav_orientation": self.nav_combo.currentData(),
            "enable_hamburger": bool(self.hamburger_cb.isChecked()),
            "placeholder_enabled": bool(self.placeholder_cb.isChecked()),
            "placeholder_gif_path": self.gif_edit.text().strip(),
            "theme": self.theme_combo.currentData(),
            "language": self.language_combo.currentData(),
            "logo_path": self.logo_edit.text().strip(),
            "shortcuts": merged,
            "remote_export": deepcopy(self._remote_export_settings),
            "quit_requested": False,
            "schedule": schedule_payload,
        }

    def _browse_gif(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Placeholder GIF"), "", "GIF (*.gif);;All files (*)")
        if path:
            self.gif_edit.setText(path)

    def _browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Logo"), "", "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All files (*)")
        if path:
            self.logo_edit.setText(path)

    # ------- Frameless Drag -------
    def mousePressEvent(self, e):
        w = self.childAt(e.position().toPoint())
        if e.button() == Qt.LeftButton and w and w.objectName() == "titlebar":
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        super().mouseReleaseEvent(e)

    # ------- Style -------
    def _apply_style(self):
        self.setStyleSheet("""
            #titlebar { background: rgba(127,127,127,0.08); }
            QLabel { font-size: 14px; }
            QLineEdit { border: 1px solid rgba(128,128,128,0.35); border-radius: 8px; padding: 6px 8px; }
            QPushButton {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(128,128,128,0.35);
                border-radius: 10px; padding: 8px 12px;
            }
            QPushButton:hover { border-color: rgba(128,128,128,0.55); }
            QPushButton:pressed { background: rgba(255,255,255,0.08); }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border:1px solid rgba(128,128,128,0.45); background: rgba(255,255,255,0.03); }
            QCheckBox::indicator:checked { background:#0a84ff; border-color:#0a84ff; }
        """)

    def _on_language_changed(self, _lang: str) -> None:
        self._apply_translations()

    def _apply_translations(self):
        self.title_lbl.setText(tr("Settings"))
        self.lbl_orientation.setText(tr("Orientation"))
        self.nav_combo.setItemText(0, tr("Left"))
        self.nav_combo.setItemText(1, tr("Top"))
        self.hamburger_cb.setText(tr("Enable hamburger menu"))
        self.lbl_theme.setText(tr("Theme"))
        self.theme_combo.setItemText(0, tr("Light"))
        self.theme_combo.setItemText(1, tr("Dark"))
        self.lbl_language.setText(tr("Language"))
        for idx, info in enumerate(self._language_options):
            if idx < self.language_combo.count():
                translated = tr(info.name)
                if translated == info.name and info.native_name:
                    translated = info.native_name
                self.language_combo.setItemText(idx, translated)
        self.placeholder_cb.setText(tr("Enable placeholder"))
        self.gif_edit.setPlaceholderText(tr("Path to GIF"))
        self.btn_browse_gif.setText(tr("Browse"))
        self.lbl_logo.setText(tr("Logo path"))
        self.logo_edit.setPlaceholderText(tr("Path to logo"))
        self.btn_browse_logo.setText(tr("Browse"))
        self.lbl_schedule.setText(tr("Content schedule"))
        self.btn_open_schedule.setText(tr("Open schedule editor"))
        self._update_schedule_summary()
        self.lbl_shortcuts.setText(tr("Shortcuts"))
        self.btn_open_shortcuts.setText(tr("Configure shortcuts"))
        self._update_shortcut_summary()
        if self.info_lbl is not None:
            self.info_lbl.setText(tr("Note: Split screen is disabled. Switch via the sidebar, Ctrl+Q is inactive."))
        config_label = tr("Configuration")
        if self._backup_handler and self._restore_handler:
            config_label = tr("Backup / restore config")
        elif self._backup_handler:
            config_label = tr("Backup config")
        elif self._restore_handler:
            config_label = tr("Restore config")
        self.btn_config.setText(config_label)
        self.action_backup.setText(tr("Backup config"))
        self.action_restore.setText(tr("Restore config"))
        self.btn_logs.setText(tr("Logs"))
        self.btn_remote_export.setText(tr("Remote export"))
        self.btn_spy.setText(tr("Window Spy"))
        self.btn_quit.setText(tr("Quit"))
        self.btn_cancel.setText(tr("Cancel"))
        self.btn_ok.setText(tr("Save"))
        self._update_remote_button_caption()
        self._refresh_config_actions()
