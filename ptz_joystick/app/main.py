"""Composition root: the only place that builds hardware objects, picked from the tables in registry.py.
Reads the settings, runs the startup checks, then hands over to the loop."""
import argparse
import logging
from dataclasses import replace
from pathlib import Path

from .. import config
from ..core.sender import CommandSender
from ..windows.console import on_console_close
from . import updates
from .checks import check_axes, check_camera, check_types
from .logs import setup_logging
from .loop import run, stop_camera
from .registry import CAMERAS, CONTROLLERS
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
    check_axes(controller, s, path)
    sender = CommandSender(camera)

    def console_closing():
        log.info("Console closing.")
        stop_camera(sender)

    on_console_close(console_closing)
    log.info("Driving camera %s. Ctrl+C to quit.", s.host)
    run(s, controller, sender)
