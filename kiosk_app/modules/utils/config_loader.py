# modules/utils/config_loader.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Standard Tastaturkuerzel
DEFAULT_SHORTCUTS: Dict[str, str] = {
    "select_1": "Ctrl+1",
    "select_2": "Ctrl+2",
    "select_3": "Ctrl+3",
    "select_4": "Ctrl+4",
    "next_page": "Ctrl+Right",
    "prev_page": "Ctrl+Left",
    "toggle_mode": "Ctrl+Q",
    "toggle_kiosk": "F11",
}

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
    split_enabled: bool = True               # Splitscreen erlauben
    sidebar_width: int = 96
    nav_orientation: str = "left"            # "left" oder "top"
    show_setup_on_start: bool = False
    enable_hamburger: bool = True
    placeholder_enabled: bool = True
    placeholder_gif_path: str = ""
    theme: str = "light"                     # "light" oder "dark"
    language: str = ""                       # z.B. "de" oder "en"; leer = Systemstandard
    logo_path: str = ""
    shortcuts: Dict[str, str] = field(default_factory=lambda: DEFAULT_SHORTCUTS.copy())


@dataclass
class KioskSettings:
    monitor_index: int = 0
    disable_system_keys: bool = True
    kiosk_fullscreen: bool = True


@dataclass
class RemoteLogDestination:
    type: str = "http"                       # "http", "sftp" oder "email"
    name: str = ""                           # Anzeigename fuer UI / Logs
    enabled: bool = True
    url: Optional[str] = None                # HTTP Ziel
    method: str = "POST"
    headers: Dict[str, str] = field(default_factory=dict)
    verify_tls: bool = True
    timeout: int = 30
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    host: Optional[str] = None               # fuer SFTP / SMTP
    port: Optional[int] = None
    remote_path: Optional[str] = None        # Zielpfad bei SFTP
    private_key: Optional[str] = None
    passphrase: Optional[str] = None
    email_from: Optional[str] = None
    email_to: List[str] = field(default_factory=list)
    email_cc: List[str] = field(default_factory=list)
    email_bcc: List[str] = field(default_factory=list)
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    use_tls: bool = True
    use_ssl: bool = False
    subject: str = "Kiosk Logs"
    body: str = "Attached kiosk log export."
    schedule_minutes: Optional[int] = None   # optionales Intervall pro Ziel


@dataclass
class RemoteLogExportSettings:
    enabled: bool = False
    destinations: List[RemoteLogDestination] = field(default_factory=list)
    include_history: int = 3
    compress: bool = True
    staging_dir: Optional[str] = None
    retention_days: Optional[int] = None
    retention_count: Optional[int] = 10
    source_glob: str = "*.log"
    schedule_minutes: Optional[int] = None
    notify_failures: bool = True


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
    remote_export: RemoteLogExportSettings = field(default_factory=RemoteLogExportSettings)


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
    "RemoteLogExportSettings",
    "RemoteLogDestination",
    "UIConfig",
    "KioskConfig",
    "LoggingConfig",
    "load_config",
    "save_config",
    "_parse_sources",
    "_parse_ui",
    "_parse_kiosk",
    "_parse_logging",
    "DEFAULT_SHORTCUTS",
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


def _as_list(value: Any) -> List[str]:
    """Normalisiert Listen- oder CSV-Eingaben zu einer Stringliste."""
    items: List[str] = []
    if value is None:
        return items
    if isinstance(value, (list, tuple, set)):
        raw_iter = value
    else:
        raw_iter = [value]
    for entry in raw_iter:
        if entry is None:
            continue
        if isinstance(entry, str):
            parts = entry.split(",")
        else:
            parts = [str(entry)]
        for part in parts:
            s = part.strip()
            if s:
                items.append(s)
    return items


def _opt_str(value: Any) -> Optional[str]:
    s = _safe_str(value)
    return s or None


def _as_opt_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None

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
    sc = ui.get("shortcuts")
    shortcuts: Dict[str, str] = {}
    if isinstance(sc, dict):
        for k, v in sc.items():
            try:
                shortcuts[str(k)] = _safe_str(v)
            except Exception:
                continue
    merged = DEFAULT_SHORTCUTS.copy()
    merged.update({k: v for k, v in shortcuts.items() if v})

    return UISettings(
        start_mode=_safe_str(ui.get("start_mode") or "quad"),
        split_enabled=_as_bool(ui, "split_enabled", True),
        sidebar_width=_as_int(ui, "sidebar_width", 96),
        nav_orientation=_safe_str(ui.get("nav_orientation") or "left"),
        show_setup_on_start=_as_bool(ui, "show_setup_on_start", False),
        enable_hamburger=_as_bool(ui, "enable_hamburger", True),
        placeholder_enabled=_as_bool(ui, "placeholder_enabled", True),
        placeholder_gif_path=_safe_str(ui.get("placeholder_gif_path") or ""),
        theme=_safe_str(ui.get("theme") or "light"),
        language=_safe_str(ui.get("language") or ""),
        logo_path=_safe_str(ui.get("logo_path") or ""),
        shortcuts=merged,
    )


