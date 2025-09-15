# MultiScreenKiosk – Schritt-für-Schritt-Anleitung

## 1. Download und Installation
1. Öffnen Sie die Release-Seite des Projekts.
   - *Screenshot: Release-Seite*
2. Laden Sie die Datei `MultiScreenKiosk-win64.zip` herunter.
   - *Screenshot: Download*
3. Entpacken Sie das ZIP in einen Ordner Ihrer Wahl.
   - *Screenshot: Entpacktes Verzeichnis*
4. Starten Sie `MultiScreenKiosk.exe` per Doppelklick.
   - *Screenshot: Start der EXE*

## 2. Ersteinrichtung (Setup)
1. Rufen Sie das Setup mit `MultiScreenKiosk.exe --setup` auf.
   - *Screenshot: Setup-Aufruf*
2. Legen Sie die **Anzahl der Fenster** fest.
   - *Screenshot: Auswahl der Fenster*
3. Fügen Sie für jedes Fenster eine Quelle hinzu (z. B. URL).
   - *Screenshot: Quelle hinzufügen*
4. Speichern Sie den Dialog – die Datei `kiosk_app/modules/config.json` wird angelegt.
   - *Screenshot: Speichern*

## 3. Start mit vorhandener Konfiguration
1. Starten Sie `MultiScreenKiosk.exe` ohne Parameter.
   - *Screenshot: Programmstart*
2. Optional: `--config PFAD` für eine eigene Konfigurationsdatei.
   - *Screenshot: Eigener Config-Pfad*

## 4. Bedienung
1. **Tastenkürzel**
   - `Ctrl+1…4` – Fenster auswählen
   - `Ctrl+Q` – Einzel-/Vierfachansicht umschalten
   - `F11` – Kiosk-Vollbild an/aus
   - `Shift + Schließen` – Beenden im Kiosk-Modus
   - *Screenshot: Bedienoberfläche*
2. **Logging**
   - Logdateien: `%LOCALAPPDATA%\\MultiScreenKiosk\\logs`
   - *Screenshot: Logverzeichnis*
