# modules/utils/logger.py
from __future__ import annotations
import json
import logging
import os
import queue
import re
import sys
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from typing import Any, Deque, Dict, Optional, Tuple
from collections import deque

# Qt Bridge ist optional. Import im Try damit der Logger auch ohne Qt funktioniert.
try:
    from PySide6.QtCore import QObject, Signal, QCoreApplication  # type: ignore
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
    filename: str = "kiosk.log"                 # Name der Logdatei
    rotate_max_bytes: int = 5 * 1024 * 1024     # 5 MB
    rotate_backups: int = 5                     # Anzahl Backups
    console: bool = True                        # Ausgabe auf STDERR
    qt_messages: bool = True                    # Qt Meldungen in Logging umleiten
    mask_keys: Tuple[str, ...] = ("password", "token", "authorization", "auth", "secret")
    memory_buffer: int = 2000                   # Zeilen fuer Live Viewer
    enable_qt_bridge: bool = True               # Live Push ins UI

# ========= Globale Objekte =========

_log_queue: "queue.Queue[logging.LogRecord]" = queue.Queue()
_listener: Optional[QueueListener] = None
_bridge: Optional["QtLogBridge"] = None
_memory_ring: Deque[str] = deque(maxlen=2000)
_root_config: Optional[LoggingConfig] = None
_session_id: str = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")

# ========= Formatter =========

class PlainFormatter(logging.Formatter):
    default_msec_format = '%s.%03d'

    def format(self, record: logging.LogRecord) -> str:
        # zusätzliche Felder robust abfragen
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
        # setMessage geht nicht. Daher ueberschreiben wir record.msg wenn es ein string ist.
        if isinstance(record.msg, str):
            record.msg = msg
        # kwargs durchgehen
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
            _bridge.emit_line(line)

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
            # Signal nur senden wenn eine Qt App laeuft
            if QCoreApplication.instance() is not None:
                self.lineEmitted.emit(text)
else:
    class QtLogBridge:  # type: ignore
        def emit_line(self, text: str):  # no-op
            pass

# ========= Initialisierung =========

def _default_log_dir() -> str:
    # Bevorzugt LOCALAPPDATA
    base = os.getenv("LOCALAPPDATA", "")
    if base:
        d = os.path.join(base, "MultiScreenKiosk", "logs")
    else:
        d = os.path.join(os.getcwd(), "logs")
    os.makedirs(d, exist_ok=True)
    return d

def init_logging(cfg: Optional[LoggingConfig]) -> None:
    """Initialisiert asynchrones Logging mit Rotation und optional JSON."""
    global _listener, _bridge, _root_config, _memory_ring

    _root_config = cfg or LoggingConfig()
    # Zielordner
    log_dir = _root_config.dir or _default_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    logfile = os.path.join(log_dir, _root_config.filename)

    # Root Logger entkoppeln
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(_parse_level(_root_config.level))

    # Queue Handler am Root
    qh = QueueHandler(_log_queue)
    qh.setLevel(root.level)
    root.addHandler(qh)

    # Formatter fuer Zielhandler
    if _root_config.fmt.lower() == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = PlainFormatter(fmt="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Zielhandler bauen
    file_handler = RotatingFileHandler(
        logfile, maxBytes=_root_config.rotate_max_bytes,
        backupCount=_root_config.rotate_backups, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SecretsFilter(_root_config.mask_keys))

    handlers = [file_handler]

    # Konsole
    if _root_config.console:
        sh = logging.StreamHandler(stream=sys.stderr)
        sh.setFormatter(formatter)
        sh.addFilter(SecretsFilter(_root_config.mask_keys))
        handlers.append(sh)

    # Memory Ring fuer Live Viewer
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

    # Startbanner
    get_logger(__name__).info(
        "logging initialised",
        extra={"session": _session_id, "source": "logging", "view": None}
    )

def _parse_level(s: str) -> int:
    return getattr(logging, str(s).upper(), logging.INFO)

# ========= Helpers fuer Aufrufer =========

class _Adapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        # sichere Extras anreichern
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
    # QueueHandler haengt am Root, die Zielhandler bekommen Level ueber Listener nicht separat
    get_logger(__name__).info(f"runtime log level set to {level}", extra={"source": "logging"})

def get_log_path() -> str:
    if _root_config is None:
        # noch nicht initialisiert
        d = _default_log_dir()
        return os.path.join(d, "kiosk.log")
    d = _root_config.dir or _default_log_dir()
    return os.path.join(d, _root_config.filename)

# ========= Qt Message Handler =========

def _install_qt_message_handler():
    # Nur wenn Qt verfuegbar
    if not _HAVE_QT:
        return
    try:
        from PySide6.QtCore import qInstallMessageHandler, QtMsgType  # type: ignore
    except Exception:
        return

    log = get_logger("qt")

    def handler(msg_type, context, message):
        # Mappe Qt Level auf Python Level
        if msg_type == 0:      # QtDebugMsg
            lvl = logging.DEBUG
        elif msg_type == 1:    # QtInfoMsg
            lvl = logging.INFO
        elif msg_type == 2:    # QtWarningMsg
            lvl = logging.WARNING
        elif msg_type == 3:    # QtCriticalMsg
            lvl = logging.ERROR
        else:                  # QtFatalMsg
            lvl = logging.CRITICAL
        log.log(lvl, str(message), extra={"source": "qt"})

    try:
        qInstallMessageHandler(handler)
    except Exception:
        pass

# ========= Dekorator fuer Exceptions =========

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
