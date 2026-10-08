"""Every setting in one place: settings.py (defaults, validation), template.py (the file and where it lives),
loading.py (reading it). Import from here: config.load, config.Settings, ..."""
from .loading import from_dict, load, parse_command
from .settings import AXES, BUTTON_COMMANDS, MAX_TIMEOUT, Settings
from .template import FILE_NAME, TEMPLATE, default_path, write_template_if_missing

__all__ = ["AXES", "BUTTON_COMMANDS", "FILE_NAME", "MAX_TIMEOUT", "TEMPLATE", "Settings", "default_path", "from_dict",
           "load", "parse_command", "write_template_if_missing"]
