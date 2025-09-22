# modules/services/local_app_service.py
from __future__ import annotations

import ctypes
from ctypes import wintypes
import subprocess
import sys
import time
import re
import shlex
import os
from dataclasses import dataclass
from threading import Thread, Event
from typing import Optional, Set, Dict, List

from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal as Signal
from PyQt5.QtGui import QWindow
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

from modules.utils.logger import get_logger

# ================= Win32 Binding =================

def _load_user32_attr(name: str):
    try:
        return getattr(ctypes.windll.user32, name)  # type: ignore[attr-defined]
    except Exception:
        return None

def _load_kernel32_attr(name: str):
    try:
        return getattr(ctypes.windll.kernel32, name)  # type: ignore[attr-defined]
    except Exception:
        return None

user32 = ctypes.windll.user32   # type: ignore[attr-defined]
kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

HWND   = wintypes.HWND
DWORD  = wintypes.DWORD
BOOL   = wintypes.BOOL
LPARAM = wintypes.LPARAM
UINT   = wintypes.UINT

# LONG_PTR und LRESULT kompatibel fuer Python 3.13
if ctypes.sizeof(ctypes.c_void_p) == 8:
    _LONG_PTR_T = ctypes.c_longlong
else:
    _LONG_PTR_T = ctypes.c_long
LONG_PTR = _LONG_PTR_T

WPARAM = wintypes.WPARAM
try:
    LRESULT = wintypes.LRESULT  # type: ignore[attr-defined]
except AttributeError:
    LRESULT = LONG_PTR

EnumWindowsProc = ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(DWORD)]
GetWindowThreadProcessId.restype  = DWORD

EnumWindows = user32.EnumWindows
EnumWindows.argtypes = [EnumWindowsProc, LPARAM]
EnumWindows.restype  = BOOL

EnumChildWindows = user32.EnumChildWindows
EnumChildWindows.argtypes = [HWND, EnumWindowsProc, LPARAM]
EnumChildWindows.restype  = BOOL

IsWindow = user32.IsWindow
IsWindow.argtypes = [HWND]
IsWindow.restype  = BOOL

IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.argtypes = [HWND]
IsWindowVisible.restype  = BOOL

GetClassNameW = user32.GetClassNameW
GetClassNameW.argtypes = [HWND, ctypes.c_wchar_p, ctypes.c_int]
GetClassNameW.restype  = ctypes.c_int

GetWindowTextW = user32.GetWindowTextW
GetWindowTextW.argtypes = [HWND, ctypes.c_wchar_p, ctypes.c_int]
GetWindowTextW.restype  = ctypes.c_int

GetAncestor = user32.GetAncestor
GetAncestor.argtypes = [HWND, UINT]
GetAncestor.restype  = HWND
GA_ROOT = 2

ShowWindow = user32.ShowWindow
ShowWindow.argtypes = [HWND, ctypes.c_int]
ShowWindow.restype  = BOOL
SW_SHOW = 5
SW_SHOWNOACTIVATE = 4
SW_RESTORE = 9

MoveWindow = user32.MoveWindow
MoveWindow.argtypes = [HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, BOOL]
MoveWindow.restype  = BOOL

SendMessageW = user32.SendMessageW
SendMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
SendMessageW.restype  = LRESULT

PostMessageW = user32.PostMessageW
PostMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
PostMessageW.restype  = BOOL

