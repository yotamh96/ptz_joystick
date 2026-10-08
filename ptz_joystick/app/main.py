"""Composition root: the only place that builds hardware objects, picked from the tables in registry.py.
Reads the settings, runs the startup checks, then hands over to the loop."""
import argparse
import logging
from pathlib import Path

from .. import config
from ..core.sender import CommandSender
from ..windows.console import on_console_close
from . import updates
from .checks import check_axes, check_camera
from .loop import run, stop_camera
from .registry import CAMERAS, CONTROLLERS
from .startup import prepare
from .version import VERSION

log = logging.getLogger(__name__)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ptz_joystick", description="Drive a PTZOptics camera with a game controller.")
    parser.add_argument("--config", type=Path, default=config.default_path(),
                        help=f"settings file (default: {config.default_path()})")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--keyboard", action="store_true", help="same as controller = \"keyboard\" in the settings file")
    args = parser.parse_args(argv)
    path = args.config
    s = prepare(path, args.keyboard)
    if s.check_updates:
        updates.check_in_background(VERSION)
    camera = CAMERAS[s.camera].connect(s)
    check_camera(camera, s.host, path)
    controller = CONTROLLERS[s.controller](s)
    check_axes(controller, s, path)
    sender = CommandSender(camera)

    def console_closing():
        log.info("Console closing.")
        stop_camera(sender)

    on_console_close(console_closing)
    log.info("Driving camera %s. Ctrl+C to quit.", s.host)
    run(s, controller, sender)
