"""The settings dialog (tray menu → Settings…): every setting and the camera password in one window. It runs on its
own thread: Tk must stay on the thread that made it, and the tray's thread runs the icon's message loop.
open_dialog() is all the tray uses. Windows only."""
import ctypes
import gc
import logging
import os
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
        self.hwnd = 0                   # the window, once the dialog's thread has made it
        self.thread: threading.Thread | None = None

    @property
    def alive(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def focus(self):
        """Bring the window to the front. Allowed: the tray's menu has just given this process the foreground."""
        if self.hwnd:
            user32.ShowWindow(self.hwnd, SW_RESTORE)
            user32.SetForegroundWindow(self.hwnd)

    def close(self):
        """Close the window (unsaved changes are dropped) and wait for it."""
        self.closing.set()
        if self.thread:
            self.thread.join(CLOSE_SECONDS)


def open_dialog(path: Path, cameras: dict[str, dict[str, int]], controllers: list[str],
                type_error: Callable[[Settings], str | None], on_restart: Callable[[], None],
                on_notepad: Callable[[], None]) -> Handle:
    """Start the dialog on its own thread. cameras: each camera type's top speeds. The callbacks run on the dialog's
    thread, so on_restart must hand over to the tray's thread (HiddenWindow.post)."""
    handle = Handle()
    handle.thread = threading.Thread(target=_run, name="settings-dialog", daemon=True,
                                     args=(handle, path, cameras, controllers, type_error, on_restart, on_notepad))
    handle.thread.start()
    return handle


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
    except Exception:
        log.exception("Settings dialog failed")
