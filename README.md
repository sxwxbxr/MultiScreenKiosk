# Kiosk App fuer Windows mit PySide6 und Qt WebEngine

Eine robuste Vollbild Anwendung fuer Anzeige von Browserinhalten und lokalen Windows Programmen. Mit Setup Dialog, dynamischem Grid, Navigation als Sidebar oder Header, Watchdogs und Logging.

---

## Inhalt

* Ueberblick
* Hauptfunktionen
* Architektur und Ordner
* Voraussetzungen
* Installation
* Start und Parameter
* Bedienung und Shortcuts
* Setup Dialog
* Konfiguration per Datei
* Einbettung lokaler Software
* Stabilitaet und Monitoring
* Sicherheit
* Tests und Smoke Check
* Fehlerbehebung
* Autostart unter Windows

---

## Ueberblick

Die App zeigt beliebig viele **Fensterquellen** in Vollbild. Jede Quelle ist entweder

* **Browser** via Qt WebEngine
* **Lokale Windows App** eingebettet per Win32 SetParent

Die **Quad Ansicht** passt sich automatisch an. Pro Seite werden bis zu vier Quellen angezeigt. Wenn weniger Quellen auf der Seite sind, nutzt das Layout den Platz optimal. Die **Einzelansicht** zeigt eine Quelle bildschirmfuellend.

Ein **Setup Dialog** beim Start erlaubt die schnelle Konfiguration ohne Datei Bearbeitung. Optional kann die Konfiguration gespeichert werden.

---

## Hauptfunktionen

* Kiosk Modus im echten Vollbild ohne Rahmen
* Navigation links als Sidebar oder oben als Header
* Paging bei vielen Fenstern vier pro Seite
* Dynamische Quad Ansicht

  * 1 Quelle fuellt alles
  * 2 Quellen teilen 1 zu 1
  * 3 Quellen oben zwei unten eine
  * 4 Quellen als 2x2
* Einbettung lokaler Apps in ein Qt Widget
* Watchdogs und Heartbeats mit Auto Reload bzw. Neustart
* Zentraler Logger mit Rotationslog
* Setup Dialog mit

  * freier Anzahl Fenster 2 4 6 8 10
  * Typ pro Fenster Browser oder Lokal
  * Name je Fenster fuer die Navigation
  * URL Eingabe bzw. Exe Auswahl und Titelmuster
  * Orientierung der Navigation
  * Option Speichern in config.json

---

## Architektur und Ordner

Schichten: **UI**, **ViewModel leichtgewichtig in Main Window**, **Services**, **Utils**

```
kiosk_app/
  modules/
    main.py                     Einstieg mit Parametern
    ui/
      main_window.py            Hauptrahmen, Moduslogik, Paging
      sidebar.py                Navigation mit Seiten
      app_state.py              Zustand und Modi
      setup_dialog.py           Setup Dialog
    services/
      browser_services.py       QWebEngine und Heartbeat
      lcoal_app_service.py      Lokale App Host und Einbettung
    utils/
      config_loader.py          Laden und Speichern der Config
      win_embed.py              Win32 Hilfen SetParent, Suche
      logger.py                 Logging
  config.json                   Konfiguration
  requirements.txt
```

Hinweis zum Dateinamen: das Service Modul fuer lokale Apps heisst im Projekt **lcoal\_app\_service.py** passend zu den Importen.

---

## Voraussetzungen

* Windows 10 oder neuer
* Python 3.10 oder neuer mit Windows Launcher `py`
* Microsoft Visual C Plus Plus Redistributable wird von Qt WebEngine oft benoetigt

---

## Installation

Empfohlen mit virtueller Umgebung im Projektordner:

