# modules/main.py
from __future__ import annotations

import sys
import argparse
import json
from pathlib import Path
from typing import Dict, Any

from PySide6.QtWidgets import QApplication, QDialog

from modules.utils.config_loader import load_config, save_config, Config
from modules.utils.logger import init_logging, get_logger
from modules.ui.app_state import AppState
from modules.ui.main_window import MainWindow
from modules.ui.setup_dialog import SetupDialog
from modules.utils.config_loader import Config, SourceSpec, UIConfig, KioskConfig

def _dict_to_config(d: Dict[str, Any]) -> Config:
    # Hilfsparser fuer das In Memory Ergebnis
    from modules.utils.config_loader import _parse_sources, _parse_ui, _parse_kiosk
    return Config(
        sources=_parse_sources(d),
        ui=_parse_ui(d),
        kiosk=_parse_kiosk(d),
    )



def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MultiScreen Kiosk")
    default_cfg = str((Path(__file__).resolve().parent / "config.json"))
    p.add_argument("--config", "-c", default=default_cfg, help="Pfad zur config.json")
    p.add_argument("--setup", action="store_true", help="Setup Dialog beim Start anzeigen")
    p.add_argument("--log-level", default=None, help="Log Level zB DEBUG INFO WARNING ERROR")
    return p.parse_args()


def _write_config_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def maybe_run_setup(app: QApplication, cfg: Config, cfg_path: Path, force: bool) -> Config | None:
    show = bool(force or (cfg.ui and getattr(cfg.ui, "show_setup_on_start", False)) or not cfg.sources)
    if not show:
        return cfg

    log = get_logger(__name__)
    dlg = SetupDialog(cfg)
    res_code = dlg.exec()
    if res_code != QDialog.Accepted:
        log.info("Setup abgebrochen. Anwendung wird beendet.", extra={"source": "setup"})
        return None

    payload = dlg.results()  # {"config": {...}, "should_save": bool}
    new_cfg_dict = payload.get("config", {})
    should_save = bool(payload.get("should_save", True))

    if should_save:
        try:
            from json import dump
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            with cfg_path.open("w", encoding="utf-8") as f:
                dump(new_cfg_dict, f, ensure_ascii=False, indent=2)
            log.info(f"Setup gespeichert in {cfg_path}", extra={"source": "setup"})
        except Exception as ex:
            log.error(f"Konnte Config nicht speichern: {ex}", extra={"source": "setup"})

    # Danach IMMER neu laden, damit wir ein Config Objekt bekommen
    try:
        new_cfg = load_config(cfg_path) if should_save else _dict_to_config(new_cfg_dict)
    except Exception as ex:
        log.error(f"Setup Ergebnis konnte nicht geladen werden: {ex}", extra={"source": "setup"})
        return None
    return new_cfg



def main() -> int:
    args = parse_args()

    # Logging frueh initialisieren, damit auch Setup Logs erfasst werden
    try:
        init_logging(None)
    except Exception:
        pass
    log = get_logger(__name__)
    log.info("app starting", extra={"source": "main"})

    app = QApplication(sys.argv)

    cfg_path = Path(args.config).resolve()
    cfg = load_config(cfg_path)

    # Optionales Setup. Bei Abbruch sofort beenden.
    cfg_after = maybe_run_setup(app, cfg, cfg_path, force=args.setup)
    if cfg_after is None:
        app.quit()
        return 0
    cfg = cfg_after

    # App State
    state = AppState()

    # Hauptfenster erstellen
    win = MainWindow(cfg, state)
    try:
        # Gewuenschten Monitor setzen
        if cfg.kiosk:
            win.show_on_monitor(getattr(cfg.kiosk, "monitor_index", 0))
        # Kiosk Vollbild
        if cfg.kiosk and getattr(cfg.kiosk, "kiosk_fullscreen", False):
            win.enter_kiosk()
    except Exception:
        pass

    win.show()
    log.info("ui shown", extra={"source": "main"})
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
