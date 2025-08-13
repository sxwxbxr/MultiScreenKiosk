# modules/utils/config_loader.py
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any, Dict

from modules.utils.logger import get_logger, LoggingConfig

log = get_logger(__name__)

# ===== Datenklassen =====

@dataclass
class SourceSpec:
    type: str                    # "browser" oder "local"
    name: str
    # Browser
    url: Optional[str] = None
    # Local App
    launch_cmd: Optional[str] = None
    embed_mode: str = "native_window"
    window_title_pattern: str = ""
    window_class_pattern: str = ""
    force_pattern_only: bool = False
    web_url: Optional[str] = None

@dataclass
class UIConfig:
    start_mode: str = "quad"                # "single" oder "quad"
    sidebar_width: int = 96
    nav_orientation: str = "left"           # left oder top
    show_setup_on_start: bool = False
    enable_hamburger: bool = True
    placeholder_enabled: bool = False
    placeholder_gif_path: str = ""
    theme: str = "light"                    # light oder dark
    logo_path: str = ""

@dataclass
class KioskConfig:
    monitor_index: int = 0
    disable_system_keys: bool = True
    kiosk_fullscreen: bool = True

@dataclass
class Config:
    sources: List[SourceSpec] = field(default_factory=list)
    ui: UIConfig = field(default_factory=UIConfig)
    kiosk: KioskConfig = field(default_factory=KioskConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

# ===== Laden und Speichern =====

_DEFAULT_PATH = os.path.join(os.getcwd(), "config.json")

def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _to_sources(items: List[Dict[str, Any]]) -> List[SourceSpec]:
    out: List[SourceSpec] = []
    for it in items or []:
        out.append(SourceSpec(
            type=str(it.get("type", "browser")),
            name=str(it.get("name", "Quelle")),
            url=it.get("url"),
            launch_cmd=it.get("launch_cmd"),
            embed_mode=str(it.get("embed_mode", "native_window")),
            window_title_pattern=str(it.get("window_title_pattern", "")),
            window_class_pattern=str(it.get("window_class_pattern", "")),
            force_pattern_only=bool(it.get("force_pattern_only", False)),
            web_url=it.get("web_url"),
        ))
    return out

def _to_ui(obj: Dict[str, Any]) -> UIConfig:
    return UIConfig(
        start_mode=str(obj.get("start_mode", "quad")),
        sidebar_width=int(obj.get("sidebar_width", 96)),
        nav_orientation=str(obj.get("nav_orientation", "left")),
        show_setup_on_start=bool(obj.get("show_setup_on_start", False)),
        enable_hamburger=bool(obj.get("enable_hamburger", True)),
        placeholder_enabled=bool(obj.get("placeholder_enabled", False)),
        placeholder_gif_path=str(obj.get("placeholder_gif_path", "")),
        theme=str(obj.get("theme", "light")),
        logo_path=str(obj.get("logo_path", "")),
    )

def _to_kiosk(obj: Dict[str, Any]) -> KioskConfig:
    return KioskConfig(
        monitor_index=int(obj.get("monitor_index", 0)),
        disable_system_keys=bool(obj.get("disable_system_keys", True)),
        kiosk_fullscreen=bool(obj.get("kiosk_fullscreen", True)),
    )

def _to_logging(obj: Dict[str, Any]) -> LoggingConfig:
    return LoggingConfig(
        level=str(obj.get("level", "INFO")),
        fmt=str(obj.get("fmt", "plain")),
        dir=obj.get("dir"),
        filename=str(obj.get("filename", "kiosk.log")),
        rotate_max_bytes=int(obj.get("rotate_max_bytes", 5 * 1024 * 1024)),
        rotate_backups=int(obj.get("rotate_backups", 5)),
        console=bool(obj.get("console", True)),
        qt_messages=bool(obj.get("qt_messages", True)),
        mask_keys=tuple(obj.get("mask_keys", ["password", "token", "authorization", "auth", "secret"])),
        memory_buffer=int(obj.get("memory_buffer", 2000)),
        enable_qt_bridge=bool(obj.get("enable_qt_bridge", True)),
    )

def load_config(path: str = _DEFAULT_PATH) -> Config:
    try:
        raw = _load_json(path)
    except FileNotFoundError:
        log.warning("config file not found at %s. using defaults", path, extra={"source": "config"})
        return Config()
    except Exception as ex:
        log.error("failed to read config %s: %s", path, ex, extra={"source": "config"})
        return Config()

    cfg = Config(
        sources=_to_sources(raw.get("sources", [])),
        ui=_to_ui(raw.get("ui", {})),
        kiosk=_to_kiosk(raw.get("kiosk", {})),
        logging=_to_logging(raw.get("logging", {})),
    )
    return cfg

def save_config(cfg: Config, path: str = _DEFAULT_PATH) -> None:
    data = {
        "sources": [asdict(s) for s in cfg.sources],
        "ui": asdict(cfg.ui),
        "kiosk": asdict(cfg.kiosk),
        "logging": asdict(cfg.logging),
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log.info("config saved to %s", path, extra={"source": "config"})
    except Exception as ex:
        log.error("failed to save config %s: %s", path, ex, extra={"source": "config"})
