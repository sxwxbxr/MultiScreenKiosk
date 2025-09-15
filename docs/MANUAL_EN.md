# MultiScreenKiosk – Step-by-Step Guide

## 1. Download and Installation
1. Open the project's release page.
   - *Screenshot: release page*
2. Download `MultiScreenKiosk-win64.zip`.
   - *Screenshot: download*
3. Extract the ZIP to a folder of your choice.
   - *Screenshot: extracted folder*
4. Double-click `MultiScreenKiosk.exe` to launch it.
   - *Screenshot: launching the EXE*

## 2. Initial Setup
1. Start the setup via `MultiScreenKiosk.exe --setup`.
   - *Screenshot: setup launch*
2. Choose the **number of panes**.
   - *Screenshot: pane selection*
3. Add a source for each pane (e.g., URL).
   - *Screenshot: add source*
4. Save the dialog – the file `kiosk_app/modules/config.json` is created.
   - *Screenshot: save*

## 3. Starting with an Existing Configuration
1. Run `MultiScreenKiosk.exe` without parameters.
   - *Screenshot: program start*
2. Optional: use `--config PATH` to supply a custom configuration.
   - *Screenshot: custom config*

## 4. Operation
1. **Keyboard shortcuts**
   - `Ctrl+1…4` – select pane
   - `Ctrl+Q` – toggle single/quad view
   - `F11` – toggle kiosk fullscreen
   - `Shift + Close` – exit in kiosk mode
   - *Screenshot: user interface*
2. **Logging**
   - Logs: `%LOCALAPPDATA%\\MultiScreenKiosk\\logs`
   - *Screenshot: log folder*
