# modules/services/local_app_service.py
from __future__ import annotations
import ctypes
import subprocess
import re
import os
import shlex
from dataclasses import dataclass
from typing import Optional, List, Tuple

from ctypes import wintypes
from PySide6.QtCore import QTimer, Qt, QSize
from PySide6.QtWidgets import QWidget

from modules.utils.logger import get_logger

# --------- Win32 Setup ----------
user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi    = ctypes.windll.psapi

HWINEVENTHOOK = wintypes.HANDLE
HMODULE = getattr(wintypes, "HMODULE", wintypes.HANDLE)

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
WinEventProc    = ctypes.WINFUNCTYPE(None, HWINEVENTHOOK, wintypes.DWORD,
                                     wintypes.HWND, wintypes.LONG, wintypes.LONG,
                                     wintypes.DWORD, wintypes.DWORD)

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
GetWindowThreadProcessId.restype  = wintypes.DWORD

GetWindowTextLengthW = user32.GetWindowTextLengthW
GetWindowTextW       = user32.GetWindowTextW
GetClassNameW        = user32.GetClassNameW
IsWindow             = user32.IsWindow
IsWindowVisible      = user32.IsWindowVisible
EnumWindows          = user32.EnumWindows
GetWindowRect        = user32.GetWindowRect

GWL_STYLE   = -16
GWL_EXSTYLE = -20
GetWindowLongPtrW = user32.GetWindowLongPtrW
SetWindowLongPtrW = user32.SetWindowLongPtrW
SetParent         = user32.SetParent
SetWindowPos      = user32.SetWindowPos
MoveWindow        = user32.MoveWindow
ShowWindow        = user32.ShowWindow
SetForegroundWindow = user32.SetForegroundWindow
SetFocus            = user32.SetFocus
AttachThreadInput   = user32.AttachThreadInput
GetForegroundWindow = user32.GetForegroundWindow
SetWinEventHook     = user32.SetWinEventHook
UnhookWinEvent      = user32.UnhookWinEvent

# kernel32
OpenProcess  = kernel32.OpenProcess
CloseHandle  = kernel32.CloseHandle
GetCurrentThreadId = kernel32.GetCurrentThreadId
GetCurrentThreadId.argtypes = []
GetCurrentThreadId.restype  = wintypes.DWORD
QueryFullProcessImageNameW  = getattr(kernel32, "QueryFullProcessImageNameW", None)

# psapi fallback
GetProcessImageFileNameW = getattr(psapi, "GetProcessImageFileNameW", None)

# Hooks
SetWinEventHook.argtypes = [
    wintypes.DWORD, wintypes.DWORD, HMODULE, WinEventProc,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD
]
SetWinEventHook.restype = HWINEVENTHOOK
UnhookWinEvent.argtypes = [HWINEVENTHOOK]
UnhookWinEvent.restype  = wintypes.BOOL

AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
AttachThreadInput.restype  = wintypes.BOOL

# WaitForInputIdle
_WaitForInputIdle = getattr(user32, "WaitForInputIdle", None)
if _WaitForInputIdle is not None:
    _WaitForInputIdle.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _WaitForInputIdle.restype  = wintypes.DWORD

# Styles
WS_CHILD        = 0x40000000
WS_POPUP        = 0x80000000
WS_CAPTION      = 0x00C00000
WS_THICKFRAME   = 0x00040000
WS_SYSMENU      = 0x00080000
WS_MINIMIZEBOX  = 0x00020000
WS_MAXIMIZEBOX  = 0x00010000
WS_VISIBLE      = 0x10000000

WS_EX_TOOLWINDOW     = 0x00000080
WS_EX_APPWINDOW      = 0x00040000
WS_EX_NOPARENTNOTIFY = 0x00000004

SWP_NOSIZE         = 0x0001
SWP_NOMOVE         = 0x0002
SWP_NOZORDER       = 0x0004
SWP_FRAMECHANGED   = 0x0020
SWP_SHOWWINDOW     = 0x0040
SWP_NOACTIVATE     = 0x0010

SW_HIDE            = 0
SW_SHOW            = 5
SW_SHOWNOACTIVATE  = 4

# WinEvent IDs
EVENT_OBJECT_CREATE = 0x8000
EVENT_OBJECT_SHOW   = 0x8002
WINEVENT_OUTOFCONTEXT   = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

# Process rights
PROCESS_QUERY_INFORMATION      = 0x0400
PROCESS_VM_READ                = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# ---------- Helpers ----------
def _safe_wait_input_idle(proc: subprocess.Popen, timeout_ms: int = 3000) -> None:
    try:
        if _WaitForInputIdle is None:
            return
        h = getattr(proc, "_handle", None)
        if h:
            _WaitForInputIdle(int(h), timeout_ms)
    except Exception:
        return

