"""Composition root: the only place that builds hardware objects. Swap an adapter here."""
import argparse
import logging
import time
from pathlib import Path

from . import config
from .cameras import Camera
from .cameras.ptzoptics import PtzOpticsCamera
from .commands import PanTilt, Zoom
from .config import Settings
from .controllers import Controller
from .controllers.winmm import discover
from .mapping import Mapper
from .sender import CommandSender
from .winconsole import on_console_close

log = logging.getLogger(__name__)


def setup_logging(s: Settings):
    """Terminal always; plus s.log_file if set. debug=True adds per-command and per-reading lines."""
    handlers, file_error = [logging.StreamHandler()], None
    if s.log_file:
        try:
            handlers.append(logging.FileHandler(s.log_file, encoding="utf-8"))
        except OSError as e:            # locked by another program, read-only folder, ...
            file_error = e
    logging.basicConfig(level=logging.DEBUG if s.debug else logging.INFO, handlers=handlers, force=True,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("urllib3").setLevel(logging.WARNING)   # requests' own chatter at DEBUG
    if file_error:
        log.warning("Can't write log file %s (%s): terminal only.", s.log_file, file_error)


def check_camera(camera: Camera, host: str, settings_path: Path):
    """Send a harmless stop, so a wrong address or password fails now instead of mid-session."""
    if not camera.send(PanTilt(0, 0)):
        raise SystemExit(f"Camera at {host} did not accept a stop command (reason logged above). "
                         f"Check host in {settings_path}, the network, and PTZ_PASSWORD.")


def stop_camera(sender: CommandSender):
    if sender.drain_with([PanTilt(0, 0), Zoom(0)]):
        log.info("Camera stopped.")
    else:
        log.error("Camera did not confirm stop.")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ptz_joystick", description="Drive a PTZOptics camera with a game controller.")
    parser.add_argument("--config", type=Path, default=config.default_path(),
                        help=f"settings file (default: {config.default_path()})")
    path = parser.parse_args(argv).config
    created = config.write_template_if_missing(path)
    s = config.load(path)
    setup_logging(s)
    if created:
        log.info("Wrote default settings to %s. Edit it and restart to change them.", path)
    log.info("Settings: %s", path)
    camera = PtzOpticsCamera(s.host, s.user, s.password, s.timeout)
    check_camera(camera, s.host, path)
    controller = discover()
    state = controller.read()
    missing = [a for a in (s.pan_axis, s.tilt_axis, s.zoom_axis) if state and a not in state.axes]
    if missing:
        raise SystemExit(f"Controller has no axis {missing} (has {list(state.axes)}). Fix the axes in {path}.")
    sender = CommandSender(camera)

    def console_closing():
        log.info("Console closing.")
        stop_camera(sender)

    on_console_close(console_closing)
    log.info("Driving camera %s. Ctrl+C to quit.", s.host)
    run(s, controller, sender)


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
        stop_camera(sender)