```powershell
cd .\kiosk_app
py -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Falls `pip` nicht gefunden wird:

```powershell
py -m ensurepip --upgrade
py -m pip install --upgrade pip
```

---

## Start und Parameter

Standardstart:

```powershell
py -m modules.main
```

Setup erzwungen, unabhaengig von der Config:

```powershell
py -m modules.main -setup
```

Eigenen Pfad zur Config Datei angeben:

```powershell
py -m modules.main --config "C:\Pfad\zu\config.json"
```

---

## Bedienung und Shortcuts

* **Strg 1 bis Strg 4** waehlt auf der aktuellen Seite die Quelle 1 bis 4
* **Strg Links Rechts** blättert die Seiten
* **Strg Q** wechselt Einzelansicht und Quad Ansicht
* **F11** Kiosk an aus
* **Schliessen in Vollbild** nur mit **Shift** beim Schliessen Signal

---

## Setup Dialog

Beim ersten Start oder mit `-setup` erscheint der Setup Dialog.

Du kannst definieren:

* Anzahl der Fenster 2 4 6 8 10
* Pro Zeile

  * Typ: Browser oder Lokal
  * Name: frei waehlbar. Er erscheint auf den Buttons
  * Browser: URL
  * Lokal: Pfad zur Exe und optional Titel Regex fuer die Fenstersuche
* Navigation links oder oben
* Optional: beim Bestaetigen in die Config Datei schreiben. Dann startet die App das naechste Mal direkt

---

## Konfiguration per Datei

Die App kann komplett ueber `config.json` gesteuert werden. Moderne Struktur mit `sources`:

```json
{
  "sources": [
    { "type": "browser", "name": "Google", "url": "https://www.google.com" },
    { "type": "local",   "name": "Editor", "launch_cmd": "C:\\\\Windows\\\\System32\\\\notepad.exe", "window_title_pattern": ".*(Editor|Notepad).*" },
    { "type": "browser", "name": "Mail",   "url": "https://mail.proton.me" }
  ],
  "ui": {
    "start_mode": "single",
    "sidebar_width": 96,
    "nav_orientation": "left",
    "show_setup_on_start": true
  },
  "kiosk": {
    "monitor_index": 0,
    "disable_system_keys": true,
    "kiosk_fullscreen": true
  },
  "browser_urls": ["https://www.google.com", "https://mail.proton.me"],
  "local_app": {
    "launch_cmd": "C:\\\\Windows\\\\System32\\\\notepad.exe",
    "embed_mode": "native_window",
    "window_title_pattern": ".*(Editor|Notepad).*",
    "web_url": null
  }
}
```

**Erläuterung der Felder**

* `sources` Liste in Anzeige Reihenfolge

  * `type` browser oder local
  * `name` Text fuer die Navigation
  * `url` nur fuer Browser
  * `launch_cmd` nur fuer lokale App. Voller Pfad zur Exe
  * `window_title_pattern` Regex fuer Fenstertitel um das Hauptfenster sicher zu finden
* `ui.nav_orientation` left oder top
* `ui.show_setup_on_start` zeigt beim Start den Setup Dialog
* Die Felder `browser_urls` und `local_app` bleiben fuer Rueckwaertskompatibilitaet erhalten

---

## Einbettung lokaler Software

Die App bettet klassische Win32 Fenster per **SetParent** in ein Qt Widget ein. Dabei werden Styles gesetzt und das Kind auf die Groesse des Eltern Widgets gebracht.

**Wichtige Hinweise**

* Rechteebene muss gleich sein. Starte die Kiosk App und die lokale App beide als normal oder beide als Administrator
* Bei manchen Programmen startet die Exe einen Hilfsprozess der das sichtbare Fenster erzeugt. Nutze dann das **Titel Regex** Feld um das Fenster sicher zu finden
* Notepad Standardpfad: `C:\Windows\System32\notepad.exe`. Bei 32 Bit Python auf 64 Bit Windows kann `C:\Windows\Sysnative\notepad.exe` hilfreich sein
* UWP Apps und manche moderne geschuetzte Fenster lassen sich nicht einbetten

---

## Stabilitaet und Monitoring

* **Browser Heartbeat** per HTTP GET. Bei Ausfall Auto Reload
* **Lokale App Watchdog** prueft Prozess. Bei Ende wird neu gestartet. Fenstersuche laeuft regelmaessig
* **Logging** nach `logs/kiosk.log` mit Rotation

---

## Sicherheit

* Laedt keine externen Plugins
* Inhalte laufen innerhalb der Qt WebEngine. Beachte Content Security Policies der Zielseiten
* Zugangsdaten nicht im Klartext in die Config schreiben. Empfehlung

  * Windows Credential Manager oder DPAPI verwenden und im Startskript in Umgebungsvariablen bereitstellen
  * Interne Seiten nach IP Whitelisting absichern

---

## Tests und Smoke Check

### Unit Tests

Falls im Projekt vorhanden, kannst du mit `pytest` ausfuehren:

```powershell
.\.venv\Scripts\python -m pip install pytest
.\.venv\Scripts\python -m pytest -q
```

### Schneller Smoke Check

1. Start mit Setup:

   ```powershell
   py -m modules.main -setup
   ```
2. Zwei Quellen anlegen

   * Browser mit bekannter URL
   * Lokale App Notepad
3. In der Anwendung

   * Strg Q wechselt die Modis
   * Strg 1 bis Strg 4 waehlt Fenster
   * Strg Links Rechts blaettert die Seiten
4. Trenne kurz die Netzwerkverbindung der Browserquelle. Nach kurzer Zeit sollte ein Reload erfolgen

---

## Fehlerbehebung

**Keine Fenster nach dem Speichern**

* Pruefe die Log Datei `logs/kiosk.log`
* Stelle sicher, dass im Setup gueltige URLs mit `http` oder `https` eingegeben wurden

**Lokale App oeffnet separat**

* `window_title_pattern` anpassen. Nimm einen eindeutigen Teil des Fenstertitels
* Starte Kiosk App und Programm mit gleicher Rechteebene
* Pruefe den Exe Pfad. Notepad Beispiel siehe oben

**PySide6 oder WebEngine Probleme**

* Stelle sicher, dass die Abhaengigkeiten aus `requirements.txt` installiert sind
* Setze bei Bedarf die Variable `QTWEBENGINE_DISABLE_SANDBOX=1` in der Umgebung

**pip nicht gefunden**

* `py -m ensurepip --upgrade`
* `py -m pip install --upgrade pip`

---

## Autostart unter Windows

### Ueber Aufgabenplanung

```powershell
$exe = "$pwd\.venv\Scripts\python.exe"
$dir = "$pwd"
$arg = "-m modules.main"
$task = "KioskApp"
schtasks /Create /TN $task /TR "`"$exe`" $arg" /SC ONLOGON /RL HIGHEST /F /WD "$dir"
```

### Ueber Autostart Ordner

Erstelle eine Verknuepfung in
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`
mit Ziel
`C:\Pfad\zu\python.exe -m modules.main`

Optional kannst du `-setup` anfuegen um beim naechsten Start die Konfiguration zu aendern.

---

## Lizenz und Hinweise

Diese Vorlage ist fuer interne Kiosk Szenarien gedacht. Die Einbettung von Drittsoftware kann lizenzrechtliche Vorgaben haben. Bitte beachte die Lizenzen der eingebetteten Anwendungen und der angezeigten Inhalte.

---