# modules/main.py
from __future__ import annotations

import sys
import argparse
import json
from pathlib import Path
from typing import Dict, Any

from PySide6.QtWidgets import QApplication, QDialog

from modules.utils.config_loader import load_config, save_config, Config, LoggingSettings
from modules.utils.logger import init_logging, get_logger
from modules.ui.app_state import AppState
from modules.ui.main_window import MainWindow
from modules.ui.setup_dialog import SetupDialog
from modules.ui.splash_screen import SplashScreen
from modules.utils.config_loader import Config
from modules.utils.i18n import i18n, tr


def default_cfg_path() -> Path:
    if getattr(sys, "frozen", False):
        # Pfad neben der EXE
        return Path(sys.executable).resolve().parent / "config.json"
    # Dev Modus wie bisher
    return Path(__file__).resolve().parent / "config.json"


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
    default_cfg = str(default_cfg_path())
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

    cfg_path = Path(args.config).resolve()
    cfg = load_config(cfg_path)

    logging_cfg = getattr(cfg, "logging", None)
    if args.log_level:
        if logging_cfg:
            logging_cfg.level = args.log_level
        else:
            logging_cfg = LoggingSettings(level=args.log_level)
            cfg.logging = logging_cfg

    try:
        init_logging(logging_cfg)
    except Exception:
        try:
            init_logging(None)
        except Exception:
            pass

    log = get_logger(__name__)
    log.info("app starting", extra={"source": "main"})

    app = QApplication(sys.argv)

    # Optionales Setup. Bei Abbruch sofort beenden.
    cfg_after = maybe_run_setup(app, cfg, cfg_path, force=args.setup)
    if cfg_after is None:
        app.quit()
        return 0
    cfg = cfg_after

    # Sprache setzen
    try:
        i18n.set_language(getattr(cfg.ui, "language", "") or i18n.get_language())
    except Exception:
        pass

    # Splash Screen
    splash = None
    assets_dir = Path(__file__).resolve().parent / "assets"
    splash_json = assets_dir / "tZuFzJlE5P.json"
    splash_gif = assets_dir / "tZuFzJlE5P.gif"
    try:
        splash = SplashScreen(
            json_path=splash_json,
            gif_path=splash_gif,
            message=tr("Preparing your displays…"),
        )
        splash.show()
        app.processEvents()
    except Exception as ex:
        log.warning("could not display splash screen: %s", ex, extra={"source": "main"})
        splash = None

    # App State
    state = AppState()

    # Hauptfenster erstellen
    try:
        win = MainWindow(cfg, state, config_path=cfg_path)
    except Exception:
        if splash:
            splash.finish(None)
        raise

    try:
        if cfg.kiosk:
            win.show_on_monitor(getattr(cfg.kiosk, "monitor_index", 0))
    except Exception:
        pass

    should_enter_kiosk = bool(cfg.kiosk and getattr(cfg.kiosk, "kiosk_fullscreen", False))

    def _present_main_window():
        if getattr(_present_main_window, "_done", False):
            return
        _present_main_window._done = True  # type: ignore[attr-defined]

        try:
            if win.isMinimized() or not win.isVisible():
                win.showNormal()
        except Exception:
            pass

        if should_enter_kiosk:
            try:
                win.enter_kiosk()
            except Exception:
                pass
        else:
            try:
                win.show()
            except Exception:
                pass

        if splash:
            splash.finish(win)
        else:
            try:
                win.raise_()
                win.activateWindow()
            except Exception:
                pass

        log.info("ui shown", extra={"source": "main"})

    _present_main_window._done = False  # type: ignore[attr-defined]
    win.initial_load_finished.connect(_present_main_window)
    if getattr(win, "_initial_loading_complete", False):  # pragma: no cover - defensive
        _present_main_window()

    try:
        win.showMinimized()
    except Exception:
        win.show()

    result = app.exec()
    if splash:
        splash.finish(win)
    return result


if __name__ == "__main__":
    sys.exit(main())
