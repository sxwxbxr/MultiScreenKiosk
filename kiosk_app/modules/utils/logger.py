# modules/utils/logger.py
from __future__ import annotations
import json
import logging
import os
import queue
import re
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from typing import Any, Deque, Dict, Optional, Tuple
from collections import deque
from pathlib import Path

from modules.utils.config_loader import RemoteLogExportSettings
from modules.utils.remote_export import RemoteLogExporter, RemoteExportResult, RemoteExportError

# Qt Bridge optional
try:
    from PyQt5.QtCore import QObject, pyqtSignal as Signal, QCoreApplication  # type: ignore
    _HAVE_QT = True
except Exception:
    _HAVE_QT = False
    QObject = object  # type: ignore

# ========= Konfiguration =========

@dataclass
class LoggingConfig:
    level: str = "INFO"                         # DEBUG, INFO, WARNING, ERROR
    fmt: str = "plain"                          # plain oder json
    dir: Optional[str] = None                   # Zielordner fuer Logfiles
    filename: str = "Logfile.log"               # Stammname; wird in YYYYMMDD_N_<stem>.log transformiert
    rotate_max_bytes: int = 5 * 1024 * 1024     # 5 MB (0 = Rotation aus)
    rotate_backups: int = 5                     # Anzahl Backups
    console: bool = True                        # Ausgabe auf STDERR
    qt_messages: bool = True                    # Qt Meldungen in Logging umleiten
    mask_keys: Tuple[str, ...] = ("password", "token", "authorization", "auth", "secret")
    memory_buffer: int = 2000                   # Zeilen fuer Live Viewer
    enable_qt_bridge: bool = True               # Live Push ins UI
    remote_export: Optional[RemoteLogExportSettings] = None

# ========= Globale Objekte =========

_log_queue: "queue.Queue[logging.LogRecord]" = queue.Queue()
_listener: Optional[QueueListener] = None
_bridge: Optional["QtLogBridge"] = None
_memory_ring: Deque[str] = deque(maxlen=2000)
_root_config: Optional[LoggingConfig] = None
_session_id: str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
_current_log_path: Optional[str] = None   # Pfad der aktuell verwendeten Logdatei
_remote_exporter: Optional[RemoteLogExporter] = None

# ========= Formatter =========

class PlainFormatter(logging.Formatter):
    default_msec_format = '%s.%03d'

    def format(self, record: logging.LogRecord) -> str:
        sid = getattr(record, "session", _session_id)
        src = getattr(record, "source", None)
        view = getattr(record, "view", None)
        base = super().format(record)
        extra = []
        if src:
            extra.append(f"source={src}")
        if view is not None:
            extra.append(f"view={view}")
        if sid:
            extra.append(f"session={sid}")
        if extra:
            base = f"{base} | " + " ".join(extra)
        return base

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
            "pid": record.process,
            "tid": record.thread,
            "thread": record.threadName,
            "session": getattr(record, "session", _session_id),
            "source": getattr(record, "source", None),
            "view": getattr(record, "view", None),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

# ========= Filter =========

class SecretsFilter(logging.Filter):
    """Maskiert bekannte Schluessel in Messages."""
    def __init__(self, keys: Tuple[str, ...]):
        super().__init__()
        self.patterns = [re.compile(rf"(?i)\b({re.escape(k)})\b\s*[:=]\s*([^\s,;]+)") for k in keys]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pat in self.patterns:
            msg = pat.sub(r"\1=<redacted>", msg)
        if isinstance(record.msg, str):
            record.msg = msg
        if isinstance(getattr(record, "extra", None), dict):
            for k in list(record.extra.keys()):
                if any(k.lower() == key.lower() for key in [p.pattern.split("\\b")[1] for p in self.patterns]):
                    record.extra[k] = "<redacted>"
        return True

# ========= Memory und Qt Bridge =========

class MemoryRingHandler(logging.Handler):
    def __init__(self, capacity: int):
        super().__init__()
        self.capacity = capacity

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:
            return
        _memory_ring.append(line)
        if _bridge is not None:
            try:
                _bridge.emit_line(line)
            except RuntimeError:
                # Qt Objekt schon zerstoert, ignorieren
                pass

def read_recent_logs(limit: int = 500) -> str:
    if limit <= 0:
        return ""
    lines = list(_memory_ring)[-limit:]
    return "\n".join(lines)

