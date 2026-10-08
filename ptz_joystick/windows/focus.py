"""Is this program's window the one in front? For controllers/keyboard.py, so keys typed into other windows don't
move the camera. Windows only.

"This program's window" depends on where it runs: the classic console window, the Windows Terminal window that
owns it, or (VS Code, which hides the console) a window of one of our parent processes.
"""
import ctypes
import os
from ctypes import wintypes

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


class OwnWindow:
    """Looks up our windows and processes once; in_front() is then cheap enough for every read."""

    def __init__(self):
        self._windows, self._pids = _console_windows(), _ancestor_pids()

    def in_front(self) -> bool:
        hwnd, pid = _foreground()
        return hwnd in self._windows or pid in self._pids
