"""Admin rights: Zao Virtual Cabin runs as admin, and Windows hides keys typed into an admin window from a program
that isn't one, so the tray restarts itself as admin. Windows only."""
import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

SW_SHOWNORMAL = 1

shell32 = ctypes.WinDLL("shell32")          # own copy: we set prototypes below
shell32.ShellExecuteW.restype = ctypes.c_ssize_t        # a number, not a real handle: above 32 is success
shell32.ShellExecuteW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                  wintypes.LPCWSTR, ctypes.c_int]


def is_admin() -> bool:
    return bool(shell32.IsUserAnAdmin())


def command(args: list[str]) -> tuple[str, str]:
    """This program with args, as (exe, parameters): the exe itself when built by PyInstaller, else python -m."""
    if getattr(sys, "frozen", False):
        return sys.executable, subprocess.list2cmdline(args)
    return sys.executable, subprocess.list2cmdline(["-m", "ptz_joystick", *args])


def relaunch_as_admin(args: list[str]) -> bool:
    """Start this program again as admin, from the same folder. Windows shows the UAC prompt; False if it was
    refused."""
    exe, params = command(args)
    return shell32.ShellExecuteW(None, "runas", exe, params, os.getcwd(), SW_SHOWNORMAL) > 32
