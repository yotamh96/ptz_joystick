"""Composition root: the only place that builds hardware objects, picked from the tables in adapters.py."""
import argparse
import logging
import time
from dataclasses import replace
from pathlib import Path

from .. import config
from ..cameras import Camera
from ..config import Settings
from ..controllers import Controller
from ..core.commands import PanTilt, SavePreset, Tracking, Zoom
from ..core.mapping import Mapper
from ..core.sender import CommandSender
from . import updates
from .adapters import CAMERAS, CONTROLLERS
from .version import VERSION
from .winconsole import on_console_close

log = logging.getLogger(__name__)


def setup_logging(s: Settings):
    """Terminal always; plus s.log_file if set. debug=True adds per-command and per-reading lines."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    file_error: OSError | None = None
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


def check_types(s: Settings, settings_path: Path):
    """camera and controller name known types, and the speeds fit that camera. Before anything connects."""
    for name, table in (("camera", CAMERAS), ("controller", CONTROLLERS)):
        if getattr(s, name) not in table:
            raise SystemExit(f"{settings_path}: {name} must be one of {', '.join(table)}, got {getattr(s, name)!r}")
    for name, top in CAMERAS[s.camera].top_speeds.items():
        if getattr(s, name) > top:
            raise SystemExit(f"{settings_path}: {name} can be at most {top} for camera {s.camera!r}, "
                             f"got {getattr(s, name)}")


def stop_camera(sender: CommandSender):
    if sender.drain_with([PanTilt(0, 0), Zoom(0)]):
        log.info("Camera stopped.")
    else:
        log.error("Camera did not confirm stop.")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ptz_joystick", description="Drive a PTZOptics camera with a game controller.")
    parser.add_argument("--config", type=Path, default=config.default_path(),
                        help=f"settings file (default: {config.default_path()})")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--keyboard", action="store_true", help="same as controller = \"keyboard\" in the settings file")
    args = parser.parse_args(argv)
    path = args.config
    created = config.write_template_if_missing(path)
    s = config.load(path)
    if args.keyboard:
        s = replace(s, controller="keyboard")
    check_types(s, path)
    setup_logging(s)
    log.info("ptz_joystick %s", VERSION)
    if s.check_updates:
        updates.check_in_background(VERSION)
    if created:
        log.info("Wrote default settings to %s. Edit it and restart to change them.", path)
    log.info("Settings: %s (camera %s, controller %s)", path, s.camera, s.controller)
    camera = CAMERAS[s.camera].connect(s)
    check_camera(camera, s.host, path)
    controller = CONTROLLERS[s.controller](s)
    if state := controller.read():
        missing = [a for a in (s.pan_axis, s.tilt_axis, s.zoom_axis) if a not in state.axes]
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
                if isinstance(cmd, SavePreset):
                    log.info("Saving the current position as preset %d.", cmd.number)
                elif isinstance(cmd, Tracking):
                    log.info("Auto-tracking %s.", "on" if cmd.on else "off")
                sender.send(cmd)
            time.sleep(period)
    finally:                            # never leave the camera moving
        stop_camera(sender)
