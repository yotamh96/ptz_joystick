"""Is a given program's window the one in front? For controllers/keyboard.py, so keys typed into other windows don't
move the camera. Windows only."""
import ctypes
from ctypes import wintypes

TH32CS_SNAPPROCESS = 2

user32, kernel32 = ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")     # own copies: we set prototypes below
user32.GetForegroundWindow.restype = wintypes.HWND
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


class AppInFront:
    """True while a window of the program named exe_name (e.g. "Zao Virtual Cabin.exe") is in front. Takes a process
    snapshot only when the foreground window's process changes, so in_front() is cheap enough for every read."""

    def __init__(self, exe_name: str):
        self._exe = exe_name.lower()
        self._pid: int | None = None
        self._match = False

    def in_front(self) -> bool:
        _, pid = _foreground()
        if pid != self._pid:
            self._pid = pid
            self._match = _processes().get(pid, (0, ""))[1].lower() == self._exe
        return self._match
