"""Run a callback when the console window is closed, or on logoff / shutdown. Windows only.

Windows ends the process right after these events, so try/finally in app.run never runs: this is the only
chance to stop the camera. Windows allows about 5 s.
"""
import ctypes
import logging
import os
import sys
from ctypes import wintypes

from ..core.problem import Problem

log = logging.getLogger(__name__)

CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT = 2, 5, 6
_HandlerRoutine = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
_registered: list[object] = []     # keep the ctypes callbacks alive, or Windows calls freed memory


def make_handler(callback):
    def handler(event):
        if event not in (CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT):
            return False                # Ctrl+C / Ctrl+Break: next handler, i.e. Python's KeyboardInterrupt
        try:
            callback()
        except Exception:
            log.exception("console-close handler failed")
        return True
    return handler


def on_console_close(callback):
    routine = _HandlerRoutine(make_handler(callback))
    if ctypes.windll.kernel32.SetConsoleCtrlHandler(routine, True):
        _registered.append(routine)
    else:
        log.warning(Problem("Can't watch for the console window closing", fix="Quit with Ctrl+C so the camera stops",
                            detail=str(ctypes.WinError())).log_line())


def _console_pids() -> list[int]:
    """The processes attached to this console; empty without one."""
    pids = (wintypes.DWORD * 64)()
    n = ctypes.windll.kernel32.GetConsoleProcessList(pids, len(pids))
    return list(pids[:min(n, len(pids))])


def owns_console() -> bool:
    """True when this console window was opened for us (the exe was double-clicked), so it closes the moment we
    exit. A terminal's shell on the list means it wasn't."""
    pids = _console_pids()
    us = {os.getpid()}
    if getattr(sys, "frozen", False):       # a PyInstaller onefile exe runs as two: the bootloader is our parent
        us.add(os.getppid())                # (not from source: there the parent is the shell that ran python)
    return bool(pids) and set(pids) <= us
