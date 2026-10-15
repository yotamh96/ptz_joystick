"""Every setting in one place: settings.py (defaults, validation), template.py (the file, where it lives, writing
it), loading.py (reading it). Import from here: config.load, config.Settings, ..."""
from .loading import bad_setting, command_text, from_dict, load, parse_command, read
from .settings import AXES, BUTTON_COMMANDS, MAX_TIMEOUT, Settings, takes_number
from .template import (
    FILE_NAME,
    TEMPLATE,
    default_path,
    render,
    save,
    write_template_if_missing,
)

__all__ = ["AXES", "BUTTON_COMMANDS", "FILE_NAME", "MAX_TIMEOUT", "TEMPLATE", "Settings", "bad_setting",
           "command_text", "default_path", "from_dict", "load", "parse_command", "read", "render", "save",
           "takes_number", "write_template_if_missing"]
