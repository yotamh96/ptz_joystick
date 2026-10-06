"""Every setting in one place."""
import os
from dataclasses import dataclass, field

from .commands import Command, Preset

AXES = "XYZRUV"


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
        check(not bad, f"buttons must map a button index 0-31 to a command from commands.py, bad: {bad}")


def load() -> Settings:
    password = os.environ.get("PTZ_PASSWORD")
    if not password:
        raise SystemExit('Set the camera password first:  setx PTZ_PASSWORD "..."  then open a new terminal.')
    try:
        return Settings(password=password)
    except ValueError as e:
        raise SystemExit(f"config.py: {e}") from None
