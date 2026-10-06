"""Composition root: the only place that builds hardware objects. Swap an adapter here."""
import logging
import time

from . import config
from .cameras.ptzoptics import PtzOpticsCamera
from .commands import PanTilt, Zoom
from .config import Settings
from .controllers import Controller
from .controllers.winmm import discover
from .mapping import Mapper
from .sender import CommandSender

log = logging.getLogger(__name__)


def setup_logging(s: Settings):
    """Terminal always; plus s.log_file if set. debug=True adds per-command and per-reading lines."""
    handlers = [logging.StreamHandler()]
    if s.log_file:
        handlers.append(logging.FileHandler(s.log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.DEBUG if s.debug else logging.INFO, handlers=handlers, force=True,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("urllib3").setLevel(logging.WARNING)   # requests' own chatter at DEBUG


def main():
    s = config.load()
    setup_logging(s)
    controller = discover()
    state = controller.read()
    missing = [a for a in (s.pan_axis, s.tilt_axis, s.zoom_axis) if state and a not in state.axes]
    if missing:
        raise SystemExit(f"Controller has no axis {missing} (has {list(state.axes)}). Fix the axes in config.py.")
    log.info("Driving camera %s. Ctrl+C to quit.", s.host)
    run(s, controller, CommandSender(PtzOpticsCamera(s.host, s.user, s.password, s.timeout)))


def run(s: Settings, controller: Controller, sender: CommandSender, period=0.05):
    mapper = Mapper(s)
    lost = False
    try:
        while True:
            state = controller.read()
            if (state is None) != lost:
                lost = state is None
                if lost:
                    log.warning("Controller lost, camera stopped. Waiting for it...")
                else:
                    log.info("Controller back.")
            if s.debug and state:
                log.debug("%s buttons=%#06x", {a: round(v, 2) for a, v in state.axes.items()}, state.buttons)
            for cmd in mapper.update(state):
                sender.send(cmd)
            time.sleep(period)
    finally:                            # never leave the camera moving
        if sender.drain_with([PanTilt(0, 0), Zoom(0)]):
            log.info("Camera stopped.")
        else:
            log.error("Camera did not confirm stop.")
