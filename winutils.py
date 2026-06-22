"""
winutils.py – Small Win32 helpers backing the cursor-lock and
always-on-top hotkey features. Windows-only; pure ctypes, no extra
dependencies required.
"""

import ctypes
import sys
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.GetForegroundWindow.restype = wintypes.HWND
user32.ClipCursor.argtypes = [ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_uint
]

GWL_EXSTYLE    = -20
WS_EX_TOPMOST  = 0x00000008
HWND_TOPMOST   = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE     = 0x0002
SWP_NOSIZE     = 0x0001
SWP_NOACTIVATE = 0x0010


def get_foreground_window():
    """Returns the HWND of the currently active window."""
    return user32.GetForegroundWindow()


def lock_cursor_to_window(hwnd):
    """Clips the cursor to the bounds of the given window. Returns True on success."""
    if not hwnd:
        return False
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    return bool(user32.ClipCursor(ctypes.byref(rect)))


def release_cursor_lock():
    """Removes any active cursor clip. Safe to call even if nothing is locked."""
    user32.ClipCursor(None)


def toggle_always_on_top(hwnd=None):
    """
    Toggles the topmost (always-on-top) state of a window, mirroring
    AutoHotkey's `WinSet, AlwaysOnTop, Toggle, A`. Defaults to the
    current foreground window. Returns the new state (True = now on top).
    """
    if hwnd is None:
        hwnd = get_foreground_window()
    if not hwnd:
        return False

    ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    is_topmost = bool(ex_style & WS_EX_TOPMOST)
    target = HWND_NOTOPMOST if is_topmost else HWND_TOPMOST

    user32.SetWindowPos(
        hwnd, target, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
    )
    return not is_topmost

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def relaunch_as_admin():
    """Relaunches this program elevated via the UAC prompt. Caller should quit right after."""
    exe = sys.executable
    if getattr(sys, "frozen", False):
        # Compiled exe (PyInstaller) — sys.argv[0] is the exe itself, skip it
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
    else:
        params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)