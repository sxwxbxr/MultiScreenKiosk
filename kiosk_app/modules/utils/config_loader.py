import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional

from modules.utils.logger import get_logger

NavOrientation = Literal["left", "top"]

# Beschreibt eine Quelle in der Reihenfolge, wie sie in der UI angezeigt wird
@dataclass
class SourceSpec:
    type: Literal["browser", "local"]
    name: str
    url: Optional[str] = None             # fuer browser
    launch_cmd: Optional[str] = None      # fuer lokal
    window_title_pattern: Optional[str] = None

@dataclass
class UIConfig:
    start_mode: Literal["single", "quad"] = "single"
    sidebar_width: int = 96
    nav_orientation: NavOrientation = "left"
    show_setup_on_start: bool = True

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
    # Rueckwaertskompatibel: browser_urls und local_app bleiben erhalten
    browser_urls: List[str]
    local_app: LocalAppConfigData
    ui: UIConfig
    kiosk: KioskConfig
    sources: List[SourceSpec] = None      # neu: komplette Liste aller Fenster

def _domain_to_label(u: str) -> str:
    try:
        host = u.split("//", 1)[1].split("/", 1)[0]
        core = host.split(".")[-2]
        return core.capitalize()
    except Exception:
        return "Quelle"

def _validate(cfg: dict) -> Config:
    log = get_logger(__name__)

    # Neuer Weg: bevorzugt "sources"
    raw_sources = cfg.get("sources")
    sources: List[SourceSpec] = []
    browser_urls: List[str] = []

    if isinstance(raw_sources, list) and len(raw_sources) >= 1:
        for i, s in enumerate(raw_sources):
            t = s.get("type")
            name = (s.get("name") or f"Quelle {i+1}").strip()
            if t == "browser":
                url = s.get("url")
                if not url or not isinstance(url, str) or not url.startswith("http"):
                    raise ValueError(f"sources[{i}] browser ohne gueltige url")
                sources.append(SourceSpec(type="browser", name=name, url=url))
                browser_urls.append(url)
            elif t == "local":
                cmd = s.get("launch_cmd")
                if not cmd or not isinstance(cmd, str):
                    raise ValueError(f"sources[{i}] local ohne launch_cmd")
                rx = s.get("window_title_pattern") or ""
                sources.append(SourceSpec(type="local", name=name, launch_cmd=cmd, window_title_pattern=rx))
            else:
                raise ValueError(f"sources[{i}] ungueltiger type: {t}")
    else:
        # Rueckfall auf alte Felder fuer Abwaertskompatibilitaet
        b = cfg.get("browser_urls", [])
        if not isinstance(b, list) or not (1 <= len(b) <= 4):
            raise ValueError("browser_urls muss Liste mit 1 bis 4 Eintraegen sein")
        for i, u in enumerate(b):
            if not isinstance(u, str) or not u.startswith("http"):
                raise ValueError(f"browser_urls[{i}] muss mit http beginnen")
        browser_urls = b

        names = cfg.get("ui", {}).get("sidebar_titles")
        if not isinstance(names, list) or not names:
            names = [_domain_to_label(u) for u in browser_urls]

        # bis zu drei Browser plus eine lokale App
        for i, u in enumerate(browser_urls):
            nm = names[i] if i < len(names) else _domain_to_label(u)
            sources.append(SourceSpec(type="browser", name=nm, url=u))

        la_old = cfg.get("local_app", {})
        if la_old.get("launch_cmd"):
            sources.append(SourceSpec(
                type="local",
                name="Lokal",
                launch_cmd=la_old["launch_cmd"],
                window_title_pattern=la_old.get("window_title_pattern", ".*")
            ))

    # local_app fuer Services fuellen, falls nicht gesetzt
    la_cfg = cfg.get("local_app", {})
    if not la_cfg.get("launch_cmd"):
        for s in sources:
            if s.type == "local":
                la_cfg = {
                    "launch_cmd": s.launch_cmd,
                    "embed_mode": "native_window",
                    "window_title_pattern": s.window_title_pattern or ".*"
                }
                break
    if not la_cfg.get("launch_cmd"):
        # minimaler Default, damit das Schema komplett ist
        la_cfg = {
            "launch_cmd": "C:\\Windows\\System32\\notepad.exe",
            "embed_mode": "native_window",
            "window_title_pattern": ".*(Editor|Notepad).*"
        }

    ui_raw = cfg.get("ui", {})
    nav = ui_raw.get("nav_orientation", "left")
    if nav not in ("left", "top"):
        nav = "left"

    ui = UIConfig(
        start_mode=ui_raw.get("start_mode", "single"),
        sidebar_width=int(ui_raw.get("sidebar_width", 96)),
        nav_orientation=nav,
        show_setup_on_start=bool(ui_raw.get("show_setup_on_start", True))
    )

    kiosk_raw = cfg.get("kiosk", {})
    kiosk = KioskConfig(
        monitor_index=int(kiosk_raw.get("monitor_index", 0)),
        disable_system_keys=bool(kiosk_raw.get("disable_system_keys", True)),
        kiosk_fullscreen=bool(kiosk_raw.get("kiosk_fullscreen", True)),
    )

    return Config(
        browser_urls=browser_urls,
        local_app=LocalAppConfigData(
            launch_cmd=la_cfg["launch_cmd"],
            embed_mode=la_cfg.get("embed_mode", "native_window"),
            window_title_pattern=la_cfg.get("window_title_pattern", ""),
            web_url=la_cfg.get("web_url")
        ),
        ui=ui,
        kiosk=kiosk,
        sources=sources
    )

def load_config(path: Path) -> Config:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return _validate(data)

def save_config(path: Path, cfg: Config):
    """Speichert die moderne Struktur mit 'sources' und zusaetzlich die Legacy Felder."""
    out = {
        "sources": [
            (
                {"type": "browser", "name": s.name, "url": s.url}
                if s.type == "browser"
                else {"type": "local", "name": s.name, "launch_cmd": s.launch_cmd,
                      "window_title_pattern": s.window_title_pattern}
            )
            for s in (cfg.sources or [])
        ],
        "ui": {
            "start_mode": cfg.ui.start_mode,
            "sidebar_width": cfg.ui.sidebar_width,
            "nav_orientation": cfg.ui.nav_orientation,
            "show_setup_on_start": cfg.ui.show_setup_on_start
        },
        "kiosk": {
            "monitor_index": cfg.kiosk.monitor_index,
            "disable_system_keys": cfg.kiosk.disable_system_keys,
            "kiosk_fullscreen": cfg.kiosk.kiosk_fullscreen
        },
        # Legacy Beibehaltung fuer aelteren Code
        "browser_urls": cfg.browser_urls,
        "local_app": {
            "launch_cmd": cfg.local_app.launch_cmd,
            "embed_mode": cfg.local_app.embed_mode,
            "window_title_pattern": cfg.local_app.window_title_pattern,
            "web_url": cfg.local_app.web_url
        }
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
