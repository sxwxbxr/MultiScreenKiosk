import locale
from typing import Dict
from PySide6.QtCore import QObject, Signal


def _detect_system_language() -> str:
    try:
        lang, _ = locale.getdefaultlocale()
        if lang and lang.lower().startswith("de"):
            return "de"
    except Exception:
        pass
    return "en"


class LanguageManager(QObject):
    language_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._lang = _detect_system_language()
        self._translations: Dict[str, Dict[str, str]] = {
            "en": {
                "Settings": "Settings",
                "Orientation": "Orientation",
                "Left": "Left",
                "Top": "Top",
                "Enable hamburger menu": "Enable hamburger menu",
                "Theme": "Theme",
                "Light": "Light",
                "Dark": "Dark",
                "Enable placeholder": "Enable placeholder",
                "Path to GIF": "Path to GIF",
                "Browse": "Browse",
                "Logo path": "Logo path",
                "Path to logo": "Path to logo",
                "Logs": "Logs",
                "Log Statistics": "Log Statistics",
                "Window Spy": "Window Spy",
                "Quit": "Quit",
                "Cancel": "Cancel",
                "Save": "Save",
                "Backup config": "Backup config",
                "Restore config": "Restore config",
                "JSON files (*.json);;All files (*)": "JSON files (*.json);;All files (*)",
                "Configuration saved to {path}": "Configuration saved to {path}",
                "Backup failed: {ex}": "Backup failed: {ex}",
                "Configuration restored from {path}": "Configuration restored from {path}",
                "Restore failed: {ex}": "Restore failed: {ex}",
                "Selected file is not a valid configuration.": "Selected file is not a valid configuration.",
                "Configuration must define at least one source.": "Configuration must define at least one source.",
                "Menu": "Menu",
                "Switch": "Switch",
                "Show bar": "Show bar",
                "Language": "Language",
                "English": "English",
                "German": "German",
                "Note: Split screen is disabled. Switch via the sidebar, Ctrl+Q is inactive.": "Note: Split screen is disabled. Switch via the sidebar, Ctrl+Q is inactive.",
                "Confirm quit": "Confirm quit",
                "Do you want to quit the application": "Do you want to quit the application",
                "Unsaved changes might get lost.": "Unsaved changes might get lost.",
                "Placeholder GIF": "Placeholder GIF",
                "Logo": "Logo",
                "Loading...": "Loading...",
                "Level": "Level",
                "Filter text": "Filter text",
                "Regex": "Regex",
                "Case sensitive": "Case sensitive",
                "Auto Scroll": "Auto Scroll",
                "Pause": "Pause",
                "Reload": "Reload",
                "Clear file": "Clear file",
                "Open file": "Open file",
                "Info": "Info",
                "No log file found": "No log file found",
                "The log file could not be cleared:\n{ex}": "The log file could not be cleared:\n{ex}",
                "Class": "Class",
                "Title": "Title",
                "Only filter PID family": "Only filter PID family",
                "Attach selection": "Attach selection",
                "Close": "Close",
                "Please select a row": "Please select a row",
                "Invalid HWND": "Invalid HWND",
                "Attach failed:\n{ex}": "Attach failed:\n{ex}",
                "Root PID: {pid}": "Root PID: {pid}",
                "Window Spy is not available.\nThe module window_spy could not be loaded.": "Window Spy is not available.\nThe module window_spy could not be loaded.",
                "Window selected": "Window selected",
                "The window was recognized. If embedding is intended, the app does this automatically.": "The window was recognized. If embedding is intended, the app does this automatically.",
                "Window Spy could not be started.\nThis version requires a different start.\n\nTechnical info: {ex}": "Window Spy could not be started.\nThis version requires a different start.\n\nTechnical info: {ex}",
                "Window Spy could not be started.\nTechnical info: {ex}": "Window Spy could not be started.\nTechnical info: {ex}",
                "Window Spy could not be displayed.\nTechnical info: {ex}": "Window Spy could not be displayed.\nTechnical info: {ex}",
                "Initial setup": "Initial setup",
                "Number of windows": "Number of windows",
                "Split screen active": "Split screen active",
                "Name": "Name",
                "Type": "Type",
                "browser": "browser",
                "local": "local",
                "URL": "URL",
                "Path to EXE": "Path to EXE",
                "Arguments": "Arguments",
                "Title regex": "Title regex",
                "Class regex": "Class regex",
                "Child class regex": "Child class regex",
                "Allow global fallback": "Allow global fallback",
                "Follow child processes": "Follow child processes",
                "Overwrite config": "Overwrite config",
                "Invalid": "Invalid",
                "Please provide at least one valid source.": "Please provide at least one valid source.",
            },
            "de": {
                "Settings": "Einstellungen",
                "Orientation": "Ausrichtung",
                "Left": "Links",
                "Top": "Oben",
                "Enable hamburger menu": "Hamburger-Menü anzeigen",
                "Theme": "Theme",
                "Light": "Hell",
                "Dark": "Dunkel",
                "Enable placeholder": "Platzhalter aktivieren",
                "Path to GIF": "Pfad zur GIF-Datei",
                "Browse": "Wählen",
                "Logo path": "Logo-Pfad",
                "Path to logo": "Pfad zum Logo",
                "Logs": "Logs",
                "Log Statistics": "Log-Statistik",
                "Window Spy": "Fenster-Spion",
                "Quit": "Beenden",
                "Cancel": "Abbrechen",
                "Save": "Speichern",
                "Backup config": "Config sichern",
                "Restore config": "Config wiederherstellen",
                "JSON files (*.json);;All files (*)": "JSON-Dateien (*.json);;Alle Dateien (*)",
                "Configuration saved to {path}": "Konfiguration gespeichert in {path}",
                "Backup failed: {ex}": "Backup fehlgeschlagen: {ex}",
                "Configuration restored from {path}": "Konfiguration wiederhergestellt von {path}",
                "Restore failed: {ex}": "Wiederherstellung fehlgeschlagen: {ex}",
                "Selected file is not a valid configuration.": "Ausgewählte Datei ist keine gültige Konfiguration.",
                "Configuration must define at least one source.": "Die Konfiguration muss mindestens eine Quelle enthalten.",
                "Menu": "Menü",
                "Switch": "Wechseln",
                "Show bar": "Leiste anzeigen",
                "Language": "Sprache",
                "English": "Englisch",
                "German": "Deutsch",
                "Note: Split screen is disabled. Switch via the sidebar, Ctrl+Q is inactive.": "Hinweis: Splitscreen ist deaktiviert. Wechsel über die Sidebar, Strg+Q ist inaktiv.",
                "Confirm quit": "Beenden bestätigen",
                "Do you want to quit the application": "Möchtest du die Anwendung beenden",
                "Unsaved changes might get lost.": "Ungespeicherte Änderungen gehen möglicherweise verloren.",
                "Placeholder GIF": "Placeholder-GIF",
                "Logo": "Logo",
                "Loading...": "Lade...",
                "Level": "Level",
                "Filter text": "Filtertext",
                "Regex": "Regex",
                "Case sensitive": "Groß-/Kleinschreibung",
                "Auto Scroll": "Auto Scroll",
                "Pause": "Pause",
                "Reload": "Neu laden",
                "Clear file": "Datei leeren",
                "Open file": "Datei öffnen",
                "Info": "Info",
                "No log file found": "Keine Logdatei gefunden",
                "The log file could not be cleared:\n{ex}": "Logdatei konnte nicht geleert werden:\n{ex}",
                "Class": "Klasse",
                "Title": "Titel",
                "Only filter PID family": "Nur PID-Familie filtern",
                "Attach selection": "Auswahl einbetten",
                "Close": "Schließen",
                "Please select a row": "Bitte eine Zeile wählen",
                "Invalid HWND": "Ungültige HWND",
                "Attach failed:\n{ex}": "Einbetten fehlgeschlagen:\n{ex}",
                "Root PID: {pid}": "Root-PID: {pid}",
                "Window Spy is not available.\nThe module window_spy could not be loaded.": "Fenster-Spion ist nicht verfügbar.\nDas Modul window_spy konnte nicht geladen werden.",
                "Window selected": "Fenster ausgewählt",
                "The window was recognized. If embedding is intended, the app does this automatically.": "Das Fenster wurde erkannt. Falls Einbettung vorgesehen ist, übernimmt die App dies automatisch.",
                "Window Spy could not be started.\nThis version requires a different start.\n\nTechnical info: {ex}": "Fenster-Spion konnte nicht gestartet werden.\nDiese Version benötigt einen anderen Start.\n\nTechnische Info: {ex}",
                "Window Spy could not be started.\nTechnical info: {ex}": "Fenster-Spion konnte nicht gestartet werden.\nTechnische Info: {ex}",
                "Window Spy could not be displayed.\nTechnical info: {ex}": "Fenster-Spion konnte nicht angezeigt werden.\nTechnische Info: {ex}",
                "Initial setup": "Ersteinrichtung",
                "Number of windows": "Anzahl Fenster",
                "Split screen active": "Splitscreen aktiv",
                "Name": "Name",
                "Type": "Typ",
                "browser": "Browser",
                "local": "Lokal",
                "URL": "URL",
                "Path to EXE": "Pfad zur EXE",
                "Arguments": "Argumente",
                "Title regex": "Titel-Regex",
                "Class regex": "Klassen-Regex",
                "Child class regex": "Child-Klassen-Regex",
                "Allow global fallback": "Globalen Fallback erlauben",
                "Follow child processes": "Kindprozessen folgen",
                "Overwrite config": "Config überschreiben",
                "Invalid": "Ungültig",
                "Please provide at least one valid source.": "Bitte mindestens eine gültige Quelle angeben.",
            },
        }

    def tr(self, key: str, **kwargs) -> str:
        text = self._translations.get(self._lang, {}).get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def set_language(self, lang: str):
        if lang and lang != self._lang:
            self._lang = lang
            self.language_changed.emit(lang)

    def get_language(self) -> str:
        return self._lang


i18n = LanguageManager()
tr = i18n.tr
