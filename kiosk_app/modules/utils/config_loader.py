# modules/utils/config_loader.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# =========================
# Datenklassen
# =========================

@dataclass
class SourceSpec:
    # type: "browser" oder "local"
    type: str
    name: str

    # Browser
    url: Optional[str] = None

    # Lokale App
    launch_cmd: Optional[str] = None
    args: Optional[str] = ""

    embed_mode: str = "native_window"
    window_title_pattern: Optional[str] = None
    window_class_pattern: Optional[str] = None
    child_window_class_pattern: Optional[str] = None
    child_window_title_pattern: Optional[str] = None

    follow_children: bool = True
    allow_global_fallback: bool = False

    # Optional fuer "web" Einbettung
    web_url: Optional[str] = None


@dataclass
class UISettings:
    start_mode: str = "quad"                 # "single" oder "quad"
    sidebar_width: int = 96
    nav_orientation: str = "left"            # "left" oder "top"
    show_setup_on_start: bool = False
    enable_hamburger: bool = True
    placeholder_enabled: bool = True
    placeholder_gif_path: str = ""
    theme: str = "light"                     # "light" oder "dark"
    logo_path: str = ""


@dataclass
class KioskSettings:
    monitor_index: int = 0
    disable_system_keys: bool = True
    kiosk_fullscreen: bool = True


@dataclass
class LoggingSettings:
    level: str = "INFO"                      # DEBUG, INFO, WARNING, ERROR
    fmt: str = "plain"                       # "plain" oder "json"
    dir: Optional[str] = None                # Zielordner
    filename: str = "kiosk.log"
    rotate_max_bytes: int = 5 * 1024 * 1024  # 5 MB
    rotate_backups: int = 5
    console: bool = True
    qt_messages: bool = True
    # Hinweis: weitere Felder aus deinem Logger koennen hier spaeter ergaenzt werden


@dataclass
class Config:
    sources: List[SourceSpec] = field(default_factory=list)
    ui: UISettings = field(default_factory=UISettings)
    kiosk: KioskSettings = field(default_factory=KioskSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)


# Kompatibilitaetsaliasse fuer bestehende Imports in deinem Projekt
UIConfig = UISettings
KioskConfig = KioskSettings
LoggingConfig = LoggingSettings

__all__ = [
    "Config",
    "SourceSpec",
    "UISettings",
    "KioskSettings",
    "LoggingSettings",
    "UIConfig",
    "KioskConfig",
    "LoggingConfig",
    "load_config",
    "save_config",
    "_parse_sources",
    "_parse_ui",
    "_parse_kiosk",
    "_parse_logging",
]

# =========================
# Parser Hilfen
# =========================

def _safe_str(x: Any, default: str = "") -> str:
    if x is None:
        return default
    try:
        return str(x)
    except Exception:
        return default

def _as_bool(d: Dict[str, Any], key: str, default: bool) -> bool:
    try:
        v = d.get(key, default)
        return bool(v)
    except Exception:
        return default

def _as_int(d: Dict[str, Any], key: str, default: int) -> int:
    try:
        return int(d.get(key, default))
    except Exception:
        return default

# =========================
# Parser
# =========================

def _parse_sources(data: Dict[str, Any]) -> List[SourceSpec]:
    """
    Versteht:
      - neues Schema: { "sources": [ { type, name, ... } ] }
      - altes Schema: { "browser_urls": [...], "local_app": {...} }
      - Minimalobjekt: { "count": N } -> N Browser Eintraege mit Google
    """
    out: List[SourceSpec] = []

    # Neues Schema
    srcs = data.get("sources")
    if isinstance(srcs, list):
        for i, item in enumerate(srcs):
            if not isinstance(item, dict):
                continue
            typ = (_safe_str(item.get("type")) or "browser").lower()
            name = _safe_str(item.get("name")) or f"Quelle {i+1}"
            if typ == "browser":
                url = _safe_str(item.get("url")) or "about:blank"
                out.append(SourceSpec(
                    type="browser",
                    name=name,
                    url=url
                ))
            elif typ == "local":
                out.append(SourceSpec(
                    type="local",
                    name=name,
                    launch_cmd=_safe_str(item.get("launch_cmd")),
                    args=_safe_str(item.get("args")),
                    embed_mode=_safe_str(item.get("embed_mode") or "native_window"),
                    window_title_pattern=_safe_str(item.get("window_title_pattern") or "") or None,
                    window_class_pattern=_safe_str(item.get("window_class_pattern") or "") or None,
                    child_window_class_pattern=_safe_str(item.get("child_window_class_pattern") or "") or None,
                    child_window_title_pattern=_safe_str(item.get("child_window_title_pattern") or "") or None,
                    follow_children=_as_bool(item, "follow_children", True),
                    allow_global_fallback=_as_bool(item, "allow_global_fallback", False),
                    web_url=_safe_str(item.get("web_url") or "") or None,
                ))
            else:
                # Unbekannter Typ -> vorsichtig als Browser behandeln
                out.append(SourceSpec(
                    type="browser",
                    name=name,
                    url=_safe_str(item.get("url") or "about:blank")
                ))
        if out:
            return out

    # Altes Schema
    urls = data.get("browser_urls")
    if isinstance(urls, list):
        for i, u in enumerate(urls):
            out.append(SourceSpec(
                type="browser",
                name=f"Browser {i+1}",
                url=_safe_str(u) or "about:blank"
            ))

    la = data.get("local_app")
    if isinstance(la, dict) and la:
        out.append(SourceSpec(
            type="local",
            name="Lokale App",
            launch_cmd=_safe_str(la.get("launch_cmd")),
            args=_safe_str(la.get("args")),
            embed_mode=_safe_str(la.get("embed_mode") or "native_window"),
            window_title_pattern=_safe_str(la.get("window_title_pattern") or "") or None,
            window_class_pattern=_safe_str(la.get("window_class_pattern") or "") or None,
            child_window_class_pattern=_safe_str(la.get("child_window_class_pattern") or "") or None,
            child_window_title_pattern=_safe_str(la.get("child_window_title_pattern") or "") or None,
            follow_children=True,
            allow_global_fallback=_as_bool(la, "allow_global_fallback", False),
            web_url=_safe_str(la.get("web_url") or "") or None,
        ))

    # Minimalobjekt Heuristik
    if not out and isinstance(data, dict) and isinstance(data.get("count"), int):
        n = max(1, int(data["count"]))
        log.warning("config enthaelt nur 'count'. Erzeuge %d Browser Quellen als Defaults.", n)
        for i in range(n):
            out.append(SourceSpec(
                type="browser",
                name=f"Browser {i+1}",
                url="https://www.google.com"
            ))

    return out


