"""The settings dialog (tray menu → Settings…): every setting and the camera password in one window. It runs on a
thread of its own, the same one for every open: Tk must stay on the thread that made it, the tray's thread runs the
icon's message loop, and Tcl keeps ~0.5 MB for every thread that ever ran Tk, for good.
open_dialog() is all the tray uses. Windows only."""
import ctypes
import functools
import gc
import logging
import os
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import replace
from pathlib import Path

from ... import config
from ...config import Settings
from ...core.problem import Problem
from ..message_box import ask
from ..user_env import user_env
from .window import SettingsWindow, write

log = logging.getLogger(__name__)

CLOSE_SECONDS = 1.0             # Quit waits this long for the dialog; it checks every 100 ms
SW_RESTORE = 9
DPI_AWARENESS_CONTEXT_SYSTEM_AWARE = -2     # Tk 8.6 scales by the system DPI only

user32 = ctypes.WinDLL("user32", use_last_error=True)       # own copy: we set prototypes below
user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]


class Handle:
    """The tray's hold on an open dialog. focus() and close() are safe from the tray's thread."""

    def __init__(self):
        self.closing = threading.Event()
        self.done = threading.Event()   # this open is over: the window closed, or never opened
        self.hwnd = 0                   # the window, once the dialog's thread has made it

    @property
    def alive(self) -> bool:
        return not self.done.is_set()

    def focus(self):
        """Bring the window to the front. Allowed: the tray's menu has just given this process the foreground."""
        if self.hwnd:
            user32.ShowWindow(self.hwnd, SW_RESTORE)
            user32.SetForegroundWindow(self.hwnd)

    def close(self):
        """Close the window (unsaved changes are dropped) and wait for it."""
        self.closing.set()
        self.done.wait(CLOSE_SECONDS)


def open_dialog(path: Path, cameras: dict[str, dict[str, int]], controllers: list[str],
                type_error: Callable[[Settings], str | None], on_restart: Callable[[], None],
                on_notepad: Callable[[], None]) -> Handle:
    """Show the dialog on the dialog's thread. cameras: each camera type's top speeds. The callbacks run on the
    dialog's thread, so on_restart must hand over to the tray's thread (HiddenWindow.post)."""
    handle = Handle()
    _dialog_thread().put(lambda: _run(handle, path, cameras, controllers, type_error, on_restart, on_notepad))
    return handle


@functools.cache
def _dialog_thread() -> queue.SimpleQueue[Callable[[], None]]:
    """The dialog's thread, started on the first open and kept for the life of the tray. -> its to-do queue."""
    jobs: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()

    def serve():
        while True:
            jobs.get()()

    threading.Thread(target=serve, name="settings-dialog", daemon=True).start()
    return jobs


def _run(handle: Handle, path: Path, cameras, controllers, type_error, on_restart, on_notepad):
    try:
        try:
            config.write_template_if_missing(path)        # deleted since the tray started
            settings = config.read(path)
        except Problem as p:                                # the same words as the red dot
            if ask(f"{p.text()}\n\nOpen it in Notepad?"):
                on_notepad()
            return
        password = user_env("PTZ_PASSWORD") or os.environ.get("PTZ_PASSWORD", "")
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(DPI_AWARENESS_CONTEXT_SYSTEM_AWARE))   # crisp at 150 %
        root = tk.Tk()
        window = SettingsWindow(root, path, replace(settings, password=password), cameras, controllers, type_error,
                                lambda s: write(path, s, password), on_restart, on_notepad)
        window.watch(handle.closing)
        root.update_idletasks()
        handle.hwnd = int(root.wm_frame(), 16)
        root.focus_force()
        root.mainloop()
        del window, root
        gc.collect()            # free every Tk object on this thread: freed on another, Tcl aborts the process
    except Exception:           # Tk can't run here (a broken build?): the file in Notepad, as before the dialog
        log.exception("Settings dialog failed, opening the settings file in Notepad instead")
        on_notepad()
    finally:
        handle.done.set()