def get_log_bridge():
    return _bridge

if _HAVE_QT:
    class QtLogBridge(QObject):
        lineEmitted = Signal(str)

        def emit_line(self, text: str):
            if QCoreApplication.instance() is not None:
                self.lineEmitted.emit(text)
else:
    class QtLogBridge:  # type: ignore
        def emit_line(self, text: str):
            pass

# ========= Utilities =========

def _default_log_dir() -> str:
    base = os.getenv("LOCALAPPDATA", "")
    if base:
        d = os.path.join(base, "MultiScreenKiosk", "logs")
    else:
        d = os.path.join(os.getcwd(), "logs")
    os.makedirs(d, exist_ok=True)
    return d

def _split_name(filename: str) -> tuple[str, str]:
    """Teilt 'foo.log' -> ('foo', '.log'), 'foo' -> ('foo', '')"""
    p = Path(filename)
    stem = p.stem if p.suffix else filename.rsplit(".", 1)[0] if "." in filename else filename
    ext = p.suffix if p.suffix else (("." + filename.rsplit(".", 1)[1]) if "." in filename else ".log")
    return stem, ext

def _pick_next_logfile_path(log_dir: str, base_filename: str) -> str:
    """
    Waehlt fuer den aktuellen Tag eine neue Datei:
      YYYYMMDD_<n>_<stem>.log
    wobei <n> = max vorhandener Index + 1.
    """
    date_str = datetime.now().strftime("%Y%m%d")  # lokales Datum
    stem, ext = _split_name(base_filename)
    # Pattern: ^YYYYMMDD_(\d+)_stem\.ext$
    safe_stem = re.escape(stem)
    safe_ext = re.escape(ext)
    rx = re.compile(rf"^{date_str}_(\d+)_({safe_stem}){safe_ext}$", re.IGNORECASE)

    max_n = 0
    try:
        for name in os.listdir(log_dir):
            m = rx.match(name)
            if m:
                try:
                    n = int(m.group(1))
                    if n > max_n:
                        max_n = n
                except Exception:
                    continue
    except FileNotFoundError:
        os.makedirs(log_dir, exist_ok=True)

    next_n = max_n + 1
    filename = f"{date_str}_{next_n}_{stem}{ext}"
    return os.path.join(log_dir, filename)

def _parse_level(s: str) -> int:
    return getattr(logging, str(s).upper(), logging.INFO)

# ========= Initialisierung =========