def _parse_ui(data: Dict[str, Any]) -> UISettings:
    ui = data.get("ui") or {}
    return UISettings(
        start_mode=_safe_str(ui.get("start_mode") or "quad"),
        sidebar_width=_as_int(ui, "sidebar_width", 96),
        nav_orientation=_safe_str(ui.get("nav_orientation") or "left"),
        show_setup_on_start=_as_bool(ui, "show_setup_on_start", False),
        enable_hamburger=_as_bool(ui, "enable_hamburger", True),
        placeholder_enabled=_as_bool(ui, "placeholder_enabled", True),
        placeholder_gif_path=_safe_str(ui.get("placeholder_gif_path") or ""),
        theme=_safe_str(ui.get("theme") or "light"),
        logo_path=_safe_str(ui.get("logo_path") or ""),
    )


def _parse_kiosk(data: Dict[str, Any]) -> KioskSettings:
    kz = data.get("kiosk") or {}
    return KioskSettings(
        monitor_index=_as_int(kz, "monitor_index", 0),
        disable_system_keys=_as_bool(kz, "disable_system_keys", True),
        kiosk_fullscreen=_as_bool(kz, "kiosk_fullscreen", True),
    )


def _parse_logging(data: Dict[str, Any]) -> LoggingSettings:
    lg = data.get("logging") or {}
    return LoggingSettings(
        level=_safe_str(lg.get("level") or "INFO"),
        fmt=_safe_str(lg.get("fmt") or "plain"),
        dir=_safe_str(lg.get("dir") or "") or None,
        filename=_safe_str(lg.get("filename") or "kiosk.log"),
        rotate_max_bytes=_as_int(lg, "rotate_max_bytes", 5 * 1024 * 1024),
        rotate_backups=_as_int(lg, "rotate_backups", 5),
        console=_as_bool(lg, "console", True),
        qt_messages=_as_bool(lg, "qt_messages", True),
    )

# =========================
# Defaults
# =========================

def _defaults_config() -> Config:
    return Config(
        sources=[
            SourceSpec(type="browser", name="Google", url="https://www.google.com"),
            SourceSpec(type="browser", name="ChatGPT", url="https://chat.openai.com"),
            SourceSpec(type="browser", name="Proton", url="https://mail.proton.me"),
            SourceSpec(
                type="local", name="Editor",
                launch_cmd="C:\\Windows\\System32\\notepad.exe",
                window_title_pattern=".*(Notepad|Editor).*",
                child_window_class_pattern="Edit",
            ),
        ],
        ui=UISettings(),
        kiosk=KioskSettings(),
        logging=LoggingSettings(),
    )

# =========================
# Oeffentliche API
# =========================

def load_config(path: Path) -> Config:
    """
    Laedt eine Config von Pfad. Heilt fehlende Felder und erzeugt bei Bedarf Defaults.
    """
    try:
        if not path.exists():
            log.info("config file not found at %s. using defaults", path)
            return _defaults_config()

        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        cfg = Config(
            sources=_parse_sources(raw),
            ui=_parse_ui(raw),
            kiosk=_parse_kiosk(raw),
            logging=_parse_logging(raw),
        )

        if not cfg.sources:
            log.warning("keine Quellen in Config erkannt. verwende Defaults.")
            cfg = _defaults_config()

        return cfg
    except Exception as ex:
        log.error("Fehler beim Laden der Config: %s. Verwende Defaults.", ex)
        return _defaults_config()


def save_config(path: Path, cfg: Config | Dict[str, Any]) -> None:
    """
    Schreibt die Config als JSON. Akzeptiert entweder ein Config Objekt oder ein dict.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data: Dict[str, Any]
        if isinstance(cfg, dict):
            data = cfg
        else:
            data = asdict(cfg)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as ex:
        log.error("Konnte Config nicht speichern: %s", ex)
        raise
