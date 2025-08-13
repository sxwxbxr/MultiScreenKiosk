# modules/main.py
from __future__ import annotations
import sys
import argparse

from PySide6.QtWidgets import QApplication, QMessageBox, QDialog

from modules.utils.config_loader import load_config, save_config, Config
from modules.utils.logger import init_logging, get_logger, set_global_level
from modules.ui.app_state import AppState, ViewMode
from modules.ui.main_window import MainWindow
from modules.ui.setup_dialog import SetupDialog


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="kiosk_app",
        description="MultiScreen Kiosk Anwendung"
    )
    p.add_argument("--setup", "-setup", action="store_true",
                   help="Setup Dialog beim Start anzeigen")
    p.add_argument("--config", "-c", default="config.json",
                   help="Pfad zur config.json")
    p.add_argument("--log-level", "-l", default=None,
                   help="Log Level ueberschreiben, z. B. DEBUG INFO WARNING ERROR")
    return p.parse_args(argv)


def _target_mode_from_cfg(cfg: Config) -> ViewMode:
    return ViewMode.SINGLE if str(cfg.ui.start_mode).lower() == "single" else ViewMode.QUAD


def apply_start_mode_to_state(state: AppState, cfg: Config) -> None:
    """Setzt den Startmodus ohne direkt die Property zu schreiben."""
    target = _target_mode_from_cfg(cfg)
    current = getattr(state, "mode", None)

    if current == target:
        return

    if hasattr(state, "set_mode"):
        try:
            state.set_mode(target)
            return
        except Exception:
            pass
    if hasattr(state, "setMode"):
        try:
            state.setMode(target)
            return
        except Exception:
            pass

    if hasattr(state, "toggle_mode"):
        try:
            state.toggle_mode()
        except Exception:
            pass


def maybe_run_setup(cfg: Config, cfg_path: str, force: bool) -> Config:
    """Zeigt optional den Setup Dialog an und speichert Aenderungen."""
    want = bool(force or cfg.ui.show_setup_on_start)
    if not want:
        return cfg

    log = get_logger(__name__)
    dlg = SetupDialog(cfg)
    res = dlg.exec()
    if res == QDialog.Accepted:
        try:
            data = dlg.results()
            if isinstance(data, dict):
                if "sources" in data and data["sources"]:
                    cfg.sources = data["sources"]
                if "ui" in data and data["ui"]:
                    ui = data["ui"]
                    if "nav_orientation" in ui:
                        cfg.ui.nav_orientation = ui["nav_orientation"]
                    if "sidebar_width" in ui:
                        cfg.ui.sidebar_width = int(ui["sidebar_width"])
                    if "enable_hamburger" in ui:
                        cfg.ui.enable_hamburger = bool(ui["enable_hamburger"])
                    if "theme" in ui:
                        cfg.ui.theme = str(ui["theme"])
                    if "start_mode" in ui:
                        cfg.ui.start_mode = str(ui["start_mode"])
            save_config(cfg, cfg_path)
            log.info("setup saved to %s", cfg_path, extra={"source": "setup"})
        except Exception as ex:
            log.error("setup save failed: %s", ex, extra={"source": "setup"})
            QMessageBox.critical(None, "Fehler", f"Setup konnte nicht gespeichert werden:\n{ex}")
    return cfg


def main(argv=None) -> int:
    args = parse_args(argv)

    # Config laden und Logging initialisieren
    cfg = load_config(args.config)
    init_logging(cfg.logging)
    log = get_logger(__name__)
    if args.log_level:
        set_global_level(args.log_level)

    log.info("app starting", extra={"source": "main"})

    app = QApplication(sys.argv)

    # Optional Setup Dialog
    cfg = maybe_run_setup(cfg, args.config, force=args.setup)

    # App State und Startmodus
    state = AppState()
    apply_start_mode_to_state(state, cfg)

    # Hauptfenster bauen
    try:
        win = MainWindow(cfg, state)
    except Exception as ex:
        log.error("MainWindow init failed: %s", ex, extra={"source": "main"}, exc_info=True)
        QMessageBox.critical(None, "Startfehler", f"MainWindow konnte nicht erstellt werden:\n{ex}")
        return 2

    # Auf gewaehltem Monitor anzeigen
    try:
        win.show_on_monitor(cfg.kiosk.monitor_index)
    except Exception:
        pass

    # Kiosk Vollbild
    if cfg.kiosk.kiosk_fullscreen:
        try:
            win.enter_kiosk()
        except Exception:
            win.show()
    else:
        win.show()

    log.info("ui shown", extra={"source": "main"})
    rc = app.exec()
    log.info("app exit with code %s", rc, extra={"source": "main"})
    return rc


if __name__ == "__main__":
    sys.exit(main())
