from __future__ import annotations
from typing import Optional, List, Tuple, Set
import ctypes
from ctypes import wintypes

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox,
    QTableWidget, QTableWidgetItem, QLabel, QMessageBox, QAbstractItemView, QWidget
)

from modules.services.local_app_service import (
    EnumWindowsProc, EnumWindows, GetWindowThreadProcessId, DWORD,
    IsWindowVisible, GetAncestor, GA_ROOT, GetWindowTextW, GetClassNameW,
    snapshot_processes
)
from modules.utils.logger import get_logger


class WindowSpyDialog(QDialog):
    def __init__(self, *,
                 title: str,
                 pid_root: Optional[int],
                 attach_callback,
                 parent: Optional[Widget] = None):  # type: ignore[name-defined]
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)
        self.setWindowFlag(Qt.Window, True)
        self.setWindowModality(Qt.NonModal)
        self.resize(900, 520)
        self.log = get_logger(__name__)

        self.pid_root = pid_root
        self.attach_callback = attach_callback

        self.only_family_cb = QCheckBox("Nur PID Familie filtern", self)
        self.only_family_cb.setChecked(True)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["HWND", "PID", "Klasse", "Titel"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)

        btn_refresh = QPushButton("Neu laden", self)
        btn_attach = QPushButton("Auswahl einbetten", self)
        btn_close = QPushButton("Schliessen", self)

        btn_refresh.clicked.connect(self.reload)
        btn_attach.clicked.connect(self.attach_selected)
        btn_close.clicked.connect(self.close)
        self.only_family_cb.stateChanged.connect(self.reload)

        top = QHBoxLayout()
        top.addWidget(QLabel(f"Root PID: {self.pid_root if self.pid_root else '-'}"))
        top.addStretch(1)
        top.addWidget(self.only_family_cb)

        bottom = QHBoxLayout()
        bottom.addWidget(btn_refresh)
        bottom.addStretch(1)
        bottom.addWidget(btn_attach)
        bottom.addWidget(btn_close)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.table, 1)
        root.addLayout(bottom)

        self.reload()
        self._center_on_parent()

    def showEvent(self, ev):
        super().showEvent(ev)
        self.raise_()
        self.activateWindow()

    def _center_on_parent(self):
        p = self.parent()
        if isinstance(p, QWidget):
            g = p.frameGeometry()
            center = g.center()
            my = self.frameGeometry()
            my.moveCenter(center)
            self.move(my.topLeft())

    def _pid_family(self) -> Set[int]:
        if not self.pid_root:
            return set()
        try:
            parent_map, _ = snapshot_processes()
        except Exception:
            return {self.pid_root}
        res = {self.pid_root}
        queue = [self.pid_root]
        while queue:
            cur = queue.pop()
            for child, parent in parent_map.items():
                if parent == cur and child not in res:
                    res.add(child)
                    queue.append(child)
        return res

    def reload(self):
        self.table.setRowCount(0)
        fam = self._pid_family() if self.only_family_cb.isChecked() else None

        rows: List[Tuple[int,int,str,str]] = []

        def _cb(hwnd, _lparam):
            try:
                if not IsWindowVisible(hwnd):
                    return True
                root = GetAncestor(hwnd, GA_ROOT)
                if not root or root != hwnd:
                    return True

                # PID
                proc_id = DWORD(0)
                GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
                pid = int(proc_id.value)
                if fam and pid not in fam:
                    return True

                # Titel
                tbuf = ctypes.create_unicode_buffer(512)
                GetWindowTextW(hwnd, tbuf, 512)
                title = tbuf.value or ""

                # Klasse
                cbuf = ctypes.create_unicode_buffer(256)
                GetClassNameW(hwnd, cbuf, 256)
                cls = cbuf.value or ""

                rows.append((int(hwnd), pid, cls, title))
            except Exception:
                pass
            return True

        EnumWindows(EnumWindowsProc(_cb), 0)

        self.table.setRowCount(len(rows))
        for r, (hwnd, pid, cls, title) in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(hex(hwnd)))
            self.table.setItem(r, 1, QTableWidgetItem(str(pid)))
            self.table.setItem(r, 2, QTableWidgetItem(cls))
            self.table.setItem(r, 3, QTableWidgetItem(title))

        self.table.resizeColumnsToContents()

    def attach_selected(self):
        items = self.table.selectedItems()
        if not items:
            QMessageBox.information(self, "Fenster Spy", "Bitte eine Zeile waehlen")
            return
        row = items[0].row()
        hwnd_item = self.table.item(row, 0)
        if not hwnd_item:
            return
        try:
            hwnd = int(hwnd_item.text(), 16)
        except Exception:
            QMessageBox.warning(self, "Fenster Spy", "Ungueltige HWND")
            return
        try:
            self.attach_callback(hwnd)
            self.log.info(f"Attach via Spy auf hwnd={hex(hwnd)}", extra={"source": "spy"})
        except Exception as ex:
            QMessageBox.critical(self, "Fenster Spy", f"Attach fehlgeschlagen:\n{ex}")
