"""Composition root: the only place that builds hardware objects, picked from the tables in registry.py.
Reads the settings, runs the startup checks, then hands over to the loop. --tray hands over to tray.py instead."""
import argparse
import logging
from pathlib import Path

from .. import config
from ..core.sender import CommandSender
from ..windows import single_instance
from ..windows.console import on_console_close
from ..windows.message_box import message_box
from . import updates
from .checks import check_axes, check_camera
from .loop import run, stop_camera
from .registry import CAMERAS, CONTROLLERS
from .startup import prepare
from .tray import run_tray
from .version import VERSION

log = logging.getLogger(__name__)
ALREADY_RUNNING = "ptz_joystick is already running. Quit it first: tray icon or its console window."


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ptz_joystick", description="Drive a PTZOptics camera with a game controller.")
    parser.add_argument("--config", type=Path, default=config.default_path(),
                        help=f"settings file (default: {config.default_path()})")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--keyboard", action="store_true", help="same as controller = \"keyboard\" in the settings file")
    parser.add_argument("--tray", action="store_true", help="run as an icon in the notification area, not in a console")
    args = parser.parse_args(argv)
    if not single_instance.claim():
        if args.tray:                       # no console to show the message
            message_box(ALREADY_RUNNING)
        raise SystemExit(ALREADY_RUNNING)
    if args.tray:
        run_tray(args.config, args.keyboard)
        return
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