def _get_text(hwnd: int) -> str:
    n = GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    GetWindowTextW(hwnd, buf, n + 1)
    return buf.value or ""

def _get_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    GetClassNameW(hwnd, buf, 256)
    return buf.value or ""

def _rect(hwnd: int) -> Tuple[int, int, int, int]:
    r = wintypes.RECT()
    GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom

def _area(hwnd: int) -> int:
    l, t, r, b = _rect(hwnd)
    return max(0, r - l) * max(0, b - t)

def _is_real_top(hwnd: int) -> bool:
    if not IsWindow(hwnd):
        return False
    ex = GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    style = GetWindowLongPtrW(hwnd, GWL_STYLE)
    if style & WS_CHILD:
        return False
    if ex & WS_EX_TOOLWINDOW:
        return False
    return True

def _enum_toplevel_windows() -> List[int]:
    res: List[int] = []
    def cb(hwnd, lparam):
        if _is_real_top(hwnd):
            res.append(hwnd)
        return True
    EnumWindows(EnumWindowsProc(cb), 0)
    return res

def _enum_windows_for_pid(pid: int) -> List[int]:
    res: List[int] = []
    def cb(hwnd, lparam):
        p = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if int(p.value) == pid and _is_real_top(hwnd):
            res.append(hwnd)
        return True
    EnumWindows(EnumWindowsProc(cb), 0)
    return res

def _pick_best_window(cands: List[int],
                      title_re: Optional[re.Pattern],
                      class_re: Optional[re.Pattern]) -> Optional[int]:
    best, best_score = None, -1
    for hwnd in cands:
        if not IsWindowVisible(hwnd):
            continue
        title = _get_text(hwnd)
        cls = _get_class(hwnd)
        score = 0
        if title_re and title_re.search(title):
            score += 3
        if class_re and class_re.search(cls):
            score += 3
        if title:
            score += 1
        score += min(_area(hwnd) // (200 * 200), 3)
        if score > best_score:
            best, best_score = hwnd, score
    return best

def _apply_child_styles(hwnd: int):
    style = GetWindowLongPtrW(hwnd, GWL_STYLE)
    ex    = GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    style &= ~WS_POPUP
    style &= ~WS_CAPTION
    style &= ~WS_THICKFRAME
    style &= ~WS_SYSMENU
    style &= ~WS_MINIMIZEBOX
    style &= ~WS_MAXIMIZEBOX
    style |= WS_CHILD | WS_VISIBLE
    SetWindowLongPtrW(hwnd, GWL_STYLE, style)
    ex &= ~WS_EX_APPWINDOW
    ex |= WS_EX_NOPARENTNOTIFY
    SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)
    SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                 SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE)

def _expected_exe_from_cmd(cmd: str, class_re: Optional[re.Pattern]) -> Optional[str]:
    if class_re and class_re.search("XLMAIN"):
        return "EXCEL.EXE"
    if not cmd:
        return None
    try:
        parts = shlex.split(cmd, posix=False)
        exe = parts[0]
    except Exception:
        exe = cmd
    return os.path.basename(exe).upper()

def _get_process_image_name(pid: int) -> Optional[str]:
    if pid <= 0:
        return None
    h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        h = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        return None
    try:
        if QueryFullProcessImageNameW:
            size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(1024)
            ok = QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
            if ok:
                return buf.value
        if GetProcessImageFileNameW:
            buf = ctypes.create_unicode_buffer(1024)
            n = GetProcessImageFileNameW(h, buf, 1024)
            if n:
                return buf.value
        return None
    finally:
        CloseHandle(h)

def _exe_basename_upper_for_pid(pid: int) -> Optional[str]:
    p = _get_process_image_name(pid)
    if not p:
        return None
    return os.path.basename(p).upper()

# ---------- Config ----------
@dataclass
class LocalAppConfig:
    launch_cmd: str
    embed_mode: str = "native_window"
    window_title_pattern: str = ""
    window_class_pattern: str = ""      # Excel: XLMAIN, Notepad: Notepad oder ApplicationFrameWindow
    single_instance_fallback: bool = True
    web_url: Optional[str] = None
    force_pattern_only: bool = False    # NEU: bei True zaehlt nur Klassen oder Titelmatch

