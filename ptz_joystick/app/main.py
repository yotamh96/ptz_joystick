"""Composition root: the only place that builds hardware objects, picked from the tables in registry.py.
Reads the settings, runs the startup checks, then hands over to the loop. --tray hands over to tray.py instead.
A Problem or a crash ends here, in both modes: logged, shown where the operator looks, exit 1."""
import argparse
import logging
from pathlib import Path

from .. import config
from ..core.problem import Problem, crashed
from ..core.sender import CommandSender
from ..windows import single_instance
from ..windows.console import on_console_close, owns_console
from ..windows.message_box import message_box
from . import updates
from .checks import check_axes, check_camera
from .logs import setup_logging
from .loop import run, stop_camera
from .registry import CAMERAS, CONTROLLERS
from .startup import bootstrap_log, prepare
from .tray import run_tray
from .version import VERSION

log = logging.getLogger(__name__)
RUN_AGAIN = "run ptz_joystick again"    # the restart step, after a problem that stopped ptz_joystick


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ptz_joystick", description="Drive a PTZOptics camera with a game controller.")
    parser.add_argument("--config", type=Path, default=config.default_path(),
                        help=f"settings file (default: {config.default_path()})")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--keyboard", action="store_true", help="same as controller = \"keyboard\" in the settings file")
    parser.add_argument("--tray", action="store_true", help="run as an icon in the notification area, not in a console")
    args = parser.parse_args(argv)
    setup_logging(config.Settings(log_file=str(bootstrap_log(args.config))))     # until the settings are read
    try:
        if not single_instance.claim():
            raise Problem("Another ptz_joystick is already running", fix="Quit it first: its tray icon or console window")
        if args.tray:
            run_tray(args.config, args.keyboard)
        else:
            _console(args.config, args.keyboard)
    except Problem as p:
        log.error(p.log_line(then=RUN_AGAIN))
        _show(p, args.tray)
    except Exception as e:
        crash = crashed(e)
        log.critical(crash.log_line(then=RUN_AGAIN), exc_info=True)
        _show(crash, args.tray)


def _show(p: Problem, tray: bool):
    """Where the operator reads p, after its log line. Then exit 1."""
    if tray:                                # no console: a message box
        message_box(p.text(then=RUN_AGAIN))
    elif owns_console():                    # double-clicked: the window would close before anyone reads it
        try:
            input("Press Enter to close.")
        except EOFError:                    # no keyboard to wait for
            pass
    raise SystemExit(1)


def _console(path: Path, keyboard: bool):
    s = prepare(path, keyboard)
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
