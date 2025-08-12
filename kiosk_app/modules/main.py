import sys
import os
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEngineProfile  # QtWebEngine init

from modules.utils.logger import init_logging, get_logger
from modules.utils.config_loader import load_config, Config
from modules.ui.app_state import AppState
from modules.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("KioskApp")
    app.setDesktopSettingsAware(True)

    log_dir = Path(os.getenv("KIOSK_LOG_DIR", ".")) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    init_logging(log_dir / "kiosk.log")
    log = get_logger(__name__)

    app_dir = Path(__file__).resolve().parent
    cfg_path = app_dir / "config.json"
    try:
        cfg: Config = load_config(cfg_path)
    except Exception as e:
        print(f"Konfiguration ungueltig: {e}\nPfad: {cfg_path}")
        return 1

    state = AppState(start_mode=cfg.ui.start_mode, active_index=0)

    win = MainWindow(cfg, state)
    win.show_on_monitor(cfg.kiosk.monitor_index)
    if cfg.kiosk.kiosk_fullscreen:
        win.enter_kiosk()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
