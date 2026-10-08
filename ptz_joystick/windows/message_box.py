"""A plain message box, for an error when there is no console and no tray icon yet. Windows only."""
import ctypes
from ctypes import wintypes

MB_ICONWARNING = 0x30

user32 = ctypes.WinDLL("user32")            # own copy: we set prototypes below
user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]


def message_box(text: str, title: str = "ptz_joystick"):
    """Show text and wait for OK."""
    user32.MessageBoxW(None, text, title, MB_ICONWARNING)
