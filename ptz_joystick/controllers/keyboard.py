"""Keyboard as a controller, for testing without a gamepad. Windows only.

Arrows = left stick (pan / tilt), W / S = right stick up / down (zoom), keys 1-4 = buttons 1-4.
A key reads as the stick pushed fully, so moves run at pan_max / tilt_max / zoom_max.
Keys count only while this program's window is in front; otherwise it reads as sticks centred, nothing held.
"""
import ctypes
import os
from ctypes import wintypes

from ..config import Settings
from . import ControllerState

VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN = 0x25, 0x26, 0x27, 0x28
BUTTON_KEYS = "1234"       # a digit's or letter's virtual-key code is its ASCII code
HELP = "Keyboard controller: arrows pan/tilt, W/S zoom in/out, 1-4 = presets. Keys work while this window is in front."
GA_ROOTOWNER, TH32CS_SNAPPROCESS = 3, 2

user32, kernel32 = ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")     # own copies: we set prototypes below
user32.GetForegroundWindow.restype = kernel32.GetConsoleWindow.restype = wintypes.HWND
user32.GetAncestor.restype, user32.GetAncestor.argtypes = wintypes.HWND, [wintypes.HWND, wintypes.UINT]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]


def _held(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def _foreground() -> tuple[int | None, int]:
    """The window in front and the process that owns it."""
    hwnd = user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return hwnd, pid.value


def _console_windows() -> set[int]:
    """The classic console window, plus its owner: Windows Terminal hides the console behind its own window."""
    console = kernel32.GetConsoleWindow()
    return {h for h in (console, console and user32.GetAncestor(console, GA_ROOTOWNER)) if h}


def _processes() -> dict[int, tuple[int, str]]:
    """Every running process: pid -> (parent pid, exe name)."""
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    entry = PROCESSENTRY32W(dwSize=ctypes.sizeof(PROCESSENTRY32W))
    procs = {}
    ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
    while ok:
        procs[entry.th32ProcessID] = (entry.th32ParentProcessID, entry.szExeFile)
        ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    kernel32.CloseHandle(snap)
    return procs


def _ancestor_pids() -> set[int]:
    """This process and its parents, up to but not including explorer.exe. A terminal that hides the console
    window (VS Code) is one of them. explorer.exe is left out, or File Explorer in front would count."""
    procs, pids, pid = _processes(), set(), os.getpid()
    while pid in procs and pid not in pids and procs[pid][1].lower() != "explorer.exe":
        pids.add(pid)
        pid = procs[pid][0]
    return pids


class KeyboardController:
    def __init__(self, settings: Settings):
        self._pan, self._tilt, self._zoom = settings.pan_axis, settings.tilt_axis, settings.zoom_axis
        self._windows, self._pids = _console_windows(), _ancestor_pids()

    def _focused(self) -> bool:
        hwnd, pid = _foreground()
        return hwnd in self._windows or pid in self._pids

    def read(self) -> ControllerState:
        def axis(minus: int, plus: int) -> float:
            return float(_held(plus) - _held(minus))

        if not self._focused():
            return ControllerState(dict.fromkeys((self._pan, self._tilt, self._zoom), 0.0), 0)
        # Up reads low, like the real pad (hence invert_tilt / invert_zoom = true), so the same settings work.
        axes = {self._pan: axis(VK_LEFT, VK_RIGHT), self._tilt: axis(VK_UP, VK_DOWN), self._zoom: axis(ord("W"), ord("S"))}
        buttons = sum(_held(ord(k)) << i for i, k in enumerate(BUTTON_KEYS))
        return ControllerState(axes, buttons)
