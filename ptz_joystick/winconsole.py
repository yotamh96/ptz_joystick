"""Run a callback when the console window is closed, or on logoff / shutdown. Windows only.

Windows ends the process right after these events, so try/finally in app.run never runs: this is the only
chance to stop the camera. Windows allows about 5 s.
"""
import ctypes
import logging
from ctypes import wintypes

log = logging.getLogger(__name__)

CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT = 2, 5, 6
_HandlerRoutine = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
_registered = []        # keep the ctypes callbacks alive, or Windows calls freed memory


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
        log.warning("Can't watch for the console closing (%s): close with Ctrl+C to stop the camera.",
                    ctypes.WinError())
