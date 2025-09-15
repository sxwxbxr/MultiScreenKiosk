# MultiScreenKiosk – Installation, Configuration and Operation Guide

## Installation

1. **Requirements**
   - Windows 10 or newer
2. **Download**
   - Fetch the latest release from the project page.
3. **Start**
   - Unzip if necessary and run `MultiScreenKiosk.exe`.

## Configuration

1. **First run**
   - `MultiScreenKiosk.exe --setup`
   - Dialog to define **number of panes** and **sources**.
2. **Configuration file**
   - Path: `kiosk_app/modules/config.json`
   - Example structure:
     ```json
     {
       "sources": [{"type": "browser", "name": "Google", "url": "https://www.google.com"}],
       "ui": {"start_mode": "single", "shortcuts": {}},
       "kiosk": {"monitor_index": 0, "kiosk_fullscreen": true}
     }
     ```
   - Alternatively generate via the setup dialog.

## Operation

1. **Start**
   - Default: `MultiScreenKiosk.exe`
   - Options:
     - `--config PATH` – use custom config path
     - `--setup` – force the setup dialog
     - `--log-level LVL` – override log level (DEBUG, INFO, …)
2. **Keyboard shortcuts**
   - `Ctrl+1…4` – select pane
   - `Ctrl+Q` – toggle single/quad view
   - `F11` – toggle kiosk fullscreen
   - `Shift + Close` – allow exit in kiosk mode
3. **Logging**
   - Log files stored under `%LOCALAPPDATA%\\MultiScreenKiosk\\logs`
   - Per launch: `YYYYMMDD_N_Logfile.log`
