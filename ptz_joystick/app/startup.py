"""Startup steps the console and the tray share: the password, the settings file, the settings and their checks,
logging, and the first log lines."""
import logging
import os
from dataclasses import replace
from pathlib import Path

from .. import config
from ..config import Settings
from ..windows.user_env import user_env
from .checks import check_types
from .logs import setup_logging
from .version import VERSION

log = logging.getLogger(__name__)


def bootstrap_log(path: Path) -> Path:
    """The log file until the settings are read: the default one, next to the settings file."""
    return path.parent / Settings().log_file


def prepare(path: Path, keyboard: bool) -> Settings:
    """The settings from path (written from the template on a first run), checked, with logging set up from them.
    keyboard: the --keyboard flag. Raises Problem naming the fix when PTZ_PASSWORD or a setting is wrong."""
    if password := user_env("PTZ_PASSWORD"):        # the newest setx, even in a terminal opened before it
        os.environ["PTZ_PASSWORD"] = password
    created = config.write_template_if_missing(path)
    s = config.load(path)
    if keyboard:
        s = replace(s, controller="keyboard")
    check_types(s, path)
    setup_logging(s)
    log.info("ptz_joystick %s", VERSION)
    if created:
        log.info("Wrote default settings to %s. Edit it and restart to change them.", path)
    log.info("Settings: %s (camera %s, controller %s)", path, s.camera, s.controller)
    return s
