import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_logger = None

def init_logging(path: Path):
    global _logger
    _logger = logging.getLogger("kiosk")
    _logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    fh = RotatingFileHandler(path, maxBytes=2*1024*1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    _logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    _logger.addHandler(ch)

def get_logger(name: str):
    return logging.getLogger(f"kiosk.{name}")
