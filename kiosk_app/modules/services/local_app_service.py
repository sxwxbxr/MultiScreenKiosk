from __future__ import annotations

import ctypes
from ctypes import wintypes
import subprocess
import sys
import time
import re
from dataclasses import dataclass
from threading import Thread, Event
from typing import Optional, Set, Dict, List

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication

from modules.utils.logger import get_logger


# ---------------- Win32 Setup ----------------

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
LONG_PTR = wintypes.LPARAM  # fuer GetWindowLongPtr Rueckgabe

# EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(DWORD)]
GetWindowThreadProcessId.restype  = DWORD

EnumWindows = user32.EnumWindows
EnumWindows.argtypes = [EnumWindowsProc, LPARAM]
EnumWindows.restype  = BOOL

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

SetForegroundWindow = user32.SetForegroundWindow
SetForegroundWindow.argtypes = [HWND]
SetForegroundWindow.restype = BOOL

# WaitForInputIdle ist nicht immer verfuegbar, daher guard
_WaitForInputIdle = _load_user32_attr("WaitForInputIdle")
if _WaitForInputIdle:
    _WaitForInputIdle.argtypes = [wintypes.HANDLE, DWORD]
    _WaitForInputIdle.restype = DWORD  # 0 = OK, WAIT_TIMEOUT = 0x102

# Fallback Reparenting
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
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020

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


# ---------------- Prozesse abfragen ----------------

def snapshot_processes() -> tuple[Dict[int, int], Dict[int, str]]:
    """
    Liefert child_pid -> parent_pid und pid -> exe_name.
    """
    hSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if int(hSnap) == -1 or hSnap is None:
        raise OSError("CreateToolhelp32Snapshot fehlgeschlagen")

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


# ---------------- Helfer ----------------

def _expected_exe_from_cmd(cmd: str) -> str:
    """
    Gibt den erwarteten Exe Dateinamen aus dem launch_cmd zurueck, in lower case.
    Beispiel: "C:\\Windows\\notepad.exe /A" -> "notepad.exe"
    """
    s = (cmd or "").strip().strip('"').strip("'")
    if not s:
        return ""
    # bis erstes Leerzeichen nehmen
    path = s.split(" ", 1)[0]
    # nur Dateiname
    base = path.replace("/", "\\").split("\\")[-1]
    return base.lower()

def _safe_wait_input_idle(popen: subprocess.Popen, timeout_ms: int = 2000) -> None:
    """
    Ruft WaitForInputIdle sicher auf, wenn verfuegbar. Ignoriert Fehler.
    """
    try:
        if _WaitForInputIdle is None:
            return
        # Handle aus Popen holen
        h = getattr(popen, "_handle", None)
        if h is None:
            return
        _WaitForInputIdle(wintypes.HANDLE(int(h)), DWORD(timeout_ms))
    except Exception:
        return


# ---------------- Modell ----------------

@dataclass
class LocalAppSpec:
    launch_cmd: str
    embed_mode: str = "native_window"
    window_title_pattern: Optional[str] = None
    window_class_pattern: Optional[str] = None
    follow_children: bool = True
    web_url: Optional[str] = None


# ---------------- Widget ----------------

