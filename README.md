# MultiScreenKiosk

A production-ready fullscreen kiosk for Windows built with Qt / PySide6 and Qt WebEngine. MultiScreenKiosk lets you combine web
content and native Windows applications in a polished kiosk experience that supports both single-view and 2×2 grid layouts.

---

## Table of contents

- [Highlights](#highlights)
- [Architecture at a glance](#architecture-at-a-glance)
- [System requirements](#system-requirements)
- [Development setup](#development-setup)
- [Running the kiosk](#running-the-kiosk)
  - [Command-line options](#command-line-options)
  - [First-run setup](#first-run-setup)
- [Configuration reference](#configuration-reference)
  - [Backup & restore](#backup--restore)
  - [Embedding local applications](#embedding-local-applications)
- [Keyboard shortcuts](#keyboard-shortcuts)
- [Logging](#logging)
- [Building a distributable](#building-a-distributable)
- [Autostarting on Windows](#autostarting-on-windows)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [License](#license)
- [Credits](#credits)

---

## Highlights

**Kiosk experience**

- Frameless fullscreen window with F11 toggle and a Shift+Close override for safe exits.
- Sidebar navigation docked on the left or top, optional hamburger overlay, and configurable logo/placeholder assets.

**Flexible layouts**

- Switch between a single-view layout and a quad 2×2 grid.
- Smart tiling gracefully handles configurations with fewer than four panes.

**Rich content sources**

- Embed websites with Qt WebEngine.
- Host native Win32 applications using the Windows `SetParent` API, complete with a watchdog and automatic restarts.
- Built-in Window Spy helps you collect the title/class details needed for complex embeddings.

**Configuration & theming**

- First-run setup wizard to define sources, URLs, executable paths, window-matching rules, and more.
- In-app Settings dialog lets you tune the theme (light/dark), layout, sidebar, placeholder animations, and keyboard mappings.

**Operations toolkit**

- Per-launch log files, live log viewer with filtering, and a log statistics dashboard (INFO/WARN/ERROR counters plus file size).
- Automatic update workflow with verification and rollback.

Target operating system: **Windows 10 or newer**.

---

## Architecture at a glance

- **UI (PySide6):** `MainWindow`, `Sidebar`, `SettingsDialog`, `SetupDialog`, `BrowserHostWidget`
- **View model:** `AppState` (active index, mode switching)
- **Services:** `BrowserService` (web views), `LocalAppService` (process spawning, embedding, and watchdog)
- **Utilities:** configuration loader and asynchronous logger with a bridge to the UI

---

## System requirements

- Python **3.10 – 3.13** (64-bit)
- PySide6 with WebEngine components

Install dependencies in a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
py -m pip install -r kiosk_app/modules/requirements.txt
```

> If WebEngine is missing, ensure `PySide6-Addons` is installed alongside `PySide6` and `PySide6-Essentials`.

---

## Development setup

1. Clone the repository and open a terminal in the project root.
2. Create and activate a Python virtual environment (see [System requirements](#system-requirements)).
3. Install the dependencies from `kiosk_app/modules/requirements.txt`.

The repository ships with a default configuration at `kiosk_app/modules/config.json`; you can modify it directly or use the
first-run wizard described below.

---

## Running the kiosk

Run commands from inside the `kiosk_app` directory:

```powershell
cd kiosk_app

# First run (opens setup wizard)
py -m modules.main --setup

# Normal run
py -m modules.main
```

### Command-line options

```text
--config PATH     Use a custom configuration file (default: kiosk_app/modules/config.json in development,
                  config.json next to the executable in packaged builds)
--setup           Force the setup dialog even if a configuration exists
--log-level LVL   Override log level (DEBUG, INFO, WARNING, ERROR)
```

### First-run setup

- Choose the number of panes for your kiosk layout.
- For each pane select the source type:
  - **Browser:** specify a name and URL.
  - **Local application:** provide the executable path, optional arguments, and window matching rules:
    - Window title regular expression
    - Window class regular expression
    - Child window class regular expression
    - Optional follow-child-process and global fallback modes
- Enable **Overwrite config** if you want to persist the result to `config.json`.
- The wizard honours the app’s light/dark theme.

---

## Configuration reference

The active configuration is stored at **`kiosk_app/modules/config.json`** in a source checkout or alongside the packaged
executable.

Example configuration snippet:

```json
{
  "sources": [
    { "type": "browser", "name": "Google", "url": "https://www.google.com" },
    {
      "type": "local",
      "name": "Editor",
      "launch_cmd": "C:\\Windows\\System32\\notepad.exe",
      "args": "",
      "embed_mode": "native_window",
      "window_title_pattern": ".*(Notepad|Editor).*",
      "window_class_pattern": "",
      "child_window_class_pattern": "Edit",
      "follow_children": true,
      "allow_global_fallback": false
    }
  ],
  "ui": {
    "start_mode": "quad",
    "sidebar_width": 96,
    "nav_orientation": "left",
    "show_setup_on_start": false,
    "enable_hamburger": true,
    "placeholder_enabled": true,
    "placeholder_gif_path": "",
    "theme": "light",
    "logo_path": ""
  },
  "kiosk": {
    "monitor_index": 0,
    "disable_system_keys": true,
    "kiosk_fullscreen": true
  }
}
```

### Backup & restore

Use **Settings → Backup config** to export the active configuration to a JSON file (default file name `config.json`).
Use **Settings → Restore config** to import a previously saved snapshot. The dialog validates the file, applies it immediately,
and rolls back automatically if validation or saving fails.

### Embedding local applications

- Works reliably with classic Win32 desktop applications. UWP/Store apps and applications with custom compositors may not allow
  parenting.
- If an app does not embed immediately:
  1. Launch it through MultiScreenKiosk to track its process ID.
  2. Use **Settings → Window Spy** to inspect the window title and class names.
  3. Update the `window_title_pattern`, `window_class_pattern`, or `child_window_class_pattern` fields accordingly.
- Some applications resist resizing. MultiScreenKiosk applies move/resize retries with `SWP_NOSENDCHANGING`, optional child
  targeting, and DPI-aware sizing. Running the kiosk without administrative rights cannot re-parent elevated applications.

Example patterns:

- **Notepad:** title `.*(Notepad|Editor).*`, child class `Edit`
- **Excel:** class `XLMAIN`

---

## Keyboard shortcuts

Default mappings (customizable in Settings):

- **Ctrl+1 … Ctrl+4** – activate pane
- **Ctrl+Q** – toggle between single and quad layouts
- **Ctrl+← / Ctrl+→** – switch pages when more than four sources exist
- **F11** – toggle kiosk fullscreen
- **Shift + Close** – allow closing while in kiosk mode

---

## Logging

- Logs are stored under `%LOCALAPPDATA%\MultiScreenKiosk\logs`.
- Each launch creates a file named `YYYYMMDD_N_Logfile.log` (where `N` increments per launch per day).
- Open **Settings → Logs** to view logs, filter entries, or clear the file.
- The **Log Statistics** window displays INFO/WARN/ERROR counters and live file size updates.

---

## Building a distributable

Create a standalone Windows executable with **PyInstaller**:

```powershell
py -m pip install pyinstaller
py -m PyInstaller ^
  --name MultiScreenKiosk ^
  --noconsole ^
  --clean ^
  --onefile ^
  --add-data "kiosk_app\modules\config.json;config.json" ^
  --add-data "kiosk_app\modules\assets;modules\assets" ^
  --collect-all PySide6 ^
  kiosk_app\modules\main.py
```

The first `--add-data` statement copies the default `config.json` next to the executable; the second bundles the splash-screen
assets so the JSON and GIF animation work in frozen builds.

If Qt WebEngine resources are missing at runtime, switch to a **one-folder** build (remove `--onefile`) and include the same data
paths.

Place the resulting `MultiScreenKiosk.exe` in a folder and start it once with `--setup` to generate a configuration.

---

## Autostarting on Windows

Create a shortcut to `MultiScreenKiosk.exe` and place it in:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

---

## Troubleshooting

- **WebEngine fails to load** – ensure `PySide6-Addons` is installed with WebEngine components.
- **Application does not embed** – run Window Spy and refine regex patterns; confirm the app is not elevated or UWP-only.
- **Sidebar overlaps content** – disable the hamburger menu in Settings or switch the navigation to the top.
- **Blank screen after setup** – verify that your active `config.json` contains at least one source definition.

---

## Roadmap

- Encrypted secrets in `config.json`
- Profiles per monitor and multi-screen layouts
- Health dashboard plus remote configuration updates
- Hardened presets for local app embedding

---

## License

MIT

---

## Credits

Built with **PySide6** and **Qt WebEngine**. Uses Win32 APIs (`SetParent`, `SetWindowPos`, and related calls) for native window
embedding.
