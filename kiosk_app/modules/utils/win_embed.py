import ctypes
import ctypes.wintypes as wt
import re

user32 = ctypes.windll.user32

EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
GetWindowText = user32.GetWindowTextW
GetWindowTextLength = user32.GetWindowTextLengthW
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
SetParent = user32.SetParent
SetWindowLong = user32.SetWindowLongW
GetWindowLong = user32.GetWindowLongW
SetWindowPos = user32.SetWindowPos
GetClientRect = user32.GetClientRect
MoveWindow = user32.MoveWindow

WS_CHILD = 0x40000000
WS_CLIPSIBLINGS = 0x04000000
WS_CLIPCHILDREN = 0x02000000
GWL_STYLE = -16
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020

def find_window_by_title_regex(pattern: str):
    rx = re.compile(pattern)
    result = []

    def _enum_proc(hwnd, lparam):
        length = GetWindowTextLength(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(hwnd, buff, length + 1)
        title = buff.value or ""
        if rx.search(title):
            result.append(hwnd)
            return False
        return True

    EnumWindows(EnumWindowsProc(_enum_proc), 0)
    return result[0] if result else None

def find_window_for_pid(pid: int, title_regex: str | None = None):
    rx = re.compile(title_regex) if title_regex else None
    found = None

    def _enum(hwnd, lparam):
        nonlocal found
        pid_out = wt.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
        if pid_out.value != pid:
            return True
        length = GetWindowTextLength(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(hwnd, buff, length + 1)
        title = buff.value or ""
        if rx is None or rx.search(title):
            found = hwnd
            return False
        return True

    EnumWindows(EnumWindowsProc(_enum), 0)
    return found

def set_parent_embed(child_hwnd: int, parent_hwnd: int) -> bool:
    ok = SetParent(wt.HWND(child_hwnd), wt.HWND(parent_hwnd))
    return ok != 0

def set_child_styles(child_hwnd: int):
    style = GetWindowLong(wt.HWND(child_hwnd), GWL_STYLE)
    style = style | WS_CHILD | WS_CLIPSIBLINGS | WS_CLIPCHILDREN
    SetWindowLong(wt.HWND(child_hwnd), GWL_STYLE, style)
    SetWindowPos(wt.HWND(child_hwnd), None, 0, 0, 0, 0,
                 SWP_NOZORDER | SWP_NOMOVE | SWP_NOSIZE | SWP_FRAMECHANGED)

def resize_child_to_parent(child_hwnd: int, parent_hwnd: int):
    rect = wt.RECT()
    GetClientRect(wt.HWND(parent_hwnd), ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    MoveWindow(wt.HWND(child_hwnd), 0, 0, w, h, True)
