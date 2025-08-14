from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Any, Dict
import json

from modules.utils.logger import get_logger

log = get_logger(__name__)


# ---------------- Paths ----------------

def default_config_path() -> Path:
    """
    Standardpfad: modules/config.json
    """
    # Diese Datei liegt in modules/utils -> parents[1] ist modules/
    return Path(__file__).resolve().parents[1] / "config.json"


# ---------------- Models ----------------

@dataclass
class SourceSpec:
    type: str                      # "browser" oder "local"
    name: str
    # Browser
    url: Optional[str] = None
    # Local App
    launch_cmd: Optional[str] = None
    embed_mode: str = "native_window"
    window_title_pattern: Optional[str] = None
    window_class_pattern: Optional[str] = None
    force_pattern_only: bool = False
    web_url: Optional[str] = None


@dataclass
class UIConfig:
    start_mode: str = "quad"                   # "single" oder "quad"
    sidebar_width: int = 96
    nav_orientation: str = "left"              # "left" oder "top"
    show_setup_on_start: bool = False
    enable_hamburger: bool = True
    placeholder_enabled: bool = True
    placeholder_gif_path: str = ""
    theme: str = "dark"                        # "light" oder "dark"
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


# ---------------- Parsing ----------------

def _source_from_dict(d: Dict[str, Any]) -> SourceSpec:
    return SourceSpec(
        type=d.get("type", "browser"),
        name=d.get("name", "Unbenannt"),
        url=d.get("url"),
        launch_cmd=d.get("launch_cmd"),
        embed_mode=d.get("embed_mode", "native_window"),
        window_title_pattern=d.get("window_title_pattern"),
        window_class_pattern=d.get("window_class_pattern"),
        force_pattern_only=d.get("force_pattern_only", False),
        web_url=d.get("web_url"),
    )


def _ui_from_dict(d: Dict[str, Any]) -> UIConfig:
    ui = UIConfig()
    for k in asdict(ui).keys():
        if k in d:
            setattr(ui, k, d[k])
    return ui


def _kiosk_from_dict(d: Dict[str, Any]) -> KioskConfig:
    kz = KioskConfig()
    for k in asdict(kz).keys():
        if k in d:
            setattr(kz, k, d[k])
    return kz


# ---------------- API ----------------

def load_config(path: Optional[str | Path] = None) -> Config:
    """
    Laedt die Konfiguration. Standard ist modules/config.json.
    """
    cfg_path = Path(path) if path else default_config_path()
    if not cfg_path.exists():
        log.info(f"config file not found at {cfg_path}. creating defaults", extra={"source": "config"})
        cfg = default_config()
        save_config(cfg, cfg_path)
        return cfg

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as ex:
        log.error(f"failed to read config {cfg_path}: {ex}", extra={"source": "config"})
        return default_config()

    cfg = Config()
    # sources
    srcs = data.get("sources", [])
    cfg.sources = [_source_from_dict(s) for s in srcs]
    # ui
    cfg.ui = _ui_from_dict(data.get("ui", {}))
    # kiosk
    cfg.kiosk = _kiosk_from_dict(data.get("kiosk", {}))

    return cfg


def save_config(cfg: Config, path: Optional[str | Path] = None) -> None:
    """
    Speichert die Konfiguration. Standard ist modules/config.json.
    """
    cfg_path = Path(path) if path else default_config_path()
    try:
        # sauberes Dict ohne None Felder in Sources
        out: Dict[str, Any] = {
            "sources": [
                {k: v for k, v in asdict(s).items() if v is not None and v != ""}
                for s in cfg.sources
            ],
            "ui": asdict(cfg.ui),
            "kiosk": asdict(cfg.kiosk),
        }
        cfg_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"config saved to {cfg_path}", extra={"source": "config"})
    except Exception as ex:
        log.error(f"failed to save config {cfg_path}: {ex}", extra={"source": "config"})


def default_config() -> Config:
    # Minimal 1 Browser als Beispiel
    return Config(
        sources=[SourceSpec(type="browser", name="Browser 1", url="https://www.google.com")],
        ui=UIConfig(),
        kiosk=KioskConfig(),
    )
