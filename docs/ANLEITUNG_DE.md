# MultiScreenKiosk – Bedienhandbuch

## 1. Überblick
MultiScreenKiosk ist eine Windows-Kiosk-Anwendung, die Web-Inhalte und klassische Desktop-Programme entweder in einem Einzelbild oder in einem 2×2-Raster anzeigen kann. Die Anwendung enthält einen Einrichtungsassistenten, frei belegbare Tastenkürzel, automatische Updates, Inhaltsplanung sowie Werkzeuge für einen stabilen Dauerbetrieb.

## 2. Voraussetzungen
- Windows 10 oder neuer (64-Bit)
- Benutzerkonto mit Berechtigung zum Installieren und Ausführen von Win32-Anwendungen
- Python 3.10–3.13 für Entwickler-Checkouts (für das Paket nicht erforderlich)
- Netzwerkzugang für externe Inhalte, Log-Exporte und Update-Downloads (optional)

## 3. Download und Installation
1. Öffnen Sie die [MultiScreenKiosk-Releases](https://github.com/sxwxbxr/MultiScreenKiosk/releases).
2. Laden Sie das aktuelle Paket `MultiScreenKiosk-win64.zip` herunter.
3. Entpacken Sie das Archiv in ein beschreibbares Verzeichnis, z. B. `C:\\Program Files\\MultiScreenKiosk` oder `%LOCALAPPDATA%\\Programs\\MultiScreenKiosk`.
4. Starten Sie `MultiScreenKiosk.exe`. Beim ersten Start öffnet sich automatisch der Einrichtungsassistent.
5. Heften Sie die EXE an das Startmenü oder richten Sie eine geplante Aufgabe ein, wenn der Kiosk nach einem Neustart automatisch starten soll.

## 4. Ersteinrichtung mit Assistent
Starten Sie `MultiScreenKiosk.exe --setup`, um den Assistenten jederzeit erneut aufzurufen.

1. **Layout wählen** – Entscheiden Sie sich für *Einzelansicht* oder *Vierer-Raster*. Eine Vorschau zeigt die Belegung der Fenster.
2. **Quellen hinzufügen** – Für jedes Fenster steht einer der folgenden Typen zur Verfügung:
   - **Browser** – Vergeben Sie einen Anzeigenamen und die Ziel-URL. Erweiterte Optionen ermöglichen Cache-Bereinigung und Reload-Intervalle.
   - **Lokale Anwendung** – Geben Sie den Pfad zur ausführbaren Datei, optionale Argumente sowie Fenstererkennungsregeln (Titel-/Klassenmuster und Child-Klasse) an. Aktivieren Sie *Child-Prozess folgen*, wenn Hilfsprogramme gestartet werden.
3. **Zeitpläne konfigurieren (optional)** – Öffnen Sie den Reiter **Zeitplanung**, legen Sie benannte Rotationen an und ziehen Sie Quellen auf den Zeitplan. Der Assistent markiert Konflikte und zeigt an, welche Fenster auf ihre statische Belegung zurückfallen.
4. **Kiosk-Optionen anpassen** – Wählen Sie Standard-Theme (hell/dunkel), Ausrichtung der Seitenleiste, Platzhalter-Animation, Splash-Screen-Grafik und Tastenkürzel-Profil.
5. **Konfiguration speichern** – Bestätigen Sie das Speichern der `config.json`. Paketierte Builds legen die Datei neben der EXE ab, Entwickler-Checkouts unter `kiosk_app/modules/config.json`.

## 5. Kiosk starten
- Doppelklicken Sie `MultiScreenKiosk.exe` für den Normalbetrieb.
- Über `--config PFAD` laden Sie eine alternative Konfigurationsdatei.
- Mit `--setup` erzwingen Sie den Assistenten, auch wenn bereits eine Konfiguration existiert.
- Über `--log-level DEBUG|INFO|WARNING|ERROR` passen Sie die Protokoll-Verbosity zur Laufzeit an.

## 6. Bedienung im Alltag
### Layout und Navigation
- Die Seitenleiste listet alle konfigurierten Quellen. Ein Klick oder Tastenkürzel aktiviert die Quelle im fokussierten Fenster.
- Im Splitscreen markiert ein farbiger Rahmen das aktive Fenster. Mit *Viererlayout umschalten* wechseln Sie zwischen Einzel- und Rasteransicht.
- Ein Splash-Screen blendet das Hauptfenster aus, bis alle Quellen bereit sind oder ein Sicherheits-Timeout erreicht wird.

### Tastenkürzel
| Tastenkombination | Aktion |
| --- | --- |
| `Ctrl+1…4` | Fenster 1–4 fokussieren |
| `Ctrl+Q` | Einzel- und Vierfachansicht umschalten |
| `Ctrl+Shift+R` | Aktives Fenster neu laden |
| `F11` | Kiosk-Vollbild an/aus |
| `Shift + Schließen` | Kiosk im Vollbild beenden |
| Eigene Belegung | Über **Einstellungen → Tastenkürzel** anpassen |

## 7. Inhalte verwalten
- Öffnen Sie **Einstellungen → Quellen**, um Einträge zu bearbeiten, neu anzuordnen oder zu entfernen. Änderungen greifen sofort.
- Aktivieren Sie **Zeitplanung**, um mehrere Quellen in einem Fenster rotieren zu lassen. Jede Rotation kann ganztägig oder innerhalb eines Zeitfensters laufen. Der Scheduler löst Überschneidungen automatisch auf und protokolliert Konflikte.
- Nutzen Sie **Platzhalter-Animation**, um Markenbilder oder Animationen während des Ladens oder bei inaktiven Fenstern anzuzeigen.

## 8. Konfiguration sichern und wiederherstellen
- Wählen Sie **Einstellungen → Config sichern**, um die aktuelle Konfiguration als JSON-Snapshot zu exportieren. Bewahren Sie die Datei sicher oder auf einem Netzlaufwerk auf.
- Nutzen Sie **Einstellungen → Config wiederherstellen**, um einen gespeicherten Stand zu importieren. Die Anwendung prüft die Datei, übernimmt sie sofort und stellt bei Fehlern automatisch die vorherige Konfiguration wieder her.

## 9. Protokolle und Überwachung
- Lokale Logdateien liegen unter `%LOCALAPPDATA%\\MultiScreenKiosk\\logs`. Jeder Start erzeugt eine Datei mit Zeitstempel.
- Über **Einstellungen → Log-Viewer** lassen sich Logs live verfolgen, filtern und Fehlerzähler einsehen.
- Konfigurieren Sie **Einstellungen → Log-Export**, um Uploads per HTTPS, SFTP oder E-Mail zu verschicken. Legen Sie Ziel, Authentifizierung, Kompression und Aufbewahrungsdauer fest. Uploads können manuell oder zeitgesteuert erfolgen.

## 10. Automatische Updates
- Paketierte Installationen prüfen beim Start und täglich um Mitternacht auf neue Versionen. Verfügbare Updates laden im Hintergrund.
- Nach erfolgreicher Prüfung fordert der Kiosk zur Installation auf oder wartet auf das definierte Wartungsfenster.
- Schlägt ein Update fehl, setzt der Rollback-Mechanismus automatisch die vorherige Version wieder ein.
- Über **Einstellungen → Updates** lassen sich automatische Updates deaktivieren oder auf manuelle Downloads umstellen.

## 11. Sprache und Lokalisierung
- MultiScreenKiosk wird mit englischen und deutschen Übersetzungen ausgeliefert.
- Unter **Einstellungen → Sprache** ändern Sie die Oberfläche. Texte werden ohne Neustart aktualisiert.
- Eigene Übersetzungen können Sie als `.qm`-Dateien im Verzeichnis `translations` neben der EXE ablegen.

## 12. Fehlerbehebung und Wiederherstellung
- Halten Sie `Shift` gedrückt, während Sie auf das Schließen-Symbol klicken, um den Vollbildmodus zu verlassen, falls Bedienelemente verborgen sind.
- Wenn eine eingebettete Anwendung nicht skaliert, überprüfen Sie die Fenstererkennungsregeln oder aktivieren Sie den Modus *Globaler Fallback* für diese Quelle.
- Zum Zurücksetzen benennen oder löschen Sie die aktive `config.json` und starten die Anwendung neu. Der Assistent erscheint mit Standardwerten.
- Kontrollieren Sie das Log-Verzeichnis auf Absturzberichte und Warnungen des Schedulers. Remote-Exporte enthalten die gleichen Diagnosen für entfernte Teams.
- Für Autostart-Aufgaben stellen Sie sicher, dass das Konto Desktopzugriff besitzt. Aktivieren Sie gegebenenfalls *Nur ausführen, wenn der Benutzer angemeldet ist* in der Aufgabenplanung.

## 13. Weitere Ressourcen
- Projektdokumentation und Quellcode: <https://github.com/sxwxbxr/MultiScreenKiosk>
- Issue-Tracker für Fehlermeldungen: <https://github.com/sxwxbxr/MultiScreenKiosk/issues>