class LocalAppWidget(QWidget):
    """
    Startet eine lokale App, merkt sich die PID, sucht sichtbare Top Level Fenster
    der PID oder deren Kindprozesse und bettet das Fenster als QWindow in Qt ein.
    Fallback: natives Reparenting via SetParent falls noetig.
    """

    def __init__(self, spec: LocalAppSpec, parent: Optional[Widget] = None):  # type: ignore[name-defined]
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

        # fuer Debug
        self._expected_exe = _expected_exe_from_cmd(spec.launch_cmd)

    # -------- API --------
    def start(self):
        if self._starting:
            self.log.info("start ignoriert, Start laeuft bereits", extra={"source": "local"})
            return
        if self._worker and self._worker.is_alive():
            self.log.info("start ignoriert, Worker aktiv", extra={"source": "local"})
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
        # Prozess beendet
        if self._proc and self._proc.poll() is not None:
            self.log.warning("Prozess ist beendet, starte neu", extra={"source": "local"})
            self._proc = None
            self._pid = None
            self._embedded_hwnd = None
            self._detach_ui()
            if not self._starting:
                self.start()
            return

        # Fenster verloren
        if self._embedded_hwnd and not bool(IsWindow(HWND(self._embedded_hwnd))):
            self.log.warning("Fenster verloren, versuche Reattach", extra={"source": "local"})
            self._embedded_hwnd = None
            self._detach_ui()
            self._find_and_embed(timeout_s=8.0)

    # Fuer Fenster Spy, manuelles Attach
    def force_attach(self, hwnd: int):
        self.log.info(f"manuelles Attach auf hwnd={hwnd}", extra={"source": "local"})
        self._embed_hwnd(hwnd)

    # -------- Events --------
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._resize_timer.start()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._resize_timer.start()

    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)
        if self._embedded_hwnd:
            try:
                SetForegroundWindow(HWND(self._embedded_hwnd))
            except Exception:
                pass

    # -------- Worker --------
    def _run(self):
        try:
            self._launch_process()
            self._find_and_embed(timeout_s=25.0)
        except Exception:
            self.log.error("Fehler im LocalApp Embedder", exc_info=True, extra={"source": "local"})
        finally:
            self._starting = False

    def _launch_process(self):
        if self._proc and self._proc.poll() is None:
            return
        cmd = (self.spec.launch_cmd or "").strip()
        if not cmd:
            raise RuntimeError("launch_cmd fehlt in LocalAppSpec")

        self.log.info(f"starte: {cmd}", extra={"source": "local"})
        flags = 0
        if sys.platform == "win32":
            flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._proc = subprocess.Popen(cmd, shell=False, creationflags=flags)  # nosec
        self._pid = int(self._proc.pid)

        # GUI Zeit geben
        _safe_wait_input_idle(self._proc, 2000)

        # kurze Gnadenfrist
        t0 = time.time()
        while time.time() - t0 < 0.6 and not self._stop_evt.is_set():
            if self._proc.poll() is not None:
                raise RuntimeError("Prozess beendete sich direkt nach Start")
            time.sleep(0.05)

    # -------- Finden und Einbetten --------
    def _find_and_embed(self, timeout_s: float):
        title_rx = re.compile(self.spec.window_title_pattern, re.I) if self.spec.window_title_pattern else None
        class_rx = re.compile(self.spec.window_class_pattern, re.I) if self.spec.window_class_pattern else None

        t_end = time.time() + timeout_s
        last_log = 0.0

        while not self._stop_evt.is_set() and time.time() < t_end:
            pid_set = self._build_pid_set(self._pid) if self.spec.follow_children else ({self._pid} if self._pid else set())
            hwnd = self._pick_window(pid_set, title_rx, class_rx)

            if hwnd:
                self._embed_hwnd(hwnd)
                return

            now = time.time()
            if now - last_log > 2.5:
                self.log.info(f"suche Fenster fuer PID Set {sorted(list(pid_set))}", extra={"source": "local"})
                last_log = now

            time.sleep(0.15)

        self.log.warning("kein Fenster zum Einbetten gefunden", extra={"source": "local"})

    def _build_pid_set(self, root_pid: Optional[int]) -> Set[int]:
        if not root_pid:
            return set()
        try:
            parent_map, _ = snapshot_processes()
        except Exception:
            return {root_pid}

        result: Set[int] = {int(root_pid)}
        queue: List[int] = [int(root_pid)]
        while queue:
            p = queue.pop()
            for child, parent in parent_map.items():
                if parent == p and child not in result:
                    result.add(child)
                    queue.append(child)
        return result

    def _pick_window(self,
                     pid_set: Set[int],
                     title_rx: Optional[re.Pattern],
                     class_rx: Optional[re.Pattern]) -> Optional[int]:
        candidates: List[int] = []
        titles: Dict[int, str] = {}
        classes: Dict[int, str] = {}
        pids: Dict[int, int] = {}

        expected_exe = self._expected_exe

        def _cb(hwnd, lparam):
            try:
                if not IsWindowVisible(hwnd):
                    return True
                root = GetAncestor(hwnd, GA_ROOT)
                if not root or root != hwnd:
                    return True

                # PID
                proc_id = DWORD(0)
                GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
                pid = int(proc_id.value)

                if pid_set and pid not in pid_set:
                    return True

                # Titel
                tbuf = ctypes.create_unicode_buffer(512)
                GetWindowTextW(hwnd, tbuf, 512)
                title = tbuf.value or ""

                # Klasse
                cbuf = ctypes.create_unicode_buffer(256)
                GetClassNameW(hwnd, cbuf, 256)
                cls = cbuf.value or ""

                # Filter
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
            # score: wenn erwartete exe in pid_set vorkommt, reicht Laenge des Titels als Proxy
            def score(h: int) -> int:
                return len(titles.get(h, "")) + (5 if classes.get(h) else 0)
            best = max(candidates, key=score)
            self.log.info(
                f"Fensterkandidat: hwnd={best} pid={pids.get(best)} "
                f"title='{titles.get(best,'')}' class='{classes.get(best,'')}'",
                extra={"source": "local"}
            )
            return best

        # Fallback ohne Filter: erstes sichtbares Root Fenster aus PID Set
        if not title_rx and not class_rx and pid_set:
            def _cb2(hwnd, lparam):
                try:
                    if not IsWindowVisible(hwnd):
                        return True
                    root = GetAncestor(hwnd, GA_ROOT)
                    if not root or root != hwnd:
                        return True
                    proc_id = DWORD(0)
                    GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
                    pid = int(proc_id.value)
                    if pid in pid_set:
                        candidates.append(int(hwnd))
                except Exception:
                    pass
                return True
            EnumWindows(EnumWindowsProc(_cb2), 0)
            if candidates:
                return candidates[0]

        return None

    # -------- Einbetten --------
    def _embed_hwnd(self, hwnd: int):
        if not hwnd:
            return
        self._embedded_hwnd = int(hwnd)

        # 1) Qt Weg
        container = None
        foreign = None
        try:
            foreign = QWindow.fromWinId(int(hwnd))
            foreign.setFlags(Qt.FramelessWindowHint)
            container = QWidget.createWindowContainer(foreign, parent=self)
            container.setFocusPolicy(Qt.StrongFocus)
            container.setAttribute(Qt.WA_NativeWindow, True)
        except Exception as ex:
            self.log.warning(f"Qt Container fehlgeschlagen: {ex}", extra={"source": "local"})
            container = None

        def attach_ui():
            if container is not None:
                self._foreign_window = foreign
                if self._container:
                    self._container.setParent(None)
                    self._container.deleteLater()
                self._container = container
                self._placeholder.setVisible(False)
                self._root.addWidget(self._container, 1)
                self._apply_resize()
            else:
                self._placeholder.setVisible(True)
            try:
                ShowWindow(HWND(self._embedded_hwnd), SW_SHOW)
            except Exception:
                pass
            self.log.info("Fenster eingebettet via Qt Container" if container is not None else "Qt Container nicht verfuegbar", extra={"source": "local"})
        QTimer.singleShot(0, attach_ui)

        # 2) Fallback Reparenting
        if container is None:
            self._native_reparent(hwnd)

    def _native_reparent(self, hwnd: int):
        """Als Fallback SetParent und Styles anpassen."""
        try:
            parent_hwnd = int(self.winId())
            style = int(GetWindowLongPtrW(HWND(hwnd), GWL_STYLE))
            style = (style | WS_CHILD) & ~WS_POPUP
            SetWindowLongPtrW(HWND(hwnd), GWL_STYLE, LONG_PTR(style))
            SetParent(HWND(hwnd), HWND(parent_hwnd))
            SetWindowPos(HWND(hwnd), None, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
            self._embedded_hwnd = int(hwnd)
            self._placeholder.setVisible(False)
            self.log.info("Fenster via SetParent eingebettet", extra={"source": "local"})
        except Exception as ex:
            self.log.error(f"native Reparenting fehlgeschlagen: {ex}", extra={"source": "local"})

    def _apply_resize(self):
        if self._container:
            self._container.setMinimumSize(QSize(1, 1))
            self._container.resize(self.size())

    def _detach_ui(self):
        def do_detach():
            if self._container:
                self._container.setParent(None)
                self._container.deleteLater()
                self._container = None
            self._foreign_window = None
            self._placeholder.setVisible(True)
        QTimer.singleShot(0, do_detach)