RedrawWindow = user32.RedrawWindow
RedrawWindow.argtypes = [HWND, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
RedrawWindow.restype  = BOOL

WM_SIZE = 0x0005
WM_WINDOWPOSCHANGING = 0x0046
WM_WINDOWPOSCHANGED  = 0x0047
WM_SETREDRAW = 0x000B
SIZE_RESTORED = 0

RDW_INVALIDATE   = 0x0001
RDW_ERASE        = 0x0004
RDW_ALLCHILDREN  = 0x0080
RDW_UPDATENOW    = 0x0100
RDW_NOFRAME      = 0x0800

GetWindowLongPtrW = user32.GetWindowLongPtrW
GetWindowLongPtrW.argtypes = [HWND, ctypes.c_int]
GetWindowLongPtrW.restype  = LONG_PTR

SetWindowLongPtrW = user32.SetWindowLongPtrW
SetWindowLongPtrW.argtypes = [HWND, ctypes.c_int, LONG_PTR]
SetWindowLongPtrW.restype  = LONG_PTR

SetWindowPos = user32.SetWindowPos
SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
SetWindowPos.restype  = BOOL

SetParent = user32.SetParent
SetParent.argtypes = [HWND, HWND]
SetParent.restype = HWND

GWL_STYLE = -16
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_CLIPSIBLINGS = 0x04000000
WS_CLIPCHILDREN = 0x02000000

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOOWNERZORDER = 0x0200
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_ASYNCWINDOWPOS = 0x4000
SWP_NOSENDCHANGING = 0x0400

# Toolhelp fuer Kindprozesse
TH32CS_SNAPPROCESS = 0x00000002

CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
CreateToolhelp32Snapshot.argtypes = [DWORD, DWORD]
CreateToolhelp32Snapshot.restype  = wintypes.HANDLE

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", DWORD),
        ("cntUsage", DWORD),
        ("th32ProcessID", DWORD),
        ("th32DefaultHeapID", ULONG_PTR),
        ("th32ModuleID", DWORD),
        ("cntThreads", DWORD),
        ("th32ParentProcessID", DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]

Process32FirstW = kernel32.Process32FirstW
Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
Process32FirstW.restype  = BOOL

Process32NextW = kernel32.Process32NextW
Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
Process32NextW.restype  = BOOL

# WaitForInputIdle kann fehlen
_WaitForInputIdle = _load_user32_attr("WaitForInputIdle")
if _WaitForInputIdle:
    _WaitForInputIdle.argtypes = [wintypes.HANDLE, DWORD]
    _WaitForInputIdle.restype  = DWORD  # 0 OK, 0x102 Timeout

# ================= Prozesse abfragen =================

def snapshot_processes() -> tuple[Dict[int, int], Dict[int, str]]:
    hSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if int(hSnap) == -1 or hSnap is None:
        return {}, {}

    parent_map: Dict[int, int] = {}
    exe_map: Dict[int, str] = {}

    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not Process32FirstW(hSnap, ctypes.byref(entry)):
            return parent_map, exe_map
        while True:
            pid = int(entry.th32ProcessID)
            ppid = int(entry.th32ParentProcessID)
            name = entry.szExeFile
            parent_map[pid] = ppid
            exe_map[pid] = name
            if not Process32NextW(hSnap, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(hSnap)

    return parent_map, exe_map

# ================= Hilfen =================

def _expected_exe_from_cmd(cmd: str) -> str:
    # Pfad bereinigen und nur Dateiname nehmen
    c = (cmd or "").strip().strip('"')
    return os.path.basename(c).lower()

# ================= Datenmodell =================

@dataclass
class LocalAppSpec:
    launch_cmd: str
    args: Optional[str] = ""                  # Parameter fuer EXE Start
    embed_mode: str = "native_window"
    window_title_pattern: Optional[str] = None
    window_class_pattern: Optional[str] = None
    child_window_class_pattern: Optional[str] = None
    child_window_title_pattern: Optional[str] = None
    follow_children: bool = True
    web_url: Optional[str] = None
    # Neu: globalen Fallback explizit erlauben
    allow_global_fallback: bool = False

# ================= Widget =================

class LocalAppWidget(QWidget):
    """
    Startet eine lokale App, sucht sichtbare Fenster der PID und bettet ein geeignetes Fenster ein.
    Sicherung: ohne explizite Freigabe wird nie ein fremdes Programm eingefangen.
    """

    ready = Signal()

    def __init__(self, spec: LocalAppSpec, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.spec = spec
        self.log = get_logger(__name__)

        self.setObjectName("LocalAppWidget")
        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors, True)

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

        self._placeholder = QLabel("Lokale Anwendung wird vorbereitet …", self)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("background: rgba(127,127,127,0.08); color: #999;")
        self._root.addWidget(self._placeholder, 1)

        self._container: Optional[QWidget] = None
        self._foreign_window: Optional[QWindow] = None

        self._proc: Optional[subprocess.Popen] = None
        self._pid: Optional[int] = None
        self._embedded_hwnd: Optional[int] = None

        self._stop_evt = Event()
        self._worker: Optional[Thread] = None
        self._starting = False

        self._resize_timer = QTimer(self)
        self._resize_timer.setInterval(120)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._apply_resize)

        self._last_find_attempt_ms = 0
        self._reattach_cooldown_ms = 800

        # Erwartete EXE zur Plausibilitaet
        self._expected_exe: str = _expected_exe_from_cmd(getattr(self.spec, "launch_cmd", ""))

    # ---------- API ----------
    def start(self):
        if self._starting or (self._worker and self._worker.is_alive()):
            return
        self._starting = True
        self._stop_evt.clear()
        self._worker = Thread(target=self._run, name="LocalAppEmbedder", daemon=True)
        self._worker.start()

    def stop(self):
        self._stop_evt.set()
        self._detach_ui()
        try:
            if self._proc and self._proc.poll() is None:
                self.log.info("lokalen Prozess beenden", extra={"source": "local"})
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=3)
                except Exception:
                    self._proc.kill()
        except Exception:
            pass
        self._proc = None
        self._pid = None
        self._embedded_hwnd = None
        self._starting = False

    def heartbeat(self):
        if self._proc and self._proc.poll() is not None:
            self.log.warning("Prozess ist beendet, starte neu", extra={"source": "local"})
            self._proc = None
            self._pid = None
            self._embedded_hwnd = None
            self._detach_ui()
            if not self._starting:
                self.start()
            return

        if self._embedded_hwnd and not bool(IsWindow(HWND(self._embedded_hwnd))):
            self.log.warning("Fenster verloren, versuche Reattach", extra={"source": "local"})
            self._embedded_hwnd = None
            self._detach_ui()

        if self._proc and self._proc.poll() is None and not self._embedded_hwnd:
            now = int(time.time() * 1000)
            if now - self._last_find_attempt_ms >= self._reattach_cooldown_ms:
                self._last_find_attempt_ms = now
                self._find_and_embed(timeout_s=1.0)

    def force_attach(self, hwnd: int):
        self.log.info(f"manuelles Attach auf hwnd={hwnd}", extra={"source": "local"})
        self._embed_hwnd(hwnd)

    def force_fit(self):
        self._apply_resize(force=True)

    # ---------- Qt Events ----------
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._resize_timer.start()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._resize_timer.start()

    # ---------- Worker ----------
    def _run(self):
        try:
            self._launch_process()
            self._find_and_embed(timeout_s=30.0)
        except Exception:
            self.log.error("Fehler im LocalApp Embedder", exc_info=True, extra={"source": "local"})
        finally:
            self._starting = False

    def _launch_process(self):
        cmd_path = (getattr(self.spec, "launch_cmd", "") or "").strip()
        if not cmd_path:
            raise RuntimeError("launch_cmd fehlt")
        args_str = (getattr(self.spec, "args", "") or "").strip()

        argv: List[str] = [cmd_path]
        if args_str:
            argv.extend(shlex.split(args_str, posix=False))

        self.log.info(f"starte: {argv}", extra={"source": "local"})
        flags = 0
        if sys.platform == "win32":
            flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._proc = subprocess.Popen(argv, shell=False, creationflags=flags)  # nosec
        self._pid = int(self._proc.pid)

        try:
            if _WaitForInputIdle is not None:
                h = getattr(self._proc, "_handle", None)
                if h is not None:
                    _WaitForInputIdle(wintypes.HANDLE(int(h)), DWORD(2000))
        except Exception:
            pass

        t0 = time.time()
        while time.time() - t0 < 0.6 and self._proc and self._proc.poll() is None:
            time.sleep(0.05)

    # ---------- Finden und Einbetten ----------
    def _find_and_embed(self, timeout_s: float):
        title_pat = getattr(self.spec, "window_title_pattern", None)
        class_pat = getattr(self.spec, "window_class_pattern", None)
        title_rx = re.compile(title_pat, re.I) if title_pat else None
        class_rx = re.compile(class_pat, re.I) if class_pat else None
        follow_children = bool(getattr(self.spec, "follow_children", True))
        allow_global = bool(getattr(self.spec, "allow_global_fallback", False))

        t_end = time.time() + timeout_s
        last_log = 0.0

        while not self._stop_evt.is_set() and time.time() < t_end:
            pid_set = self._build_pid_set(self._pid) if follow_children else ({self._pid} if self._pid else set())
            hwnd = self._pick_window(pid_set, title_rx, class_rx)

            if not hwnd and allow_global and (title_rx or class_rx):
                # Global nur, wenn EXE zur erwarteten EXE passt
                hwnd = self._pick_window_global(title_rx, class_rx)

            if hwnd:
                self._embed_hwnd(hwnd)
                return

            now = time.time()
            if now - last_log > 2.5:
                self.log.info(
                    f"suche Fenster; pid_set={sorted(list(pid_set))} "
                    f"filter_title={'ja' if title_rx else 'nein'} filter_class={'ja' if class_rx else 'nein'} "
                    f"global={'ja' if allow_global else 'nein'} expected_exe={self._expected_exe}",
                    extra={"source": "local"}
                )
                last_log = now
            time.sleep(0.15)

        self.log.warning("kein Fenster zum Einbetten gefunden", extra={"source": "local"})

    def _build_pid_set(self, root_pid: Optional[int]) -> Set[int]:
        if not root_pid:
            return set()
        try:
            parent_map, _ = snapshot_processes()
        except Exception:
            return {int(root_pid)}

        result: Set[int] = {int(root_pid)}
        queue: List[int] = [int(root_pid)]
        while queue:
            p = queue.pop()
            for child, parent in parent_map.items():
                if parent == p and child not in result:
                    result.add(child)
                    queue.append(child)
        return result

    def _exe_matches_expected(self, pid: int, exe_map: Dict[int, str]) -> bool:
        expected = self._expected_exe
        if not expected:
            return True
        exe = exe_map.get(pid, "") or ""
        return os.path.basename(exe).lower() == expected

    def _pick_window(self,
                     pid_set: Set[int],
                     title_rx: Optional[re.Pattern],
                     class_rx: Optional[re.Pattern]) -> Optional[int]:
        if not pid_set:
            return None

        # Einmaliges Mapping holen
        _, exe_map = snapshot_processes()

        candidates: List[int] = []
        titles: Dict[int, str] = {}
        classes: Dict[int, str] = {}
        pids: Dict[int, int] = {}

        def _cb(hwnd, _lparam):
            try:
                if not IsWindowVisible(hwnd):
                    return True
                root = GetAncestor(hwnd, GA_ROOT)
                if not root or root != hwnd:
                    return True

                proc_id = DWORD(0)
                GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
                pid = int(proc_id.value)
                if pid not in pid_set:
                    return True

                # EXE Plausibilitaet
                if not self._exe_matches_expected(pid, exe_map):
                    return True

                tbuf = ctypes.create_unicode_buffer(512)
                GetWindowTextW(hwnd, tbuf, 512)
                title = tbuf.value or ""

                cbuf = ctypes.create_unicode_buffer(256)
                GetClassNameW(hwnd, cbuf, 256)
                cls = cbuf.value or ""

                if title_rx and not title_rx.search(title):
                    return True
                if class_rx and not class_rx.search(cls):
                    return True

                candidates.append(int(hwnd))
                titles[int(hwnd)] = title
                classes[int(hwnd)] = cls
                pids[int(hwnd)] = pid
            except Exception:
                pass
            return True

        EnumWindows(EnumWindowsProc(_cb), 0)

        if candidates:
            def score(h: int) -> int:
                return len(titles.get(h, "")) + (5 if classes.get(h) else 0)
            best = max(candidates, key=score)
            self.log.info(
                f"kandidat(pid): hwnd={best} pid={pids.get(best)} title='{titles.get(best,'')}' class='{classes.get(best,'')}'",
                extra={"source": "local"}
            )
            return best

        return None

    def _pick_window_global(self,
                            title_rx: Optional[re.Pattern],
                            class_rx: Optional[re.Pattern]) -> Optional[int]:
        # Global nur mit EXE Filter
        _, exe_map = snapshot_processes()

        candidates: List[int] = []
        titles: Dict[int, str] = {}
        classes: Dict[int, str] = {}
        pids: Dict[int, int] = {}

        def _cb(hwnd, _lparam):
            try:
                if not IsWindowVisible(hwnd):
                    return True
                root = GetAncestor(hwnd, GA_ROOT)
                if not root or root != hwnd:
                    return True

                proc_id = DWORD(0)
                GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
                pid = int(proc_id.value)

                if not self._exe_matches_expected(pid, exe_map):
                    return True

                tbuf = ctypes.create_unicode_buffer(512)
                GetWindowTextW(hwnd, tbuf, 512)
                title = tbuf.value or ""
                cbuf = ctypes.create_unicode_buffer(256)
                GetClassNameW(hwnd, cbuf, 256)
                cls = cbuf.value or ""

                if title_rx and not title_rx.search(title):
                    return True
                if class_rx and not class_rx.search(cls):
                    return True

                candidates.append(int(hwnd))
                titles[int(hwnd)] = title
                classes[int(hwnd)] = cls
                pids[int(hwnd)] = pid
            except Exception:
                pass
            return True

        EnumWindows(EnumWindowsProc(_cb), 0)

        if candidates:
            def score(h: int) -> int:
                return len(titles.get(h, "")) + (5 if classes.get(h) else 0)
            best = max(candidates, key=score)
            self.log.info(
                f"kandidat(global): hwnd={best} pid={pids.get(best)} title='{titles.get(best,'')}' class='{classes.get(best,'')}'",
                extra={"source": "local"}
            )
            return best
        return None

    # ---------- Einbetten ----------
    def _embed_hwnd(self, hwnd: int):
        if not hwnd:
            return

        target = hwnd
        try:
            child = self._find_preferred_child(hwnd)
            if child:
                target = child
        except Exception:
            pass

        def attach_ui():
            success = False
            container = None
            foreign = None
            try:
                foreign = QWindow.fromWinId(int(target))
                foreign.setFlags(Qt.FramelessWindowHint)
                container = QWidget.createWindowContainer(foreign, parent=self)
                container.setFocusPolicy(Qt.StrongFocus)
                container.setAttribute(Qt.WA_NativeWindow, True)
            except Exception as ex:
                self.log.warning(
                    f"Qt Container fehlgeschlagen: {ex}",
                    extra={"source": "local"},
                )
                container = None

            try:
                self._fix_styles_for_child(int(target))
            except Exception:
                pass

            if container is not None:
                self._embedded_hwnd = int(target)
                self._foreign_window = foreign
                if self._container:
                    self._container.setParent(None)
                    self._container.deleteLater()
                self._container = container
                self._placeholder.setVisible(False)
                self._root.addWidget(self._container, 1)
                self._apply_resize(force=True)
                success = True
            else:
                success = self._native_reparent(int(target))

            try:
                if self._embedded_hwnd:
                    ShowWindow(HWND(self._embedded_hwnd), SW_SHOWNOACTIVATE)
            except Exception:
                pass

            if success:
                self.log.info("Fenster eingebettet", extra={"source": "local"})
                self.ready.emit()
            else:
                self.log.warning(
                    "Einbetten fehlgeschlagen; erneuter Versuch beim naechsten Heartbeat",
                    extra={"source": "local"},
                )
                self._embedded_hwnd = None

        QTimer.singleShot(0, attach_ui)

    def _native_reparent(self, hwnd: int) -> bool:
        try:
            self._fix_styles_for_child(hwnd)
            parent_hwnd = int(self.winId())
            SetParent(HWND(hwnd), HWND(parent_hwnd))
            SetWindowPos(HWND(hwnd), HWND(0), 0, 0, 0, 0,
                         SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE)
            self._embedded_hwnd = int(hwnd)
            self._placeholder.setVisible(False)
            self._apply_resize(force=True)
            self.log.info("Fenster via SetParent eingebettet", extra={"source": "local"})
            return True
        except Exception as ex:
            self.log.error(f"native Reparenting fehlgeschlagen: {ex}", extra={"source": "local"})
        return False

    def _fix_styles_for_child(self, hwnd: int):
        style = int(GetWindowLongPtrW(HWND(hwnd), GWL_STYLE))
        style &= ~WS_POPUP
        style &= ~WS_CAPTION
        style &= ~WS_THICKFRAME
        style &= ~WS_MINIMIZEBOX
        style &= ~WS_MAXIMIZEBOX
        style |= WS_CHILD | WS_CLIPSIBLINGS | WS_CLIPCHILDREN
        SetWindowLongPtrW(HWND(hwnd), GWL_STYLE, LONG_PTR(style))
        SetWindowPos(HWND(hwnd), HWND(0), 0, 0, 0, 0,
                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE)

    def _find_preferred_child(self, root_hwnd: int) -> Optional[int]:
        class_pat = getattr(self.spec, "child_window_class_pattern", None)
        title_pat = getattr(self.spec, "child_window_title_pattern", None)
        class_rx = re.compile(class_pat, re.I) if class_pat else None
        title_rx = re.compile(title_pat, re.I) if title_pat else None

        best = None
        best_score = -1

        def _cb(hwnd, _lp):
            nonlocal best, best_score
            try:
                if not IsWindowVisible(hwnd):
                    return True
                tbuf = ctypes.create_unicode_buffer(512)
                GetWindowTextW(hwnd, tbuf, 512)
                title = tbuf.value or ""
                cbuf = ctypes.create_unicode_buffer(256)
                GetClassNameW(hwnd, cbuf, 256)
                cls = cbuf.value or ""

                score = 0
                if class_rx and class_rx.search(cls):
                    score += 100
                if title_rx and title_rx.search(title):
                    score += 50
                score += min(len(title), 50)

                if score > best_score:
                    best_score = score
                    best = int(hwnd)
            except Exception:
                pass
            return True

        EnumChildWindows(HWND(root_hwnd), EnumWindowsProc(_cb), 0)
        return best

    def _apply_resize(self, force: bool = False):
        if self._container:
            self._container.setMinimumSize(QSize(1, 1))
            self._container.resize(self.size())

        if not self._embedded_hwnd:
            return

        w = max(1, int(self.width()))
        h = max(1, int(self.height()))

        try:
            SendMessageW(HWND(self._embedded_hwnd), WM_SETREDRAW, WPARAM(0), LPARAM(0))
            SetWindowPos(HWND(self._embedded_hwnd), HWND(0), 0, 0, 64, 64,
                         SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_NOACTIVATE | SWP_NOSENDCHANGING | SWP_ASYNCWINDOWPOS)
            MoveWindow(HWND(self._embedded_hwnd), 0, 0, w, h, True)
            SetWindowPos(HWND(self._embedded_hwnd), HWND(0), 0, 0, w, h,
                         SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
            SendMessageW(HWND(self._embedded_hwnd), WM_SIZE, WPARAM(SIZE_RESTORED), LPARAM((h << 16) | (w & 0xFFFF)))
        except Exception:
            pass
        finally:
            try:
                SendMessageW(HWND(self._embedded_hwnd), WM_SETREDRAW, WPARAM(1), LPARAM(0))
                RedrawWindow(HWND(self._embedded_hwnd), None, None,
                             RDW_INVALIDATE | RDW_ALLCHILDREN | RDW_UPDATENOW | RDW_NOFRAME)
                ShowWindow(HWND(self._embedded_hwnd), SW_RESTORE)
            except Exception:
                pass

    def _detach_ui(self):
        def do_detach():
            if self._container:
                self._container.setParent(None)
                self._container.deleteLater()
                self._container = None
            self._foreign_window = None
            self._placeholder.setVisible(True)
        QTimer.singleShot(0, do_detach)
