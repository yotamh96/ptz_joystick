"""The settings dialog's window: the tabs, Save / Cancel / Open in Notepad, and what Save does. Every call on the
dialog's thread (__init__.py)."""
import logging
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk

from ... import config
from ...config import Settings
from ...core.problem import Problem
from ..user_env import set_user_env
from . import form
from .tabs import Tabs

log = logging.getLogger(__name__)

TITLE = "ptz_joystick settings"
RESTART_QUESTION = "Settings saved. Restart now to use them?"
WATCH_MS = 100                  # how often the window checks whether the tray asked it to close


def write(path: Path, s: Settings, old_password: str):
    """Save the settings file, then the password if it changed. Raises Problem."""
    config.save(path, s)
    if s.password != old_password:
        try:
            set_user_env("PTZ_PASSWORD", s.password)
        except OSError as e:
            raise Problem("Can't save the camera password", fix='Run setx PTZ_PASSWORD "..." in a terminal',
                          detail=str(e)) from None


class SettingsWindow:
    """Fills root. settings: as the file has them, with the current password. write(s) saves; on_restart and
    on_notepad go back to the tray."""

    def __init__(self, root: tk.Tk, path: Path, settings: Settings, cameras: dict[str, dict[str, int]],
                 controllers: list[str], type_error: Callable[[Settings], str | None],
                 write: Callable[[Settings], None], on_restart: Callable[[], None], on_notepad: Callable[[], None]):
        self.root, self._path, self._old = root, path, settings
        self._type_error, self._write, self._on_restart, self._on_notepad = type_error, write, on_restart, on_notepad
        self.closed = False
        root.title(TITLE)
        root.resizable(False, False)
        root.report_callback_exception = self._failed      # the windowed exe has no stderr to print to
        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)
        self.tabs = Tabs(frame, form.to_fields(settings), path, cameras, controllers)
        self.tabs.notebook.pack(fill="both", expand=True)
        bar = ttk.Frame(frame, padding=(0, 10, 0, 0))
        bar.pack(fill="x")
        ttk.Button(bar, text="Open in Notepad", command=self.notepad).pack(side="left")
        ttk.Button(bar, text="Cancel", command=self.close).pack(side="right")
        ttk.Button(bar, text="Save", command=self.save, default="active").pack(side="right", padx=(0, 8))
        root.bind("<Return>", lambda _: self.save())
        root.bind("<Escape>", lambda _: self.close())
        root.protocol("WM_DELETE_WINDOW", self.close)

    def save(self):
        """Check every field; the first bad one is marked and the dialog stays. Then write, ask, close."""
        self.tabs.clear_error()
        try:
            s = form.from_fields(self.tabs.values(), self._type_error)
        except form.FieldError as e:
            self.tabs.show_error(e)
            return
        if s == self._old:
            self.close()
            return
        try:
            self._write(s)
        except Problem as p:
            messagebox.showerror(TITLE, p.log_line(), parent=self.root)
            return
        log.info("Settings saved to %s", self._path)
        restart = messagebox.askyesno(TITLE, RESTART_QUESTION, parent=self.root)
        self.close()
        if restart:
            self._on_restart()

    def notepad(self):
        """Close without saving, then open the file: one editor at a time, so neither overwrites the other."""
        self.close()
        self._on_notepad()

    def close(self):
        if not self.closed:
            self.closed = True
            self.root.destroy()

    def watch(self, closing: threading.Event):
        """Close when the tray asks (Quit, logoff). Checked every WATCH_MS: only this thread may touch Tk."""
        if closing.is_set():
            self.close()
        elif not self.closed:
            self.root.after(WATCH_MS, self.watch, closing)

    def _failed(self, kind, value, tb):
        log.error("Settings dialog: unexpected error", exc_info=(kind, value, tb))
