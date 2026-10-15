"""One copy at a time: two would both read the controller and both drive the camera. Windows only."""
import ctypes
from ctypes import wintypes

NAME = "Local\\ptz_joystick"        # this user's session; ptz_joystick.exe and ptz_joystick_tray.exe share it
ERROR_ACCESS_DENIED, ERROR_ALREADY_EXISTS = 5, 183

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)      # own copy: we set prototypes below
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_held: list[int] = []               # the open handles are the claim; Windows closes them when the process ends


def claim(name: str = NAME) -> bool:
    """True if no other copy holds name. This process then holds it until it ends."""
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, name)
    error = ctypes.get_last_error()
    if handle:
        _held.append(handle)
    # Access denied: a copy run as administrator holds it.
    return error not in (ERROR_ALREADY_EXISTS, ERROR_ACCESS_DENIED)
