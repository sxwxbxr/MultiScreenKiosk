import pytest
from utils.i18n import i18n, tr


def test_language_switching():
    original = i18n.get_language()
    try:
        i18n.set_language("en")
        assert tr("Settings") == "Settings"
        i18n.set_language("de")
        assert tr("Settings") == "Einstellungen"
    finally:
        i18n.set_language(original)


def test_setup_dialog_retranslation():
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication
    from ui.setup_dialog import SetupDialog

    app = QApplication.instance() or QApplication([])
    original = i18n.get_language()
    try:
        i18n.set_language("en")
        dlg = SetupDialog({})
        assert dlg.windowTitle() == "Initial setup"
        i18n.set_language("de")
        assert dlg.windowTitle() == "Ersteinrichtung"
    finally:
        i18n.set_language(original)
        dlg.close()
