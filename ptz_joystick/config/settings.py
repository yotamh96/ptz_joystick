"""Settings: every setting, its default and its validation. ptz_joystick.toml overrides the defaults (loading.py)."""
from collections.abc import Callable
from dataclasses import dataclass, field

from ..core.commands import MOVES, Command, Preset, Tracking

AXES = "XYZRUV"
MAX_TIMEOUT = 2.0       # seconds: a stuck request plus the final stops must fit the 3 s shutdown window
# Settings-file name -> (command a button may fire, how to write it). Actions only: a stick move started by a
# button would never be stopped, because the sticks only stop moves they started. A "tracking" button toggles:
# the mapper sends Tracking(on) and Tracking(off) in turn, so the stored Tracking(True) only marks the button.
BUTTON_COMMANDS: dict[str, tuple[Callable[..., Command], str]] = {
    "preset": (Preset, "preset N (N = a whole number, 0 or more)"),
    "tracking": (lambda: Tracking(True), "tracking"),
}



@dataclass(frozen=True)
class Settings:
    camera: str = "ptzoptics"           # camera type: a name in app/registry.py CAMERAS
    host: str = "http://192.168.77.3"
    user: str = "admin"
    password: str = ""                  # filled from PTZ_PASSWORD by load(), never from the file
    timeout: float = 1.0                # seconds per camera request

    controller: str = "winmm"           # controller type: a name in app/registry.py CONTROLLERS
    pan_axis: str = "X"                 # X Y Z R U V  (debug=True shows which one moves)
    tilt_axis: str = "Y"
    zoom_axis: str = "R"
    invert_tilt: bool = True            # stick up usually reads low
    invert_zoom: bool = True            # stick up = zoom in
    deadzone: float = 0.15
    full_speed_at: float = 0.7          # stick reading that means top speed (this pad tops out ~0.75, not 1.0)

    pan_max: int = 24                   # top speeds; each camera type checks its own limits (app/checks.py)
    tilt_max: int = 20
    zoom_max: int = 7

    buttons: dict = field(default_factory=lambda: {   # button index -> command
        0: Preset(1), 1: Preset(2), 2: Preset(3), 3: Preset(4)})
    save_hold_seconds: float = 2.0      # hold a preset button this long to save the current position there; 0 = off
    debug: bool = False                # True = log axis values and buttons (DEBUG level)
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
            check(isinstance(v, int) and v >= 1, f"{name} must be a whole number, 1 or more, got {v!r}")
        check(0 < self.timeout <= MAX_TIMEOUT,
              f"timeout must be more than 0 and at most {MAX_TIMEOUT:g} seconds, got {self.timeout!r}")
        check(0 <= self.save_hold_seconds <= 10,
              f"save_hold_seconds must be 0 (saving off) to 10 seconds, got {self.save_hold_seconds!r}")
        check(self.host.startswith(("http://", "https://")), f"host must start with http://, got {self.host!r}")
        bad = {b: c for b, c in self.buttons.items()
               if not (isinstance(b, int) and 0 <= b < 32 and isinstance(c, Command) and not isinstance(c, MOVES))}
        check(not bad, f"buttons must map a button index 0-31 to a button action (not a stick move), bad: {bad}")
