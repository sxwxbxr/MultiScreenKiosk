# MultiScreenKiosk – Installations-, Konfigurations- und Bedienungsanleitung

## Installation

1. **Voraussetzungen**
   - Windows 10 oder neuer
2. **Download**
   - Neueste Release von der Projektseite herunterladen.
3. **Start**
   - Ggf. ZIP entpacken und `MultiScreenKiosk.exe` ausführen.

## Konfiguration

1. **Erster Start**
   - `MultiScreenKiosk.exe --setup`
   - Dialog zum Festlegen der **Anzahl der Fenster** und **Quellen**.
2. **Konfigurationsdatei**
   - Pfad: `kiosk_app/modules/config.json`
   - Struktur-Beispiel:
     ```json
     {
       "sources": [{"type": "browser", "name": "Google", "url": "https://www.google.com"}],
       "ui": {"start_mode": "single", "shortcuts": {}},
       "kiosk": {"monitor_index": 0, "kiosk_fullscreen": true}
     }
     ```
   - Alternativ über den Setup‑Dialog erzeugen lassen.

## Bedienung

1. **Starten**
   - Standard: `MultiScreenKiosk.exe`
   - Optionen:
     - `--config PATH` – alternativen Konfigurationspfad verwenden
     - `--setup` – Setup-Dialog erneut öffnen
     - `--log-level LVL` – Log‑Level überschreiben (DEBUG, INFO, …)
2. **Tastenkürzel**
   - `Ctrl+1…4` – Pane auswählen
   - `Ctrl+Q` – Einzel-/Vierfachansicht umschalten
   - `F11` – Kiosk-Vollbild an/aus
   - `Shift + Schließen` – Beenden im Kiosk-Modus
3. **Logging**
   - Logdateien unter `%LOCALAPPDATA%\\MultiScreenKiosk\\logs`
   - Pro Start: `YYYYMMDD_N_Logfile.log`
