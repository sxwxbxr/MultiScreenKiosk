from __future__ import annotations

"""Simple on-screen keyboard overlay for touch kiosks.

This module provides :class:`OnScreenKeyboard`, a minimal virtual keyboard
implemented with standard Qt widgets.  It is intentionally lightweight so the
project has a built-in solution without depending on the Qt Virtual Keyboard
commercial add-on or the Windows on-screen keyboard utility.  The keyboard is
shown or hidden automatically when focus changes to text input widgets.
"""

from typing import Iterable

from PySide6.QtCore import Qt, QObject, Slot, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QGridLayout,
    QToolButton,
    QLineEdit,
    QTextEdit,
    QPlainTextEdit,
)


class OnScreenKeyboard(QWidget):
    """A very small virtual keyboard composed of :class:`QToolButton` keys."""

    #: Layout definition for the keyboard.  Each inner iterable describes one row
    #: and contains the labels for the keys in that row.
    KEY_ROWS: Iterable[Iterable[str]] = (
        ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "Backspace"),
        ("q", "w", "e", "r", "t", "y", "u", "i", "o", "p"),
        ("a", "s", "d", "f", "g", "h", "j", "k", "l", "Enter"),
        ("z", "x", "c", "v", "b", "n", "m", "Space"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        # ``Qt.Tool`` makes the widget float above the main window without a task
        # bar entry. ``WindowStaysOnTopHint`` keeps it above all other widgets so
        # it behaves like a classic overlay keyboard.
        super().__init__(parent, Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setObjectName("OnScreenKeyboard")
        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        for row, keys in enumerate(self.KEY_ROWS):
            for col, label in enumerate(keys):
                btn = QToolButton(self)
                btn.setText(label)
                btn.clicked.connect(lambda _=False, k=label: self.press_key(k))
                layout.addWidget(btn, row, col)

        self._target_widget: QWidget | None = None
        self.hide()

    # ------------------------------------------------------------------
    # key handling
    # ------------------------------------------------------------------
    def _send_event(self, widget: QWidget, event: QKeyEvent) -> None:
        """Dispatch a :class:`QKeyEvent` to ``widget``."""
        QApplication.sendEvent(widget, event)

    def press_key(self, key: str) -> None:
        """Send ``key`` to the currently focused widget.

        Special keys:
            * ``Backspace`` – generates a backspace key press
            * ``Enter`` – generates a return/enter key press
            * ``Space`` – inserts a single space character
        """

        widget = QApplication.focusWidget() or self._target_widget
        if widget is None:
            return

        if key == "Backspace":
            event = QKeyEvent(QEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
            self._send_event(widget, event)
            return
        if key == "Enter":
            event = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
            self._send_event(widget, event)
            return

        text = " " if key == "Space" else key
        event = QKeyEvent(QEvent.KeyPress, 0, Qt.NoModifier, text)
        self._send_event(widget, event)


class KeyboardFocusHandler(QObject):
    """Show the on-screen keyboard for editable widgets and hide otherwise."""

    EDITABLE_TYPES = (QLineEdit, QTextEdit, QPlainTextEdit)

    def __init__(self, keyboard: OnScreenKeyboard, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._keyboard = keyboard
        app = QApplication.instance()
        if app is not None:
            app.focusChanged.connect(self._on_focus_changed)

    # We annotate parameters as QWidget | None for PySide6's signal signature.
    @Slot("QWidget*", "QWidget*")
    def _on_focus_changed(self, old: QWidget | None, new: QWidget | None) -> None:
        if new is not None and isinstance(new, self.EDITABLE_TYPES):
            # Display keyboard when an editable widget receives focus.
            self._keyboard._target_widget = new
            self._keyboard.show()
        else:
            self._keyboard._target_widget = None
            self._keyboard.hide()
