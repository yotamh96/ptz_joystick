"""A plain message box, and a Yes/No question, for when there is no console and no window to own one. Windows only."""
import ctypes
from ctypes import wintypes

MB_YESNO, MB_ICONQUESTION, MB_ICONWARNING, IDYES = 0x04, 0x20, 0x30, 6

user32 = ctypes.WinDLL("user32")            # own copy: we set prototypes below
user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]


def message_box(text: str, title: str = "ptz_joystick"):
    """Show text and wait for OK."""
    user32.MessageBoxW(None, text, title, MB_ICONWARNING)


def ask(text: str, title: str = "ptz_joystick") -> bool:
    """Show text with Yes and No, and wait. -> True for Yes."""
    return user32.MessageBoxW(None, text, title, MB_YESNO | MB_ICONQUESTION) == IDYES
