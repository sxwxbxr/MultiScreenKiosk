# MultiScreenKiosk

A production-ready fullscreen kiosk for Windows (Qt / PySide6 + Qt WebEngine).
Switch between single view and a 2×2 grid, embed websites and native Windows apps, and control everything from a clean sidebar or header. Includes a first-run setup, live logging tools, and a Window Spy to help you embed complex apps.

---

## Highlights

* **True kiosk fullscreen** (frameless, F11 toggle)
* **Navigation**: sidebar **left** or **top**, optional hamburger overlay
* **Layouts**: **Single** view or **Quad** 2×2; smart tiling when fewer than 4 panes
* **Sources per pane**

  * **Browser** via Qt WebEngine
  * **Local app** (native window embedding with Win32 `SetParent`), watchdog + auto-restart
* **First-run Setup** dialog to define sources (names, URLs, EXE + args, title/class regex)
* **Settings** inside the app: theme (light/dark), logo, placeholder GIF, orientation, hamburger
* **Placeholders** while web views load (optional custom GIF)
* **Keyboard**: Ctrl+1…4 select view, Ctrl+Q switch layout, F11 kiosk, Shift+Close to exit in kiosk
* **Logging tools**

  * Per-launch log file **`YYYYMMDD_N_Logfile.log`**
  * In-app **Log Viewer** (with filter, clear file)
  * **Log Stats** window (INFO/WARN/ERROR/DEBUG counters + live file size)
* **Window Spy** (from Settings) to inspect running windows (title, class, child class) for embedding

Target OS: **Windows 10 or newer**.

---

## Architecture (short)

* **UI** (PySide6): `MainWindow`, `Sidebar`, `SettingsDialog`, `SetupDialog`, `BrowserHostWidget`
* **ViewModel**: `AppState` (active index, mode)
* **Services**: `BrowserService` (per web view), `LocalAppService` (spawn + embed + watchdog)
* **Utils**: `config_loader`, `logger` (async queue, rotating files, UI bridge)

---

## Requirements

* Python **3.10–3.13** (x64)
* PySide6 with WebEngine

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Typical `requirements.txt`:

```
PySide6>=6.6
PySide6-Addons>=6.6
PySide6-Essentials>=6.6
```

> If WebEngine is missing, install `PySide6-Addons` as well.

---

## Getting started

```powershell
# first run (opens setup)
py -m modules.main --setup

# normal run
py -m modules.main
```

### Command line options

```
--config PATH     Use custom config path (default: modules/config.json)
--setup           Force opening the Setup dialog even if config exists
--log-level LVL   Override log level (DEBUG, INFO, WARNING, ERROR)
```

---

## First-run Setup

* Choose **number of panes**.
* For each pane:

  * **Browser**: set **Name** and **URL**.
  * **Local**: set **Name**, **EXE**, optional **Arguments**, and optionally:

    * **Window title regex** (e.g. `.*(Notepad|Editor).*`)
    * **Window class regex** (e.g. `XLMAIN` for Excel)
    * **Child class regex** (e.g. `Edit` for Notepad text control)
    * **Follow child processes** and **Global fallback** (advanced)
* Tick **Overwrite config** to write `modules/config.json`.

> The setup follows the app’s light/dark theme (custom color palettes do not affect setup).

---

## Configuration

Location: **`kiosk_app/modules/config.json`** (used by the app).

Example:

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

---

## Embedding local apps (tips)

* Works for classic Win32 desktop apps. UWP/Store apps and apps with custom compositors may refuse parenting.
* If the app does not embed immediately:

  1. Start it via this kiosk to track its **PID**.
  2. Use **Settings → Window Spy** to inspect title/class names.
  3. Fill **window\_title\_pattern** / **window\_class\_pattern** / **child\_window\_class\_pattern** in the config.
* Some apps resist resizing. The kiosk applies:

  * **Move/resize retries** with `SWP_NOSENDCHANGING`
  * Optional **child targeting** for rendering controls
  * DPI-aware sizing
* Running the kiosk **without admin** cannot re-parent **elevated** apps.

Examples:

* **Notepad**: title `.*(Notepad|Editor).*`, child class `Edit`
* **Excel**: class `XLMAIN`

---

## Shortcuts

* **Ctrl+1…4**: activate pane
* **Ctrl+Q**: switch Single ↔ Quad
* **Ctrl+← / Ctrl+→**: page previous/next (when more than 4 sources)
* **F11**: toggle kiosk fullscreen
* **Shift + Close**: allow close while in kiosk

---

## Logging

* Files under `%LOCALAPPDATA%\MultiScreenKiosk\logs`
* **Per launch** file name: `YYYYMMDD_N_Logfile.log` (N = 1, 2, 3 … on that day)
* Open **Settings → Logs** to view (filter + clear)
* **Log Statistics** shows level counts and **live file size** (updates every second)

---

## Building a single .exe (Windows)

Use **PyInstaller**:

```powershell
pip install pyinstaller
pyinstaller ^
  --name MultiScreenKiosk ^
  --noconsole ^
  --clean ^
  --onefile ^
  --add-data "kiosk_app/modules/config.json;modules" ^
  --collect-all PySide6 ^
  kiosk_app\modules\main.py
```

If WebEngine resources are not found at runtime, switch to a **one-folder** build and include Qt resources:

```powershell
pyinstaller ^
  --name MultiScreenKiosk ^
  --noconsole ^
  --clean ^
  --add-data "kiosk_app/modules/config.json;modules" ^
  --collect-all PySide6 ^
  kiosk_app\modules\main.py
```

Place the resulting `MultiScreenKiosk.exe` in a folder and test starting with `--setup` once.

---

## Autostart (optional)

Create a shortcut to `MultiScreenKiosk.exe` and place it in:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

---

## Troubleshooting

* **WebEngine fails to load** → ensure `PySide6-Addons` is installed.
* **App doesn’t embed** → run **Window Spy** and refine regex patterns; check app elevation and UWP limitations.
* **Sidebar overlays** → disable hamburger in Settings or use top orientation.
* **Nothing after setup** → check that `modules/config.json` contains a non-empty `sources` array.

---

## Roadmap (short)

* Encrypted secrets in `config.json`
* Profiles per monitor / multi-screen layouts
* Health dashboard and remote config update
* Crash-safe local app embedding presets for more apps

---

## License

MIT (or your preferred license). Replace this section with the actual license you choose.

---

## Credits

Built with **PySide6** and **Qt WebEngine**. Uses Win32 APIs (`SetParent`, `SetWindowPos`, etc.) for native window embedding.
