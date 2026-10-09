"""One session of the tray app, on its own thread: the startup steps, then the control loop. Restart = stop this
session and start a new one. Never raises: errors go to the log and to report.stopped()."""
import logging
import os
import threading
from pathlib import Path
from typing import Protocol

from ..config import Settings
from ..controllers import Controller
from ..core.commands import PanTilt
from ..core.sender import CommandSender
from ..windows.user_env import user_env
from . import updates
from .checks import check_axes
from .loop import run
from .registry import CAMERAS, CONTROLLERS
from .startup import prepare
from .version import VERSION

log = logging.getLogger(__name__)

KEYBOARD_IN_TRAY = "The keyboard controller only works in the console version (ptz_joystick.exe)."
STICK_PROMPT_AFTER = 1.0    # s. A missing controller raises at once, so it never gets a wrong "move the stick" pop-up


class Report(Protocol):
    """What a session tells the tray. Called from the session's threads."""

    def log_to(self, log_file: str) -> None:
        """The log file the settings name ("" = none): what Open log opens."""

    def waiting_for_camera(self, host: str, why: str) -> None:
        """The camera didn't take the startup stop; why = its newest warning ("" if none yet)."""

    def waiting_for_stick(self) -> None:
        """About to ask the controller factory, which may wait for a stick move."""

    def stick_prompt(self) -> None:
        """Still waiting for the stick after STICK_PROMPT_AFTER seconds."""

    def no_controller(self, message: str) -> None:
        """The factory found no device; message says what to check. Trying again soon."""

    def driving(self, host: str) -> None:
        """Startup done: the control loop runs."""

    def controller(self, ok: bool) -> None:
        """While driving: the controller was unplugged (False) or is back (True)."""

    def camera(self, ok: bool, why: str) -> None:
        """While driving: the camera stopped (False) or started (True) taking commands."""

    def stopped(self, message: str) -> None:
        """The session ended with an error; message names the fix."""

    def update(self, tag: str, url: str) -> None:
        """A newer release is on GitHub."""


class LastWarning(logging.Handler):
    """Keeps the newest WARNING logged under it: the camera adapter's reason, e.g. 'camera rejected the login
    (401): ...'."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.text = ""

    def emit(self, record):
        self.text = record.getMessage()


def run_session(path: Path, keyboard: bool, stop: threading.Event, report: Report, check_updates: bool = False,
                retry_every: float = 5.0):
    """Startup steps, then drive the camera until stop is set. check_updates: ask GitHub (the first session)."""
    camera_warning = LastWarning()                  # one per session: a new session starts with no reason
    cameras_log = logging.getLogger("ptz_joystick.cameras")
    cameras_log.addHandler(camera_warning)
    try:
        _session(path, keyboard, stop, report, check_updates, retry_every, camera_warning)
    except SystemExit as e:                         # the startup checks' messages name the fix
        log.error("%s", e)
        report.stopped(str(e))
    except Exception as e:
        log.critical("Crashed: %r", e, exc_info=True)
        report.stopped(f"Crashed: {e!r}. See the log.")
    finally:
        cameras_log.removeHandler(camera_warning)


def _session(path: Path, keyboard: bool, stop: threading.Event, report: Report, check_updates: bool,
             retry_every: float, camera_warning: LastWarning):
    if password := user_env("PTZ_PASSWORD"):        # the newest setx, without signing out
        os.environ["PTZ_PASSWORD"] = password
    s = prepare(path, keyboard)
    report.log_to(s.log_file)
    if check_updates and s.check_updates:
        updates.check_in_background(VERSION, on_found=report.update)
    if s.controller == "keyboard":
        raise SystemExit(KEYBOARD_IN_TRAY)
    camera = CAMERAS[s.camera].connect(s)
    while not camera.send(PanTilt(0, 0)):           # the startup check, retried: the camera may boot after the PC
        report.waiting_for_camera(s.host, camera_warning.text)
        if stop.wait(retry_every):
            return
    controller = _wait_for_controller(s, stop, report, retry_every)
    if controller is None:
        return
    check_axes(controller, s, path)
    sender = CommandSender(camera, on_camera=lambda ok: report.camera(ok, camera_warning.text))
    report.driving(s.host)
    log.info("Driving camera %s.", s.host)
    run(s, controller, sender, stop=stop, on_controller=report.controller)


def _wait_for_controller(s: Settings, stop: threading.Event, report: Report, retry_every: float) -> Controller | None:
    """The controller the settings name, once one is plugged in. None if stop was set meanwhile."""
    while not stop.is_set():
        report.waiting_for_stick()
        prompt = threading.Timer(STICK_PROMPT_AFTER, report.stick_prompt)
        prompt.daemon = True
        prompt.start()
        try:
            controller = CONTROLLERS[s.controller](s)       # may wait for a stick move, and can't be interrupted
        except SystemExit as e:                             # the Controller contract's "no device"
            report.no_controller(str(e))
            stop.wait(retry_every)
            continue
        finally:
            prompt.cancel()
        return None if stop.is_set() else controller        # stopped while waiting: don't drive
    return None