# ---------- Widget ----------
class LocalAppWidget(QWidget):
    """
    Bettet eine lokale Anwendung als Child Fenster ein.
    - ODER Logik fuer Klassen und Titeltreffer
    - Optional: force_pattern_only, dann ignorieren wir PID und EXE Filter
    """
    def __init__(self, cfg_obj, parent=None):
        super().__init__(parent)
        self.log = get_logger(__name__)
        self.cfg = LocalAppConfig(
            launch_cmd=getattr(cfg_obj, "launch_cmd", ""),
            embed_mode=getattr(cfg_obj, "embed_mode", "native_window"),
            window_title_pattern=getattr(cfg_obj, "window_title_pattern", "") or "",
            window_class_pattern=getattr(cfg_obj, "window_class_pattern", "") or "",
            single_instance_fallback=True,
            web_url=getattr(cfg_obj, "web_url", None),
            force_pattern_only=bool(getattr(cfg_obj, "force_pattern_only", False)),
        )
        self.proc: Optional[subprocess.Popen] = None
        self.child_hwnd: Optional[int] = None
        self.target_pid: Optional[int] = None

        self._title_re: Optional[re.Pattern] = None
        self._class_re: Optional[re.Pattern] = None
        if self.cfg.window_title_pattern:
            try:
                self._title_re = re.compile(self.cfg.window_title_pattern, re.IGNORECASE)
            except re.error:
                self.log.warning("ungueltige window_title_pattern Regex. Ignoriere.")
        if self.cfg.window_class_pattern:
            try:
                self._class_re = re.compile(self.cfg.window_class_pattern, re.IGNORECASE)
            except re.error:
                self.log.warning("ungueltige window_class_pattern Regex. Ignoriere.")

        self._expected_exe_upper: Optional[str] = _expected_exe_from_cmd(self.cfg.launch_cmd, self._class_re)

        self._embed_timer = QTimer(self)
        self._embed_timer.setInterval(500)
        self._embed_timer.timeout.connect(self._try_embed)

        self._watchdog = QTimer(self)
        self._watchdog.setInterval(2000)
        self._watchdog.timeout.connect(self._tick_watchdog)

        self._hook = None
        self._hook_cb = WinEventProc(self._on_win_event)

        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setMinimumSize(QSize(50, 50))

    # ------ Lifecycle ------
    def start(self):
        if self.cfg.embed_mode != "native_window":
            self.log.warning("embed_mode '%s' nicht implementiert. Nutze native_window.", self.cfg.embed_mode)

        if not self.proc or self.proc.poll() is not None:
            cmd = self.cfg.launch_cmd
            if not cmd:
                self.log.error("kein launch_cmd konfiguriert")
            else:
                try:
                    self.proc = subprocess.Popen(cmd, shell=True)
                    self.log.info("Prozess gestartet: %s", cmd)
                    if not self._expected_exe_upper:
                        self._expected_exe_upper = _expected_exe_from_cmd(cmd, self._class_re)
                    self.target_pid = self.proc.pid
                    _safe_wait_input_idle(self.proc, 3000)
                except Exception as ex:
                    self.log.exception("Start fehlgeschlagen: %s", ex)
                    self.proc = None
                    self.target_pid = None

        self._install_hook()
        self._embed_timer.start()
        self._watchdog.start()

    def stop(self):
        self._remove_hook()
        self._embed_timer.stop()
        self._watchdog.stop()
        if self.child_hwnd and IsWindow(self.child_hwnd):
            try:
                SetParent(self.child_hwnd, 0)
                ShowWindow(self.child_hwnd, SW_HIDE)
            except Exception:
                pass
        self.child_hwnd = None
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.proc = None
        self.target_pid = None

    def heartbeat(self):
        pass

    # ------ Hook ------
    def _install_hook(self):
        if self._hook:
            return
        self._hook = SetWinEventHook(
            EVENT_OBJECT_CREATE, EVENT_OBJECT_SHOW,
            0, self._hook_cb, 0, 0,
            WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS
        )

    def _remove_hook(self):
        if self._hook:
            try:
                UnhookWinEvent(self._hook)
            except Exception:
                pass
            self._hook = None

    def _accept_window_by_pid_and_image(self, hwnd: int, class_or_title_matched: bool) -> bool:
        # Nur Muster? Dann reicht Klasse oder Titel
        if self.cfg.force_pattern_only and class_or_title_matched:
            return True

        pid = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pid_val = int(pid.value)
        if self.target_pid is not None and pid_val != self.target_pid:
            return False

        if self._expected_exe_upper:
            exe = _exe_basename_upper_for_pid(pid_val)
            if exe:
                return exe == self._expected_exe_upper
            # wenn EXE nicht lesbar und Muster passt, akzeptieren
            if class_or_title_matched:
                return True

        return True

    def _on_win_event(self, hook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
        if idObject != 0 or not _is_real_top(hwnd):
            return
        title = _get_text(hwnd)
        cls   = _get_class(hwnd)
        # ODER Logik
        title_ok = (self._title_re.search(title) if self._title_re else True)
        class_ok = (self._class_re.search(cls) if self._class_re else True)
        class_or_title_ok = title_ok or class_ok
        if not class_or_title_ok:
            return
        if not self._accept_window_by_pid_and_image(hwnd, class_or_title_ok):
            return
        try:
            self._reparent(hwnd)
            p = wintypes.DWORD()
            GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            self.target_pid = int(p.value)
        except Exception:
            pass

    # ------ Suche und Einbettung ------
    def _find_target_window(self) -> Optional[int]:
        # 1) PID Kandidaten
        pid = self.target_pid or (self.proc.pid if self.proc else 0)
        if pid:
            cand = _enum_windows_for_pid(pid)
            # ODER Filter
            filtered: List[int] = []
            for h in cand:
                t = _get_text(h)
                c = _get_class(h)
                title_ok = (self._title_re.search(t) if self._title_re else True)
                class_ok = (self._class_re.search(c) if self._class_re else True)
                if not (title_ok or class_ok):
                    continue
                if self._accept_window_by_pid_and_image(h, True):
                    filtered.append(h)
            hwnd = _pick_best_window(filtered, self._title_re, self._class_re)
            if hwnd:
                return hwnd

        # 2) Fallback global
        if self.cfg.single_instance_fallback:
            all_top = _enum_toplevel_windows()
            filtered = []
            for h in all_top:
                t = _get_text(h)
                c = _get_class(h)
                title_ok = (self._title_re.search(t) if self._title_re else True)
                class_ok = (self._class_re.search(c) if self._class_re else True)
                if not (title_ok or class_ok):
                    continue
                if self._accept_window_by_pid_and_image(h, True):
                    filtered.append(h)
            hwnd = _pick_best_window(filtered, self._title_re, self._class_re)
            if hwnd:
                p = wintypes.DWORD()
                GetWindowThreadProcessId(hwnd, ctypes.byref(p))
                self.target_pid = int(p.value)
                return hwnd
        return None

    def _reparent(self, hwnd: int):
        host_hwnd = int(self.winId())
        _apply_child_styles(hwnd)
        SetParent(hwnd, host_hwnd)
        self.child_hwnd = hwnd
        self._fit_child(hwnd)
        ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)

    def _try_embed(self):
        if self.child_hwnd and IsWindow(self.child_hwnd):
            return
        hwnd = self._find_target_window()
        if not hwnd:
            return
        try:
            self._reparent(hwnd)
        except Exception as ex:
            self.log.exception("Einbetten fehlgeschlagen: %s", ex)

    def _fit_child(self, hwnd: int):
        w = max(1, self.width())
        h = max(1, self.height())
        MoveWindow(hwnd, 0, 0, w, h, True)

    # ------ Fokus und Sichtbarkeit ------
    def _focus_child(self):
        if not self.child_hwnd or not IsWindow(self.child_hwnd):
            return
        host_tid = GetCurrentThreadId()
        pid = wintypes.DWORD()
        child_tid = GetWindowThreadProcessId(self.child_hwnd, ctypes.byref(pid))
        if child_tid:
            AttachThreadInput(host_tid, child_tid, True)
            try:
                SetForegroundWindow(self.child_hwnd)
                SetFocus(self.child_hwnd)
            finally:
                AttachThreadInput(host_tid, child_tid, False)

    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)
        self._focus_child()

    def showEvent(self, ev):
        super().showEvent(ev)
        if self.child_hwnd and IsWindow(self.child_hwnd):
            ShowWindow(self.child_hwnd, SW_SHOW)
            self._fit_child(self.child_hwnd)

    def hideEvent(self, ev):
        super().hideEvent(ev)
        if self.child_hwnd and IsWindow(self.child_hwnd):
            ShowWindow(self.child_hwnd, SW_HIDE)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self.child_hwnd and IsWindow(self.child_hwnd):
            self._fit_child(self.child_hwnd)

    def _tick_watchdog(self):
        if self.proc and self.proc.poll() is not None:
            self.child_hwnd = None
            self.target_pid = None
            if self.cfg.launch_cmd:
                self.log.warning("Prozess beendet. Starte neu.")
                self.start()
            return
        if not self.child_hwnd or not IsWindow(self.child_hwnd):
            self._embed_timer.start()
