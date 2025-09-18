# Changelog

All notable changes since [v0.9.0-rc1](https://github.com/sxwxbxr/MultiScreenKiosk/releases/tag/v0.9.0-rc1).

## [main]

### Added
- Introduced interactive content scheduling with a dedicated editor dialog, runtime scheduler, and conflict reporting so panes can rotate through named sources on a timetable.
- Added configuration backup and restore actions in the settings dialog, including validation of imported files and persistence helpers in the main window.
- Added a shortcut editor and runtime support for customizable keyboard mappings so operators can redefine pane selection and kiosk toggles.
- Added a remote log export service with HTTP/SFTP/email destinations, archive retention controls, optional compression, and a configuration dialog for on-demand or scheduled uploads.
- Added an automatic update workflow that checks release feeds, downloads and verifies packages, installs updates with rollback handling, and reports results back to the UI.
- Added a startup splash screen with Lottie/GIF animation support, readiness tracking, and a fallback timer that keeps the window hidden until the kiosk is ready.
- Added multilingual UI support powered by packaged translation assets and a runtime language manager so operators can switch between English and German.

### Changed
- Packaged builds now bundle default configuration and asset files, seeding them beside the executable on first run so setup can start with sensible defaults.
- The startup sequence keeps the kiosk minimized until content is ready, repeatedly forces the window to the foreground, and guarantees the splash screen closes even when embeds stall.
- Layout handling honours configurations that disable split screen, ensuring the kiosk boots directly into single-view mode when requested.

### Fixed
- Scheduling now recalculates pane assignments on the fly, logging conflicts and updating displays so local Win32 embeds follow the intended timetable without getting stuck.
- Hardened the initial loading tracker so every embed eventually marks itself ready or times out, preventing the splash screen from blocking access to diagnostics like Window Spy.

### Documentation
- Added detailed English and German operation manuals covering installation, setup, backups, and daily use.
- Reworked the project README with updated highlights, architecture notes, and troubleshooting guidance.
