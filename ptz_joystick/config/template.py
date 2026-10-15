"""The settings file: its name, where it lives, the commented template a first run writes, and writing it back."""
import json
import os
import re
import sys
from pathlib import Path

from ..core.problem import Problem
from .loading import command_text
from .settings import Settings

FILE_NAME = "ptz_joystick.toml"

HEADER = """\
# ptz_joystick settings. Easiest: tray menu → Settings…, which rewrites this file (comments you add are lost).
# Or edit here, save, then restart ptz_joystick (tray: right-click → Restart).
# The camera password is not here: set it with  setx PTZ_PASSWORD "..."

"""
# Every setting but the buttons, in file order. render() puts in the values and keeps each comment where it is.
LAYOUT = """\
camera = "ptzoptics"            # camera type: ptzoptics
host = "http://192.168.77.3"    # camera address
user = "admin"                  # camera user
timeout = 1.0                   # seconds to wait for each camera request (max 2)

controller = "winmm"            # winmm (any controller joy.cpl shows) or keyboard
pan_axis = "X"                  # which controller axis does what: X Y Z R U V
tilt_axis = "Y"                 #   (debug = true shows which letter moves)
zoom_axis = "R"
invert_tilt = true              # flip if up/down feels backwards
invert_zoom = true
deadzone = 0.15                 # stick readings at or below this are ignored
full_speed_at = 0.7             # stick reading that gives top speed (max 1.0)

pan_max = 24                    # camera's top speeds (PTZOptics max 24 / 20 / 7)
tilt_max = 20
zoom_max = 7

save_hold_seconds = 2.0         # tap a preset button = go there; hold it this long = save the current
                                #   view there; 0 = saving off (and presets fire on press)
debug = false                   # true logs every stick reading and every command sent
log_file = "ptz_joystick.log"   # next to this file unless a full path; "" = terminal only
check_updates = true            # at startup, log a line if a newer release is on GitHub
"""
BUTTONS = '[buttons]                       # button index (0 = "button 1" in joy.cpl) = command\n'
SETTING_LINE = re.compile(r'^(\w+) = ("[^"]*"|\S+) *(#.*)?$', re.MULTILINE)       # name = value   # comment
COMMENT_COLUMN = 32


def toml_value(v: object) -> str:
    """v as TOML writes it. json.dumps escapes backslash, quote and control characters as TOML does, except DEL."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False).replace("\x7f", "\\u007f")
    return repr(v)


def render(s: Settings) -> str:
    """The settings file for s: the template's lines and comments with s's values. Never the password."""
    def line(m: re.Match[str]) -> str:
        text = f"{m[1]} = {toml_value(getattr(s, m[1]))}"
        return f"{text:<{COMMENT_COLUMN - 1}} {m[3]}" if m[3] else text

    rows = "".join(f"{b} = {toml_value(command_text(c))}\n" for b, c in sorted(s.buttons.items()))
    return HEADER + SETTING_LINE.sub(line, LAYOUT) + "\n" + BUTTONS + rows


TEMPLATE = render(Settings())


def default_path() -> Path:
    """Next to the exe when frozen by PyInstaller, else in the repo folder (next to README.md)."""
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    return base / FILE_NAME


def write_template_if_missing(path: Path) -> bool:
    if path.exists():
        return False
    try:
        path.write_text(TEMPLATE, encoding="utf-8")
    except OSError as e:
        raise Problem(f"Can't create {path.name}", fix="Move the exe to a folder you can write to",
                      detail=str(e)) from None
    return True


def save(path: Path, s: Settings):
    """Write s to path as render() lays it out. Through a temp file, so a failed write never leaves half a file."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(render(s), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as e:
        raise Problem(f"Can't save {path.name}", fix="Check that you can write to its folder",
                      detail=str(e)) from None
