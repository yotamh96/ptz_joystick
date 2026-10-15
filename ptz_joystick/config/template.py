"""The settings file: its name, where it lives, and the commented template a first run writes."""
import sys
from pathlib import Path

FILE_NAME = "ptz_joystick.toml"

TEMPLATE = """\
# ptz_joystick settings. Edit, save, then restart ptz_joystick (tray: right-click → Restart).
# The camera password is not here: set it with  setx PTZ_PASSWORD "..."

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

[buttons]                       # button index (0 = "button 1" in joy.cpl) = command
0 = "preset 1"
1 = "preset 2"
2 = "preset 3"
3 = "preset 4"
"""


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
        raise SystemExit(f"Can't create settings file {path}: {e}") from None
    return True
