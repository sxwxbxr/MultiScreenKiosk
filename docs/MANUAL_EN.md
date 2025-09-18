# MultiScreenKiosk – Operator Manual

## 1. Overview
MultiScreenKiosk is a Windows kiosk application that can display web content and classic desktop programs either in a single-pane layout or in a 2×2 grid. The application ships with a setup wizard, configurable keyboard shortcuts, automatic updates, content scheduling, and tooling that helps operators keep installations healthy over the long term.

## 2. Requirements
- Windows 10 or newer (64-bit)
- A user account with permission to install and run Win32 applications
- Python 3.10–3.13 for development checkouts (not required for packaged releases)
- Network access for remote content, log exports, and update downloads (optional)

## 3. Download and Installation
1. Visit the [MultiScreenKiosk releases](https://github.com/sxwxbxr/MultiScreenKiosk/releases) page.
2. Download the latest `MultiScreenKiosk-win64.zip` package.
3. Extract the archive to a writable directory, e.g. `C:\\Program Files\\MultiScreenKiosk` or `%LOCALAPPDATA%\\Programs\\MultiScreenKiosk`.
4. Launch `MultiScreenKiosk.exe`. The first run opens the setup wizard automatically.
5. Pin the executable or create a scheduled task if the kiosk should start automatically after a reboot.

## 4. First-Time Setup Wizard
Launch `MultiScreenKiosk.exe --setup` to reopen the wizard at any time.

1. **Select layout** – Choose between *Single view* or *Quad grid*. The wizard previews how sources fill the panes.
2. **Add sources** – For each pane pick one of the following source types:
   - **Browser** – Enter a display name and the target URL. Optional advanced settings cover cache busting and kiosk reload intervals.
   - **Local application** – Provide the executable path, optional command-line arguments, and window matching rules (title/class patterns and child window class). Enable *Follow child process* when launching helper executables.
3. **Configure scheduling (optional)** – Switch to the **Scheduling** tab, create named rotations, and drag sources onto the timetable. The wizard highlights conflicts and indicates panes that fall back to their static assignment.
4. **Adjust kiosk options** – Choose the default theme (light/dark), sidebar orientation, placeholder animation, startup splash artwork, and keyboard shortcut profile.
5. **Save configuration** – Confirm to write the resulting `config.json`. Packaged builds store the file next to the executable. Development checkouts write to `kiosk_app/modules/config.json`.

## 5. Starting the Kiosk
- Double-click `MultiScreenKiosk.exe` for normal operation.
- Pass `--config PATH` to load an alternative configuration file.
- Use `--setup` to force the setup wizard even when a configuration already exists.
- Supply `--log-level DEBUG|INFO|WARNING|ERROR` to override the verbosity of runtime logging.

## 6. Daily Operation
### Layout and navigation
- The sidebar lists every configured source. Click an entry or use shortcuts to activate it in the focused pane.
- When split mode is enabled, the active pane is marked by a coloured border. Use *Toggle quad layout* to switch between a single focused pane and the 2×2 grid.
- A splash screen hides the kiosk window until all panes report that their content is ready or a safety timeout elapses.

### Keyboard shortcuts
| Shortcut | Action |
| --- | --- |
| `Ctrl+1…4` | Focus pane 1–4 |
| `Ctrl+Q` | Toggle single vs. quad view |
| `Ctrl+Shift+R` | Reload the active pane |
| `F11` | Toggle kiosk fullscreen |
| `Shift + Close` | Close the kiosk while in fullscreen mode |
| Custom mappings | Configure via **Settings → Shortcuts** |

## 7. Managing Content
- Open **Settings → Sources** to edit, reorder, or remove existing entries. Changes apply instantly.
- Enable **Scheduling** to rotate through multiple sources in the same pane. Each rotation can run all day or during a defined window. The scheduler resolves overlaps automatically and writes any conflicts to the log.
- Use **Placeholder animation** to provide branded imagery while panes load or when no source is active.

## 8. Configuration Backups and Restore
- Choose **Settings → Backup config** to export the active configuration to a JSON snapshot. Store the file on a secure drive or network share.
- Select **Settings → Restore config** to import a saved snapshot. The kiosk validates the file, applies the new configuration immediately, and reverts to the previous version if validation fails.

## 9. Logs and Monitoring
- Local log files live in `%LOCALAPPDATA%\\MultiScreenKiosk\\logs`. Each launch produces a timestamped log.
- View logs live via **Settings → Log viewer**, which supports filtering, tailing, and error counters.
- Configure remote uploads through **Settings → Log export**. Supported transports include HTTPS, SFTP, and email. Define the target endpoint, authentication, compression, and retention window. Uploads can be triggered manually or scheduled.

## 10. Automatic Updates
- Packaged builds poll the release feed on startup and at midnight. Available updates download in the background.
- After verification the kiosk prompts for installation or waits for a configured maintenance window.
- If the update fails, the rollback mechanism restores the previous version automatically.
- Disable automatic updates or switch to manual downloads via **Settings → Updates**.

## 11. Language and Localization
- MultiScreenKiosk ships with English and German translations.
- Change the interface language under **Settings → Language**. The kiosk reloads UI strings immediately without restarting.
- Custom translation packs can be deployed by placing `.qm` files in the `translations` directory next to the executable.

## 12. Troubleshooting and Recovery
- Press `Shift` while clicking the close icon to exit fullscreen if standard UI controls are hidden.
- If an embedded application fails to resize, review the window matching rules or enable the *Global fallback* mode for that source.
- To reset the kiosk, delete or rename the active `config.json` and restart. The wizard appears again with default values.
- Check the log folder for crash reports and scheduler warnings. Remote exports include the same diagnostics for remote teams.
- When running as an autostart task, ensure the account has permission to interact with the desktop; otherwise, enable *Run only when user is logged on* in Task Scheduler.

## 13. Further Resources
- Project documentation and source: <https://github.com/sxwxbxr/MultiScreenKiosk>
- Issue tracker for bug reports: <https://github.com/sxwxbxr/MultiScreenKiosk/issues>
