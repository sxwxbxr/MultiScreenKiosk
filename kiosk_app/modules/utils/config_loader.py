import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional

from modules.utils.logger import get_logger

@dataclass
class UIConfig:
    start_mode: Literal["single", "quad"] = "single"
    sidebar_width: int = 96
    sidebar_titles: List[str] = None

@dataclass
class KioskConfig:
    monitor_index: int = 0
    disable_system_keys: bool = True
    kiosk_fullscreen: bool = True

@dataclass
class LocalAppConfigData:
    launch_cmd: str
    embed_mode: Literal["native_window", "sdk", "web"] = "native_window"
    window_title_pattern: str = ""
    web_url: Optional[str] = None

@dataclass
class Config:
    browser_urls: List[str]
    local_app: LocalAppConfigData
    ui: UIConfig
    kiosk: KioskConfig

def _domain_to_label(u: str) -> str:
    try:
        host = u.split("//", 1)[1].split("/", 1)[0]
        core = host.split(".")[-2]
        return core.capitalize()
    except Exception:
        return "Quelle"

def _validate(cfg: dict) -> Config:
    log = get_logger(__name__)
    b = cfg.get("browser_urls", [])
    if not isinstance(b, list) or len(b) != 3:
        raise ValueError("browser_urls muss Liste mit drei Eintraegen sein")
    for i, u in enumerate(b):
        if not isinstance(u, str) or not u.startswith("http"):
            raise ValueError(f"browser_urls[{i}] muss mit http beginnen")

    la = cfg.get("local_app", {})
    if not la.get("launch_cmd"):
        raise ValueError("local_app.launch_cmd fehlt")

    ui = cfg.get("ui", {})
    kiosk = cfg.get("kiosk", {})

    titles = ui.get("sidebar_titles")
    if not isinstance(titles, list) or len(titles) != 4:
        gen = [_domain_to_label(x) for x in b]
        gen.append("Lokal")
        titles = gen
        log.warning("ui.sidebar_titles fehlt oder ungueltig. Nutze %s", titles)

    return Config(
        browser_urls=b,
        local_app=LocalAppConfigData(
            launch_cmd=la["launch_cmd"],
            embed_mode=la.get("embed_mode", "native_window"),
            window_title_pattern=la.get("window_title_pattern", ""),
            web_url=la.get("web_url"),
        ),
        ui=UIConfig(
            start_mode=ui.get("start_mode", "single"),
            sidebar_width=int(ui.get("sidebar_width", 96)),
            sidebar_titles=titles,
        ),
        kiosk=KioskConfig(
            monitor_index=int(kiosk.get("monitor_index", 0)),
            disable_system_keys=bool(kiosk.get("disable_system_keys", True)),
            kiosk_fullscreen=bool(kiosk.get("kiosk_fullscreen", True)),
        ),
    )

def load_config(path: Path) -> Config:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    cfg = _validate(data)
    return cfg
