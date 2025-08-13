import sys
import os
import argparse
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog

from modules.utils.logger import init_logging, get_logger
from modules.utils.config_loader import load_config, save_config, Config, SourceSpec
from modules.ui.app_state import AppState
from modules.ui.main_window import MainWindow
from modules.ui.setup_dialog import SetupDialog


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="kiosk_app", add_help=True)
    parser.add_argument("-setup", "--setup", action="store_true",
                        help="Setup beim Start anzeigen, unabhaengig von der Config")
    parser.add_argument("--config", type=str, default=None,
                        help="Pfad zur config.json")
    return parser.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])

    app = QApplication(sys.argv)
    app.setApplicationName("KioskApp")
    app.setDesktopSettingsAware(True)

    log_dir = Path(os.getenv("KIOSK_LOG_DIR", ".")) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    init_logging(log_dir / "kiosk.log")
    log = get_logger(__name__)

    app_dir = Path(__file__).resolve().parent
    cfg_path = Path(args.config) if args.config else (app_dir / "config.json")

    try:
        cfg: Config = load_config(cfg_path)
    except Exception as e:
        print(f"Konfiguration ungueltig: {e}\nPfad: {cfg_path}")
        return 1

    # Setup Dialog optional oder erzwungen per Parameter
    force_setup = bool(args.setup)
    if cfg.ui.show_setup_on_start or force_setup:
        if force_setup:
            print("[Info] Setup wurde per Parameter erzwungen (-setup).")
        dlg = SetupDialog(
            parent=None,
            initial_urls=cfg.browser_urls,
            initial_local_cmd=cfg.local_app.launch_cmd
        )
        if dlg.exec() == QDialog.Accepted:
            res = dlg.results()
            # Quellen uebernehmen
            new_sources = []
            new_browser_urls = []
            for s in res["sources"]:
                if s["type"] == "browser":
                    new_sources.append(SourceSpec(type="browser", name=s["name"], url=s["url"]))
                    new_browser_urls.append(s["url"])
                else:
                    new_sources.append(SourceSpec(
                        type="local",
                        name=s["name"],
                        launch_cmd=s["launch_cmd"],
                        window_title_pattern=s.get("window_title_pattern", "")
                    ))
            cfg.sources = new_sources
            cfg.browser_urls = new_browser_urls
            cfg.ui.nav_orientation = res["orientation"]

            if res["save_to_file"]:
                # Wenn gespeichert wird, schalten wir das Setup fuer kuenftige Starts ab.
                # Per Parameter kannst du es jederzeit erneut erzwingen.
                cfg.ui.show_setup_on_start = False
                try:
                    save_config(cfg_path, cfg)
                    print(f"[Info] Konfiguration gespeichert: {cfg_path}")
                except Exception as e:
                    print(f"Speichern fehlgeschlagen: {e}")

    state = AppState(start_mode=cfg.ui.start_mode, active_index=0)

    win = MainWindow(cfg, state)
    win.show_on_monitor(cfg.kiosk.monitor_index)
    if cfg.kiosk.kiosk_fullscreen:
        win.enter_kiosk()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
