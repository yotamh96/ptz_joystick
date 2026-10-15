"""One session of the tray app, on its own thread: the startup steps, then the control loop. Restart = stop this
session and start a new one. Never raises: errors go to the log and to report.stopped()."""
import logging
import threading
from pathlib import Path
from typing import Protocol

from ..config import Settings
from ..controllers import Controller
from ..core.commands import PanTilt
from ..core.problem import Problem, crashed
from ..core.sender import CommandSender
from . import updates
from .checks import check_axes
from .loop import run
from .registry import CAMERAS, CONTROLLERS
from .startup import prepare
from .status import CLICK_RESTART
from .version import VERSION

log = logging.getLogger(__name__)

STICK_PROMPT_AFTER = 1.0    # s. A missing controller raises at once, so it never gets a wrong "move the stick" pop-up


class Report(Protocol):
    """What a session tells the tray. Called from the session's threads."""

    def log_to(self, log_file: str) -> None:
        """The log file the settings name ("" = none): what Open log opens."""

    def waiting_for_camera(self, host: str, problem: Problem | None) -> None:
        """The camera didn't take the startup stop; problem = why (None if the camera didn't say)."""

    def waiting_for_stick(self) -> None:
        """About to ask the controller factory, which may wait for a stick move."""

    def stick_prompt(self) -> None:
        """Still waiting for the stick after STICK_PROMPT_AFTER seconds."""

    def no_controller(self, problem: Problem) -> None:
        """The factory found no device; problem says what to check. Trying again soon."""

    def driving(self, host: str) -> None:
        """Startup done: the control loop runs."""

    def controller(self, ok: bool) -> None:
        """While driving: the controller was unplugged (False) or is back (True)."""

    def camera(self, ok: bool, problem: Problem | None) -> None:
        """While driving: the camera stopped (False, problem = why) or started (True) taking commands."""

    def stopped(self, problem: Problem) -> None:
        """The session ended; problem names the fix. The tray adds its restart step."""

    def update(self, tag: str, url: str) -> None:
        """A newer release is on GitHub."""


def run_session(path: Path, keyboard: bool, stop: threading.Event, report: Report, check_updates: bool = False,
                retry_every: float = 5.0):
    """Startup steps, then drive the camera until stop is set. check_updates: ask GitHub (the first session)."""
    try:
        _session(path, keyboard, stop, report, check_updates, retry_every)
    except Problem as p:                            # the startup checks' problems name the fix
        log.error(p.log_line(then=CLICK_RESTART))
        report.stopped(p)
    except Exception as e:
        crash = crashed(e)
        log.critical(crash.log_line(then=CLICK_RESTART), exc_info=True)
        report.stopped(crash)


def _session(path: Path, keyboard: bool, stop: threading.Event, report: Report, check_updates: bool,
             retry_every: float):
    s = prepare(path, keyboard)
    report.log_to(s.log_file)
    if check_updates and s.check_updates:
        updates.check_in_background(VERSION, on_found=report.update)
    camera = CAMERAS[s.camera].connect(s)
    while not camera.send(PanTilt(0, 0)):           # the startup check, retried: the camera may boot after the PC
        report.waiting_for_camera(s.host, camera.problem)
        if stop.wait(retry_every):
            return
    controller = _wait_for_controller(s, stop, report, retry_every)
    if controller is None:
        return
    check_axes(controller, s, path)
    sender = CommandSender(camera, on_camera=lambda ok: report.camera(ok, camera.problem))
    report.driving(s.host)
    log.info("Driving the camera at %s", s.host)
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
        except Problem as p:                                # the Controller contract's "no device"
            report.no_controller(p)
            stop.wait(retry_every)
            continue
        finally:
            prompt.cancel()
        return None if stop.is_set() else controller        # stopped while waiting: don't drive
    return None