def init_logging(cfg: Optional[LoggingConfig]) -> None:
    """Initialisiert asynchrones Logging und erstellt pro Start eine neue Datei."""
    global _listener, _bridge, _root_config, _memory_ring, _current_log_path, _remote_exporter

    if _remote_exporter is not None:
        try:
            _remote_exporter.shutdown()
        except Exception:
            pass
        _remote_exporter = None

    _root_config = cfg or LoggingConfig()
    log_dir = _root_config.dir or _default_log_dir()
    os.makedirs(log_dir, exist_ok=True)

    # Dateiname fuer diesen Start bestimmen
    selected_path = _pick_next_logfile_path(log_dir, _root_config.filename)
    _current_log_path = selected_path

    # Root Logger neu aufsetzen
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(_parse_level(_root_config.level))

    qh = QueueHandler(_log_queue)
    qh.setLevel(root.level)
    root.addHandler(qh)

    # Formatter
    if _root_config.fmt.lower() == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = PlainFormatter(fmt="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Zielhandler
    handlers: list[logging.Handler] = []

    if _root_config.rotate_max_bytes and _root_config.rotate_max_bytes > 0:
        file_handler = RotatingFileHandler(
            selected_path,
            maxBytes=_root_config.rotate_max_bytes,
            backupCount=_root_config.rotate_backups,
            encoding="utf-8"
        )
    else:
        # Rotation aus: normale Datei
        file_handler = logging.FileHandler(selected_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SecretsFilter(_root_config.mask_keys))
    handlers.append(file_handler)

    if _root_config.console:
        sh = logging.StreamHandler(stream=sys.stderr)
        sh.setFormatter(formatter)
        sh.addFilter(SecretsFilter(_root_config.mask_keys))
        handlers.append(sh)

    _memory_ring = deque(maxlen=_root_config.memory_buffer)
    mem = MemoryRingHandler(capacity=_root_config.memory_buffer)
    mem.setFormatter(formatter)
    handlers.append(mem)

    # Listener starten
    if _listener is not None:
        try:
            _listener.stop()
        except Exception:
            pass
    _listener = QueueListener(_log_queue, *handlers, respect_handler_level=False)
    _listener.start()

    # Qt Bridge
    if _root_config.enable_qt_bridge and _HAVE_QT:
        _bridge = QtLogBridge()
    else:
        _bridge = None

    # Qt Meldungen abfangen
    if _root_config.qt_messages:
        _install_qt_message_handler()

    # Banner
    get_logger(__name__).info(
        "logging initialised",
        extra={"session": _session_id, "source": "logging", "view": None}
    )
    get_logger(__name__).info(
        f"log file: {selected_path}",
        extra={"source": "logging"}
    )

    # Remote Export optional aktivieren
    remote_cfg = getattr(_root_config, "remote_export", None)
    if remote_cfg and getattr(remote_cfg, "enabled", False):
        try:
            _remote_exporter = RemoteLogExporter(
                remote_cfg,
                log_path=selected_path,
                logger=logging.getLogger(__name__),
            )
            if getattr(remote_cfg, "schedule_minutes", None):
                _remote_exporter.start_periodic_export()
            get_logger(__name__).info(
                "remote log export ready",
                extra={"source": "logging"}
            )
        except Exception as ex:
            _remote_exporter = None
            get_logger(__name__).error(
                f"failed to initialise remote export: {ex}",
                extra={"source": "logging"}
            )

# ========= Helpers =========

class _Adapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs = kwargs or {}
        extra = kwargs.get("extra", {})
        if not isinstance(extra, dict):
            extra = {}
        extra.setdefault("session", _session_id)
        kwargs["extra"] = extra
        return msg, kwargs

def get_logger(name: str, **extra) -> logging.LoggerAdapter:
    base = logging.getLogger(name)
    adapter = _Adapter(base, extra or {})
    return adapter

def set_global_level(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(_parse_level(level))
    get_logger(__name__).info(f"runtime log level set to {level}", extra={"source": "logging"})

def get_log_path() -> str:
    """Gibt den Pfad der aktuell verwendeten Logdatei zurueck."""
    if _current_log_path:
        return _current_log_path
    # Fallback vor Init
    d = _default_log_dir()
    stem, ext = _split_name(LoggingConfig().filename)
    today = datetime.now().strftime("%Y%m%d")
    return os.path.join(d, f"{today}_1_{stem}{ext}")


def get_remote_exporter() -> Optional[RemoteLogExporter]:
    return _remote_exporter


def export_logs_now(reason: str = "manual") -> RemoteExportResult:
    if _remote_exporter is None:
        raise RemoteExportError("remote log export is not configured")
    return _remote_exporter.export_now(reason=reason)


def start_remote_export_schedule(interval_minutes: Optional[int] = None) -> bool:
    if _remote_exporter is None:
        raise RemoteExportError("remote log export is not configured")
    return _remote_exporter.start_periodic_export(interval_minutes)


def stop_remote_export_schedule() -> None:
    if _remote_exporter is not None:
        _remote_exporter.stop_periodic_export()

# ========= Qt Message Handler =========

def _install_qt_message_handler():
    if not _HAVE_QT:
        return
    try:
        from PyQt5.QtCore import qInstallMessageHandler  # type: ignore
    except Exception:
        return

    log = get_logger("qt")

    def handler(msg_type, context, message):
        # 0=Debug, 1=Info, 2=Warning, 3=Critical, 4=Fatal
        lvl_map = {0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING, 3: logging.ERROR, 4: logging.CRITICAL}
        lvl = lvl_map.get(int(msg_type), logging.INFO)
        try:
            log.log(lvl, str(message), extra={"source": "qt"})
        except Exception:
            pass

    try:
        qInstallMessageHandler(handler)
    except Exception:
        pass

# ========= Dekorator =========

def log_exceptions(logger: logging.LoggerAdapter, level: int = logging.ERROR):
    """Dekorator der Exceptions loggt und erneut wirft."""
    def deco(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except SystemExit:
                raise
            except KeyboardInterrupt:
                logger.warning("interrupted", extra={"source": "exception"})
                raise
            except Exception:
                logger.log(level, "uncaught exception in %s", func.__name__, exc_info=True, extra={"source": "exception"})
                raise
        return wrapper
    return deco
