# Kiosk Anwendung fuer Windows mit PyQt5

## Features
- Echter Vollbild Kiosk ohne Rahmen
- Sidebar mit vier Quellen, Strg+1 bis Strg+4 fuer direkte Wahl
- Umschalten Einzel oder Viereransicht per Strg+Q
- F11 schaltet Kiosk an und aus
- Drei Qt WebEngine Instanzen plus lokale Software als eingebettetes Fenster
- Heartbeat fuer Browser mit automatischem Reload
- Watchdog fuer lokalen Prozess mit Neustart
- Konfiguration per `config.json`
- Rotationslog unter `./logs/kiosk.log`

## Setup
1. Python 3.10 oder neuer installieren
2. Repository Inhalt in einen Ordner kopieren
3. In der Konsole:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
