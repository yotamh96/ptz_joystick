"""Every setting in one place."""
import os
from dataclasses import dataclass, field

from .commands import Preset


@dataclass(frozen=True)
class Settings:
    host: str = "http://192.168.77.3"
    user: str = "admin"
    password: str = ""                  # filled from PTZ_PASSWORD by load()
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
    log_file: str = "ptz_joystick.log"  # appended next to where you run it; "" = terminal only


def load() -> Settings:
    password = os.environ.get("PTZ_PASSWORD")
    if not password:
        raise SystemExit('Set the camera password first:  setx PTZ_PASSWORD "..."  then open a new terminal.')
    return Settings(password=password)
