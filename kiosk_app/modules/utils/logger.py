from __future__ import annotations
import json
import logging
import os
import queue
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from typing import Any, Deque, Dict, Optional, Tuple
from collections import deque

# Qt Bridge optional
try:
    from PySide6.QtCore import QObject, Signal, QCoreApplication
    _HAVE_QT = True
except Exception:
    _HAVE_QT = False
    QObject = object  # type: ignore

try:
    from shiboken6 import isValid as _is_valid_qobj  # type: ignore
except Exception:
    def _is_valid_qobj(_obj):  # type: ignore
        return True

@dataclass
class LoggingConfig:
    level: str = "INFO"
    fmt: str = "plain"                          # plain oder json
    dir: Optional[str] = None
    filename: str = "kiosk.log"
    rotate_max_bytes: int = 5 * 1024 * 1024
    rotate_backups: int = 5
    console: bool = True
    qt_messages: bool = True
    mask_keys: Tuple[str, ...] = ("password", "token", "authorization", "auth", "secret")
    memory_buffer: int = 2000
    enable_qt_bridge: bool = True

_log_queue: "queue.Queue[logging.LogRecord]" = queue.Queue()
_listener: Optional[QueueListener] = None
_bridge: Optional["QtLogBridge"] = None
_memory_ring: Deque[str] = deque(maxlen=2000)
_root_config: Optional[LoggingConfig] = None
_session_id: str = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")

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

class SecretsFilter(logging.Filter):
    def __init__(self, keys: Tuple[str, ...]):
        super().__init__()
        self.patterns = [re.compile(rf"(?i)\b({re.escape(k)})\b\s*[:=]\s*([^\s,;]+)") for k in keys]
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pat in self.patterns:
            msg = pat.sub(r"\1=<redacted>", msg)
        if isinstance(record.msg, str):
            record.msg = msg
        return True

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
        try:
            if _bridge is not None:
                _bridge.emit_line(line)
        except Exception:
            pass

def read_recent_logs(limit: int = 500) -> str:
    if limit <= 0:
        return ""
    lines = list(_memory_ring)[-limit:]
    return "\n".join(lines)

def get_log_path() -> str:
    if _root_config is None:
        d = _default_log_dir()
        return os.path.join(d, "kiosk.log")
    d = _root_config.dir or _default_log_dir()
    return os.path.join(d, _root_config.filename)

def clear_log() -> None:
    path = get_log_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("")
    except Exception:
        pass
    _memory_ring.clear()

def _default_log_dir() -> str:
    base = os.getenv("LOCALAPPDATA", "")
    if base:
        d = os.path.join(base, "MultiScreenKiosk", "logs")
    else:
        d = os.path.join(os.getcwd(), "logs")
    os.makedirs(d, exist_ok=True)
    return d

# NEU: fuer den Log Viewer
def get_log_bridge():
    return _bridge

if _HAVE_QT:
    class QtLogBridge(QObject):
        lineEmitted = Signal(str)
        def emit_line(self, text: str):
            try:
                if QCoreApplication.instance() is None:
                    return
                if not _is_valid_qobj(self):
                    return
                self.lineEmitted.emit(text)
            except Exception:
                pass
else:
    class QtLogBridge:  # type: ignore
        def emit_line(self, text: str):  # no-op
            pass

def _parse_level(s: str) -> int:
    return getattr(logging, str(s).upper(), logging.INFO)

def init_logging(cfg: Optional[LoggingConfig]) -> None:
    global _listener, _bridge, _root_config, _memory_ring

    _root_config = cfg or LoggingConfig()
    log_dir = _root_config.dir or _default_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    logfile = os.path.join(log_dir, _root_config.filename)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(_parse_level(_root_config.level))

    qh = QueueHandler(_log_queue)
    qh.setLevel(root.level)
    root.addHandler(qh)

    if _root_config.fmt.lower() == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = PlainFormatter(fmt="%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        logfile, maxBytes=_root_config.rotate_max_bytes,
        backupCount=_root_config.rotate_backups, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SecretsFilter(_root_config.mask_keys))

    handlers = [file_handler]

    if _root_config.console:
        sh = logging.StreamHandler(stream=sys.stderr)
        sh.setFormatter(formatter)
        sh.addFilter(SecretsFilter(_root_config.mask_keys))
        handlers.append(sh)

    _memory_ring = deque(maxlen=_root_config.memory_buffer)
    mem = MemoryRingHandler(capacity=_root_config.memory_buffer)
    mem.setFormatter(formatter)
    handlers.append(mem)

    if _listener is not None:
        try:
            _listener.stop()
        except Exception:
            pass
    _listener = QueueListener(_log_queue, *handlers, respect_handler_level=False)
    _listener.daemon = True
    _listener.start()

    _bridge = QtLogBridge() if (_root_config.enable_qt_bridge and _HAVE_QT) else None

    if _root_config.qt_messages:
        _install_qt_message_handler()

    get_logger(__name__).info("logging initialised", extra={"session": _session_id, "source": "logging", "view": None})

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

def _install_qt_message_handler():
    if not _HAVE_QT:
        return
    try:
        from PySide6.QtCore import qInstallMessageHandler
    except Exception:
        return

    log = get_logger("qt")

    def handler(msg_type, context, message):
        # 0..4: Debug, Info, Warning, Critical, Fatal
        mapping = {0: logging.DEBUG, 1: logging.INFO, 2: logging.WARNING, 3: logging.ERROR, 4: logging.CRITICAL}
        lvl = mapping.get(int(msg_type), logging.INFO)
        log.log(lvl, str(message), extra={"source": "qt"})

    try:
        qInstallMessageHandler(handler)
    except Exception:
        pass
