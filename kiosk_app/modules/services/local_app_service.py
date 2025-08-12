import subprocess
from dataclasses import dataclass
from typing import Optional, Literal

from PySide6.QtCore import QObject, Signal, QTimer, Qt, QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtWebEngineWidgets import QWebEngineView

from modules.utils.logger import get_logger
from modules.utils.win_embed import (
    find_window_for_pid,
    find_window_by_title_regex,
    set_parent_embed,
    set_child_styles,
    resize_child_to_parent,
)

@dataclass
class LocalAppConfig:
    launch_cmd: str
    embed_mode: Literal["native_window", "sdk", "web"] = "native_window"
    window_title_pattern: str = ""
    web_url: Optional[str] = None

def _normalize_cfg(cfg_obj) -> LocalAppConfig:
    if isinstance(cfg_obj, LocalAppConfig):
        return cfg_obj
    return LocalAppConfig(
        launch_cmd=getattr(cfg_obj, "launch_cmd", getattr(cfg_obj, "command", "")),
        embed_mode=getattr(cfg_obj, "embed_mode", "native_window"),
        window_title_pattern=getattr(cfg_obj, "window_title_pattern", ""),
        web_url=getattr(cfg_obj, "web_url", None),
    )

class LocalAppWidget(QWidget):
    def __init__(self, cfg_obj, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NativeWindow, True)
        self.winId()

        self.cfg = _normalize_cfg(cfg_obj)
        self.log = get_logger(__name__)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        if self.cfg.embed_mode == "web" and self.cfg.web_url:
            self.web = QWebEngineView(self)
            self.layout.addWidget(self.web)
        else:
            self.web = None
            self.placeholder = QLabel("Lokale Anwendung", self)
            self.placeholder.setStyleSheet("background:#111; color:#bbb; font-size:14px; padding:8px;")
            self.layout.addWidget(self.placeholder)

        self.service = LocalAppService(self, self.cfg)

    def start(self):
        self.service.start()
        if self.web and self.cfg.web_url:
            self.web.setUrl(QUrl(self.cfg.web_url))

    def stop(self):
        self.service.stop()

    def heartbeat(self):
        self.service.heartbeat()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        try:
            if self.service and self.service.embed_hwnd:
                resize_child_to_parent(self.service.embed_hwnd, int(self.winId()))
        except Exception:
            pass

class LocalAppService(QObject):
    started = Signal()
    failed = Signal(str)

    def __init__(self, host_widget: QWidget, cfg: LocalAppConfig):
        super().__init__(host_widget)
        self.host = host_widget
        self.cfg = cfg
        self.log = get_logger(f"{__name__}.Local")
        self.proc: Optional[subprocess.Popen] = None
        self.embed_hwnd: Optional[int] = None

        self.watchdog = QTimer(self)
        self.watchdog.setInterval(1000)
        self.watchdog.timeout.connect(self._tick)

    def start(self):
        if self.cfg.embed_mode in ("native_window", "sdk"):
            try:
                self.proc = subprocess.Popen(self.cfg.launch_cmd, shell=True)
                self.log.info("Lokaler Prozess gestartet: %s", self.cfg.launch_cmd)
            except Exception as e:
                self.failed.emit(str(e))
                return
        self.watchdog.start()

    def stop(self):
        try:
            self.watchdog.stop()
        except Exception:
            pass
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
        except Exception as e:
            self.log.warning("Stop Fehler: %s", e)
        self.proc = None
        self.embed_hwnd = None

    def heartbeat(self):
        pass

    def _try_embed(self):
        if self.cfg.embed_mode != "native_window":
            return

        hwnd = None
        if self.proc and self.proc.poll() is None:
            hwnd = find_window_for_pid(self.proc.pid, self.cfg.window_title_pattern or None)
        if not hwnd and self.cfg.window_title_pattern:
            hwnd = find_window_by_title_regex(self.cfg.window_title_pattern)

        if hwnd and hwnd != self.embed_hwnd:
            ok = set_parent_embed(hwnd, int(self.host.winId()))
            if ok:
                set_child_styles(hwnd)
                resize_child_to_parent(hwnd, int(self.host.winId()))
                self.embed_hwnd = hwnd
                self.started.emit()

    def _tick(self):
        if self.cfg.embed_mode == "web":
            return
        if self.proc and self.proc.poll() is not None:
            self.log.warning("Prozess beendet, starte neu")
            self.start()
            return
        self._try_embed()
        if self.embed_hwnd:
            try:
                resize_child_to_parent(self.embed_hwnd, int(self.host.winId()))
            except Exception:
                pass

    def rebind_host(self, new_host: QWidget):
        self.host = new_host
        self.host.setAttribute(Qt.WA_NativeWindow, True)
        self.host.winId()
        if self.embed_hwnd:
            ok = set_parent_embed(self.embed_hwnd, int(self.host.winId()))
            if ok:
                set_child_styles(self.embed_hwnd)
                resize_child_to_parent(self.embed_hwnd, int(self.host.winId()))
