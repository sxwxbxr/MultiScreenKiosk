# modules/main.py
from __future__ import annotations

import sys
import argparse

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from modules.utils.logger import init_logging, get_logger, set_global_level, LoggingConfig
from modules.utils.config_loader import load_config, save_config, Config
from modules.ui.app_state import AppState, ViewMode
from modules.ui.main_window import MainWindow


def _apply_start_mode_to_state(state: AppState, cfg: Config) -> None:
    """Setzt den gewuenschten Startmodus, ohne die Property direkt zu setzen."""
    want = ViewMode.QUAD if (getattr(cfg.ui, "start_mode", "single") == "quad") else ViewMode.SINGLE
    # nur umschalten wenn noetig
    if getattr(state, "mode", None) != want:
        state.toggle_mode()


def _maybe_run_setup(cfg: Config, force: bool) -> Config:
    """Zeigt optional den Setup Dialog und speichert die Config."""
    show = force or bool(getattr(cfg.ui, "show_setup_on_start", False))
    if not show:
        return cfg

    try:
        from modules.ui.setup_dialog import SetupDialog
    except Exception:
        # kein Setup Dialog vorhanden
        return cfg

    # Signatur robust behandeln
    try:
        dlg = SetupDialog(cfg)
    except TypeError:
        dlg = SetupDialog()

    if dlg.exec():
        try:
            res = dlg.results()
        except Exception:
            res = None

        if isinstance(res, Config):
            cfg = res
        elif isinstance(res, dict):
            # Mindestens sources uebernehmen, Rest beibehalten
            if "sources" in res and isinstance(res["sources"], list):
                cfg.sources = res["sources"]

        try:
            save_config(cfg)  # modules/config.json
        except Exception:
            pass

    return cfg


def main(argv: list[str] | None = None) -> int:
    # ---- Argumente
    ap = argparse.ArgumentParser(prog="kiosk", add_help=True)
    ap.add_argument("--setup", action="store_true", help="Setup Dialog beim Start anzeigen")
    ap.add_argument("--config", type=str, default=None, help="Pfad zu einer alternativen config.json")
    ap.add_argument("--log-level", type=str, default="INFO", help="Log Level: DEBUG, INFO, WARNING, ERROR")
    args = ap.parse_args(argv)

    # ---- Logging frueh initialisieren (ohne cfg.logging Abhaengigkeit)
    init_logging(LoggingConfig(level=args.log_level))
    log = get_logger(__name__)
    log.info("app starting", extra={"source": "main"})

    # ---- Qt App
    app = QApplication(sys.argv)
    # High DPI Attribute: in Qt6 teils deprecated, aber unkritisch
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)   # type: ignore[attr-defined]
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)      # type: ignore[attr-defined]
    except Exception:
        pass

    # ---- Config laden und ggf. Setup
    cfg = load_config(args.config)
    cfg = _maybe_run_setup(cfg, force=args.setup)

    # ---- App State und Window
    state = AppState()
    _apply_start_mode_to_state(state, cfg)

    try:
        win = MainWindow(cfg, state)
    except Exception as ex:
        # freundliche Fehlermeldung
        m = QMessageBox()
        m.setIcon(QMessageBox.Critical)
        m.setWindowTitle("Startfehler")
        m.setText(f"MainWindow konnte nicht erstellt werden:\n{ex}")
        m.exec()
        return 1

    # Monitor und Kiosk
    try:
        win.show_on_monitor(cfg.kiosk.monitor_index)
    except Exception:
        pass

    win.show()

    try:
        if bool(getattr(cfg.kiosk, "kiosk_fullscreen", True)):
            win.enter_kiosk()
    except Exception:
        pass

    rc = app.exec()
    log.info("app exiting", extra={"source": "main"})
    return int(rc)


if __name__ == "__main__":
    sys.exit(main())