def _parse_kiosk(data: Dict[str, Any]) -> KioskSettings:
    kz = data.get("kiosk") or {}
    return KioskSettings(
        monitor_index=_as_int(kz, "monitor_index", 0),
        disable_system_keys=_as_bool(kz, "disable_system_keys", True),
        kiosk_fullscreen=_as_bool(kz, "kiosk_fullscreen", True),
    )


def _parse_remote_destinations(raw: Dict[str, Any]) -> List[RemoteLogDestination]:
    items = raw.get("destinations") if isinstance(raw, dict) else None
    destinations: List[RemoteLogDestination] = []
    if not isinstance(items, list):
        return destinations

    for entry in items:
        if not isinstance(entry, dict):
            continue
        typ = (_safe_str(entry.get("type")) or "http").lower()
        if typ not in {"http", "sftp", "email"}:
            continue

        name = _safe_str(entry.get("name") or "") or typ.upper()
        headers_data = entry.get("headers")
        headers: Dict[str, str] = {}
        if isinstance(headers_data, dict):
            for k, v in headers_data.items():
                try:
                    headers[str(k)] = _safe_str(v)
                except Exception:
                    continue

        dest = RemoteLogDestination(
            type=typ,
            name=name,
            enabled=_as_bool(entry, "enabled", True),
            url=_opt_str(entry.get("url") or entry.get("endpoint")),
            method=_safe_str(entry.get("method") or "POST").upper() if typ == "http" else _safe_str(entry.get("method") or "POST"),
            headers=headers,
            verify_tls=_as_bool(entry, "verify_tls", True),
            timeout=_as_int(entry, "timeout", 30),
            username=_opt_str(entry.get("username") or entry.get("user")),
            password=_opt_str(entry.get("password")),
            token=_opt_str(entry.get("token") or entry.get("bearer_token")),
            host=_opt_str(entry.get("host") or entry.get("server")),
            port=_as_opt_int(entry.get("port")),
            remote_path=_opt_str(entry.get("remote_path") or entry.get("path")),
            private_key=_opt_str(entry.get("private_key") or entry.get("key_file")),
            passphrase=_opt_str(entry.get("passphrase") or entry.get("key_passphrase")),
            email_from=_opt_str(entry.get("email_from") or entry.get("from")),
            email_to=_as_list(entry.get("email_to") or entry.get("recipients")),
            email_cc=_as_list(entry.get("email_cc")),
            email_bcc=_as_list(entry.get("email_bcc")),
            smtp_host=_opt_str(entry.get("smtp_host") or entry.get("host")),
            smtp_port=_as_opt_int(entry.get("smtp_port") or entry.get("port")),
            use_tls=_as_bool(entry, "use_tls", True),
            use_ssl=_as_bool(entry, "use_ssl", False),
            subject=_safe_str(entry.get("subject") or "Kiosk Logs"),
            body=_safe_str(entry.get("body") or entry.get("message") or "Attached kiosk log export."),
            schedule_minutes=_as_opt_int(entry.get("schedule_minutes")),
        )
        destinations.append(dest)

    return destinations


def _parse_remote_export(lg: Dict[str, Any]) -> RemoteLogExportSettings:
    raw = lg.get("remote_export") or {}
    if not isinstance(raw, dict):
        raw = {}
    retention_count_val = _as_opt_int(raw.get("retention_count"))
    if retention_count_val is not None and retention_count_val < 0:
        retention_count_val = None
    retention_days_val = _as_opt_int(raw.get("retention_days"))
    if retention_days_val is not None and retention_days_val < 0:
        retention_days_val = None
    return RemoteLogExportSettings(
        enabled=_as_bool(raw, "enabled", False),
        destinations=_parse_remote_destinations(raw),
        include_history=_as_int(raw, "include_history", 3),
        compress=_as_bool(raw, "compress", True),
        staging_dir=_opt_str(raw.get("staging_dir")),
        retention_days=retention_days_val,
        retention_count=10 if retention_count_val is None else retention_count_val,
        source_glob=_safe_str(raw.get("source_glob") or "*.log"),
        schedule_minutes=_as_opt_int(raw.get("schedule_minutes")),
        notify_failures=_as_bool(raw, "notify_failures", True),
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
        remote_export=_parse_remote_export(lg),
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
