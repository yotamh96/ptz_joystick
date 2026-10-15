"""The control loop: read the controller, send what changed, and always leave the camera stopped."""
import logging
import threading
from collections.abc import Callable

from ..config import Settings
from ..controllers import Controller
from ..core.commands import PanTilt, SavePreset, Tracking, Zoom
from ..core.mapping import Mapper
from ..core.problem import Problem
from ..core.sender import CommandSender

log = logging.getLogger(__name__)

# The same words in the log, the tray's status text and its pop-up (app/status.py).
CONTROLLER_UNPLUGGED = Problem("The controller is unplugged and the camera stopped", fix="Plug it back in")


def run(s: Settings, controller: Controller, sender: CommandSender, period=0.05,
        stop: threading.Event | None = None, on_controller: Callable[[bool], None] | None = None):
    """Drive the camera until stop is set (or Ctrl+C). on_controller(False) when the controller is lost,
    on_controller(True) when it's back."""
    stop = stop or threading.Event()
    mapper = Mapper(s)
    lost = False
    try:
        while not stop.is_set():
            state = controller.read()
            if (state is None) != lost:
                lost = state is None
                if lost:
                    log.warning(CONTROLLER_UNPLUGGED.log_line())
                else:
                    log.info("The controller is back")
                if on_controller:
                    on_controller(not lost)
            if s.debug and state:
                log.debug("%s buttons=%#06x", {a: round(v, 2) for a, v in state.axes.items()}, state.buttons)
            for cmd in mapper.update(state):
                if isinstance(cmd, SavePreset):
                    log.info("Saving the current position as preset %d.", cmd.number)
                elif isinstance(cmd, Tracking):
                    log.info("Auto-tracking %s.", "on" if cmd.on else "off")
                sender.send(cmd)
            stop.wait(period)
    finally:                            # never leave the camera moving
        stop_camera(sender)


def stop_camera(sender: CommandSender):
    if sender.drain_with([PanTilt(0, 0), Zoom(0)]):
        log.info("Camera stopped.")
    else:
        log.error("Camera did not confirm stop.")
