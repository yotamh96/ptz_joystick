"""A user environment variable as setx left it, for a program that started before setx ran, and setting one as setx
does. Windows only.

A running program keeps the environment it started with. setx writes HKCU\\Environment, so reading there finds a
password set after the tray app started."""
import ctypes
import winreg
from ctypes import wintypes

KEY = "Environment"
HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x001A, 0x0002
BROADCAST_MS = 1000             # a program that doesn't answer within this is skipped

user32 = ctypes.WinDLL("user32", use_last_error=True)       # own copy: we set prototypes below
user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPCWSTR,
                                       wintypes.UINT, wintypes.UINT, ctypes.c_void_p]


def user_env(name: str, key: str = KEY) -> str | None:
    """The variable from HKCU\\<key>, expanded the way Windows expands it for new programs. None if not there."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            value, kind = winreg.QueryValueEx(k, name)
    except OSError:                     # no such key or value
        return None
    if not isinstance(value, str):
        return None
    return winreg.ExpandEnvironmentStrings(value) if kind == winreg.REG_EXPAND_SZ else value


def set_user_env(name: str, value: str, key: str = KEY):
    """Save the variable in HKCU\\<key> as plain text (REG_SZ: % is not expanded), as setx does, and tell Explorer,
    so programs started from now on get it. Raises OSError if the registry refuses."""
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
    user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, KEY, SMTO_ABORTIFHUNG, BROADCAST_MS, None)
