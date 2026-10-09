"""Tray mode (--tray): the hidden window, the icon and its menu, and one session at a time. The composition root for
the tray, as main.py is for the console. Windows only."""
import logging
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from ..config import Settings
from ..windows import autostart
from ..windows.console import on_console_close
from ..windows.tray import dots, menu
from ..windows.tray.icon import NIIF_ERROR, NIIF_INFO, NIIF_WARNING, TrayIcon, fit
from ..windows.tray.window import WM_APP_TRAY, HiddenWindow
from .logs import setup_logging
from .session import run_session
from .status import GREEN, RED, YELLOW, Popup, Status
from .version import VERSION

log = logging.getLogger(__name__)

JOIN_SECONDS = 4.0              # a session ends by stopping the camera; the sender gives up on that after 3 s
CLICKS = (0x0202, 0x0205)       # WM_LBUTTONUP, WM_RBUTTONUP: either button opens the menu
KINDS = {"info": NIIF_INFO, "warning": NIIF_WARNING, "error": NIIF_ERROR}
Event = Callable[[Status], Popup | None]


def run_tray(path: Path, keyboard: bool):
    """Until Quit. Logs to the default log file from the start, so even a missing password gets logged."""
    setup_logging(Settings(log_file=str(bootstrap_log(path))))
    log.info("ptz_joystick %s (tray)", VERSION)
    app = TrayApp(path, keyboard)
    if sys.stderr:                  # started from a terminal (--tray while developing): closing it is a Quit
        on_console_close(app.shutdown)
    app.start_session()
    app.run()


def bootstrap_log(path: Path) -> Path:
    """The log file until the settings are read: the default one, next to the settings file."""
    return path.parent / Settings().log_file


def open_in_notepad(path: str):
    subprocess.Popen(["notepad.exe", path])     # a list, so a path with spaces stays one argument


class TrayApp:
    """Lives on the main thread, which runs the window's message loop."""

    def __init__(self, path: Path, keyboard: bool):
        self._path, self._keyboard = path, keyboard
        self._status = Status(str(bootstrap_log(path)))
        self._window = HiddenWindow(on_tray=self._clicked, on_end_session=self.shutdown,
                                    on_taskbar_created=self._taskbar_created, on_close=self.quit)
        self._icon = TrayIcon(self._window.hwnd, WM_APP_TRAY, later=self._later)
        self._dots = {color: dots.dot_icon(color) for color in (GREEN, YELLOW, RED)}
        self._session = 0                   # the current session's number: older sessions' news is dropped
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._show()

    def run(self):
        self._window.run()

    def start_session(self):
        self._session += 1
        self._stop = threading.Event()
        self._status.starting()
        self._show()
        self._thread = threading.Thread(target=run_session, name=f"session-{self._session}", daemon=True,
                                        args=(self._path, self._keyboard, self._stop, _Report(self, self._session)),
                                        kwargs={"check_updates": self._session == 1})
        self._thread.start()

    def restart(self):
        self._stop_session()
        self.start_session()

    def shutdown(self):
        """Stop the camera and remove the icon: Quit, logoff, shutdown, a closed terminal."""
        self._stop_session()
        self._icon.remove()

    def quit(self):
        self.shutdown()
        self._window.quit()

    def apply(self, session: int | None, event: Event):
        """Run event on the window's thread. session: the session it came from, so a stopped session's late news
        is dropped. None: from no session in particular (the update notice)."""
        def on_window_thread():
            if session is not None and session != self._session:
                return
            popup = event(self._status)
            self._show()
            if popup:
                self._icon.popup("ptz_joystick", popup.text, KINDS[popup.kind])

        self._window.post(on_window_thread)

    def _stop_session(self):
        self._stop.set()
        if self._thread:
            self._thread.join(JOIN_SECONDS)

    def _show(self):
        self._icon.set(self._dots[self._status.color], self._status.tooltip)

    def _later(self, seconds: float, fn: Callable[[], None]):
        timer = threading.Timer(seconds, self._window.post, args=(fn,))
        timer.daemon = True
        timer.start()

    def _taskbar_created(self):
        self._icon.taskbar_created()

    def _clicked(self, event: int):
        if event in CLICKS:
            picked = menu.show(self._window.hwnd, self._entries())
            if picked and picked.action:
                picked.action()

    def _entries(self) -> list[menu.Entry]:
        log_file = self._status.log_file
        entries: list[menu.Entry] = [
            menu.Item(fit(self._status.text, 128)),
            None,
            menu.Item("Open settings", lambda: open_in_notepad(str(self._path))),
            menu.Item("Open log", lambda: open_in_notepad(log_file), enabled=bool(log_file)),
            menu.Item("Restart", self.restart),
        ]
        if getattr(sys, "frozen", False):       # the exe: a source run has no one command for the Run key
            command = autostart.command_for(sys.executable)
            on = autostart.enabled(command)

            def toggle():
                if on:
                    autostart.disable()
                else:
                    autostart.enable(command)

            entries.append(menu.Item("Start with Windows", toggle, checked=on))
        entries += [None, menu.Item("Quit", self.quit)]
        return entries


class _Report:
    """A session's view of the tray. Each call goes to the window's thread, tagged with the session's number."""

    def __init__(self, app: TrayApp, session: int):
        self._app, self._session = app, session

    def _send(self, event: Event):
        self._app.apply(self._session, event)

    def log_to(self, log_file: str) -> None:
        self._send(lambda s: s.log_to(log_file))

    def waiting_for_camera(self, host: str, why: str) -> None:
        self._send(lambda s: s.waiting_for_camera(host, why))

    def waiting_for_stick(self) -> None:
        self._send(lambda s: s.waiting_for_stick())

    def stick_prompt(self) -> None:
        self._send(lambda s: s.stick_prompt())

    def no_controller(self, message: str) -> None:
        self._send(lambda s: s.no_controller(message))

    def driving(self, host: str) -> None:
        self._send(lambda s: s.driving(host))

    def controller(self, ok: bool) -> None:
        self._send(lambda s: s.controller(ok))

    def camera(self, ok: bool, why: str) -> None:
        self._send(lambda s: s.camera(ok, why))

    def stopped(self, message: str) -> None:
        self._send(lambda s: s.stopped(message))

    def update(self, tag: str, url: str) -> None:
        self._app.apply(None, lambda s: s.update(tag))      # from no session in particular: a Restart mustn't lose it
