"""Every setting in one place. Defaults live here; ptz_joystick.toml overrides them."""
import os
import sys
import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

from .commands import Command, Preset

AXES = "XYZRUV"
FILE_NAME = "ptz_joystick.toml"
COMMANDS = {"preset": Preset}           # name used in the settings file -> command class


@dataclass(frozen=True)
class Settings:
    host: str = "http://192.168.77.3"
    user: str = "admin"
    password: str = ""                  # filled from PTZ_PASSWORD by load(), never from the file
    timeout: float = 1.0                # seconds per camera request

    pan_axis: str = "X"                 # X Y Z R U V  (debug=True shows which one moves)
    tilt_axis: str = "Y"
    zoom_axis: str = "R"
    invert_tilt: bool = True            # stick up usually reads low
    invert_zoom: bool = True            # stick up = zoom in
    deadzone: float = 0.15
    full_speed_at: float = 0.7          # stick reading that means top speed (this pad tops out ~0.75, not 1.0)

    pan_max: int = 24                   # camera speed ranges
    tilt_max: int = 20
    zoom_max: int = 7

    buttons: dict = field(default_factory=lambda: {   # button index -> command
        0: Preset(1), 1: Preset(2), 2: Preset(3), 3: Preset(4)})
    debug: bool = False                 # True = log axis values and buttons (DEBUG level)
    log_file: str = "ptz_joystick.log"  # relative = next to the settings file; "" = terminal only
    check_updates: bool = True          # look for a newer release on GitHub at startup (notice only)

    def __post_init__(self):
        """Catch bad values at startup, not on the first stick push."""
        def check(ok, msg):
            if not ok:
                raise ValueError(msg)

        check(0 <= self.deadzone < self.full_speed_at <= 1,
              f"need 0 <= deadzone < full_speed_at <= 1, got deadzone={self.deadzone} full_speed_at={self.full_speed_at}")
        for name in ("pan_axis", "tilt_axis", "zoom_axis"):
            v = getattr(self, name)
            check(isinstance(v, str) and len(v) == 1 and v in AXES, f"{name} must be one of {' '.join(AXES)}, got {v!r}")
        for name in ("pan_max", "tilt_max", "zoom_max"):
            v = getattr(self, name)
            check(isinstance(v, int) and v >= 1, f"{name} must be a whole number >= 1, got {v!r}")
        check(self.timeout > 0, f"timeout must be > 0 seconds, got {self.timeout!r}")
        check(self.host.startswith(("http://", "https://")), f"host must start with http://, got {self.host!r}")
        bad = {b: c for b, c in self.buttons.items() if not (isinstance(b, int) and 0 <= b < 32 and isinstance(c, Command))}
        check(not bad, f"buttons must map a button index 0-31 to a command, bad: {bad}")


TEMPLATE = """\
# ptz_joystick settings. Edit, save, restart ptz_joystick.
# The camera password is not here: set it with  setx PTZ_PASSWORD "..."

host = "http://192.168.77.3"    # camera address
user = "admin"                  # camera user
timeout = 1.0                   # seconds to wait for each camera request

pan_axis = "X"                  # which controller axis does what: X Y Z R U V
tilt_axis = "Y"                 #   (debug = true shows which letter moves)
zoom_axis = "R"
invert_tilt = true              # flip if up/down feels backwards
invert_zoom = true
deadzone = 0.15                 # stick readings at or below this are ignored
full_speed_at = 0.7             # stick reading that gives top speed (max 1.0)

pan_max = 24                    # camera's top speeds
tilt_max = 20
zoom_max = 7

debug = false                   # true logs every stick reading and every command sent
log_file = "ptz_joystick.log"   # next to this file unless a full path; "" = terminal only
check_updates = true            # at startup, log a line if a newer release is on GitHub

[buttons]                       # button index (0 = "button 1" in joy.cpl) = command
0 = "preset 1"
1 = "preset 2"
2 = "preset 3"
3 = "preset 4"
"""


def default_path() -> Path:
    """Next to the exe when frozen by PyInstaller, else inside the package folder."""
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    return base / FILE_NAME


def write_template_if_missing(path: Path) -> bool:
    if path.exists():
        return False
    try:
        path.write_text(TEMPLATE, encoding="utf-8")
    except OSError as e:
        raise SystemExit(f"Can't create settings file {path}: {e}") from None
    return True


def parse_command(text) -> Command:
    """'preset 1' -> Preset(1)."""
    words = text.split() if isinstance(text, str) else []
    cls = COMMANDS.get(words[0].lower()) if words else None
    try:
        return cls(*map(int, words[1:]))
    except (TypeError, ValueError):
        raise ValueError(f"bad command {text!r}, use one of: {', '.join(f'{n} N' for n in COMMANDS)}") from None


def parse_buttons(table: dict) -> dict:
    if bad := [b for b in table if not b.isdigit()]:
        raise ValueError(f"buttons: index must be a number 0-31, got {bad}")
    try:
        return {int(b): parse_command(c) for b, c in table.items()}
    except ValueError as e:
        raise ValueError(f"buttons: {e}") from None


TYPE_NAMES = {str: "text in quotes", int: "a whole number", float: "a number", bool: "true or false", dict: "a [table]"}


def from_dict(d: dict, password: str) -> Settings:
    known = {f.name: f.type for f in fields(Settings) if f.name != "password"}
    values = {"password": password}
    for key, v in d.items():
        if key == "password":
            raise ValueError('password must not be in the settings file, use:  setx PTZ_PASSWORD "..."')
        if key not in known:
            raise ValueError(f"unknown setting {key!r}")
        want = known[key]
        types = (int, float) if want is float else want     # 1 is fine where 1.0 is expected
        if isinstance(v, bool) != (want is bool) or not isinstance(v, types):
            raise ValueError(f"{key} must be {TYPE_NAMES[want]}, got {v!r}")
        values[key] = parse_buttons(v) if key == "buttons" else v
    return Settings(**values)


def load(path: Path) -> Settings:
    password = os.environ.get("PTZ_PASSWORD")
    if not password:
        raise SystemExit('Set the camera password first:  setx PTZ_PASSWORD "..."  then open a new terminal.')
    try:
        with open(path, "rb") as f:
            s = from_dict(tomllib.load(f), password)
        # A relative log file sits next to the settings file (and so the exe), whatever folder you run from.
        return replace(s, log_file=str(path.parent / s.log_file)) if s.log_file else s
    except (tomllib.TOMLDecodeError, ValueError) as e:
        raise SystemExit(f"{path}: {e}") from None
    except OSError as e:
        raise SystemExit(f"Can't read settings file {path}: {e}") from None
