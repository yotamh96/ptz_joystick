"""The icon in the notification area: add, change, pop up a message, remove. Use it on the window's thread.
Windows only."""
import ctypes
from collections.abc import Callable
from ctypes import wintypes

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
NIIF_INFO, NIIF_WARNING, NIIF_ERROR = 1, 2, 3
RETRY_SECONDS = 2.0             # Start with Windows may run us before the taskbar is there


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", ctypes.c_wchar * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", ctypes.c_wchar * 256), ("uVersion", wintypes.UINT), ("szInfoTitle", ctypes.c_wchar * 64),
                ("dwInfoFlags", wintypes.DWORD), ("guidItem", GUID), ("hBalloonIcon", wintypes.HICON)]


shell32 = ctypes.WinDLL("shell32")          # own copy: we set prototypes below
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]


def fit(text: str, size: int) -> str:
    """text for a WCHAR[size] field, leaving room for the closing NUL. Counted in UTF-16 units as Windows counts;
    a cut text ends with an ellipsis."""
    units = text.encode("utf-16-le")
    if len(units) <= (size - 1) * 2:
        return text
    return units[:(size - 2) * 2].decode("utf-16-le", errors="ignore") + "…"     # ignore: half an emoji


def _notify(message: int, data: NOTIFYICONDATAW) -> bool:
    return bool(shell32.Shell_NotifyIconW(message, ctypes.byref(data)))


class TrayIcon:
    def __init__(self, hwnd: int, callback_message: int, later: Callable[[float, Callable[[], None]], None]):
        """Mouse events come to hwnd as callback_message. later(seconds, fn) runs fn on the window's thread after
        that long: the retry when the taskbar isn't there yet."""
        self._hwnd, self._message, self._later = hwnd, callback_message, later
        self._hicon, self._tip = 0, ""
        self._added = self._retrying = self._removed = False
        self._pending: tuple[str, str, int] | None = None       # a pop-up asked for before the icon was there

    def set(self, hicon: int, tip: str):
        """Show this icon and hover text."""
        self._hicon, self._tip = hicon, tip
        if self._added:
            self._send(NIM_MODIFY, NIF_ICON | NIF_TIP)
        elif not self._retrying:
            self._add()

    def popup(self, title: str, text: str, kind: int):
        """A pop-up from the icon (a notification on Windows 10 and 11). kind: NIIF_INFO, NIIF_WARNING or NIIF_ERROR."""
        if not self._added:
            self._pending = (title, text, kind)
            return
        data = self._data(NIF_INFO)
        data.szInfoTitle, data.szInfo, data.dwInfoFlags = fit(title, 64), fit(text, 256), kind
        _notify(NIM_MODIFY, data)

    def taskbar_created(self):
        """Explorer (re)started and our icon went with it: add it again."""
        self._added = False
        self._add()

    def remove(self):
        if self._added:
            _notify(NIM_DELETE, self._data(0))
        self._added, self._removed = False, True

    def _add(self):
        if self._added or self._removed:
            return
        flags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        # NIM_ADD also fails while Explorer still has our icon: TaskbarCreated after a DPI or monitor change, or an
        # add that timed out at sign-in but worked. NIM_MODIFY then takes the icon over instead of retrying forever.
        if self._send(NIM_ADD, flags) or self._send(NIM_MODIFY, flags):
            self._added = True
            if self._pending:
                pending, self._pending = self._pending, None
                self.popup(*pending)
        elif not self._retrying:
            self._retrying = True
            self._later(RETRY_SECONDS, self._retry)

    def _retry(self):
        self._retrying = False
        self._add()

    def _data(self, flags: int) -> NOTIFYICONDATAW:
        return NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=self._hwnd, uID=1, uFlags=flags)

    def _send(self, message: int, flags: int) -> bool:
        data = self._data(flags)
        data.uCallbackMessage, data.hIcon, data.szTip = self._message, self._hicon, fit(self._tip, 128)
        return _notify(message, data)
