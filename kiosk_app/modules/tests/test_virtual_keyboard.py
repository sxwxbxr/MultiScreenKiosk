import os

# Ensure Qt can run in environments without a display server
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit, QWidget
from ui.virtual_keyboard import OnScreenKeyboard, KeyboardFocusHandler


def test_keyboard_visibility_and_input():
    app = QApplication.instance() or QApplication([])

    line_edit = QLineEdit()
    dummy = QWidget()

    keyboard = OnScreenKeyboard()
    handler = KeyboardFocusHandler(keyboard)

    # Simulate focus change via the handler and ensure the keyboard becomes visible
    handler._on_focus_changed(None, line_edit)
    assert keyboard.isVisible()

    # Simulate pressing a key and ensure the text is inserted
    keyboard.press_key("a")
    app.processEvents()
    assert line_edit.text() == "a"

    # Move focus away and ensure keyboard hides
    handler._on_focus_changed(line_edit, dummy)
    assert not keyboard.isVisible()

    # Clean up QApplication for other tests
    keyboard.close()
    line_edit.close()
    dummy.close()
    app.quit()
