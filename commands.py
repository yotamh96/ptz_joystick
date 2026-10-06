"""Camera-agnostic commands. Speeds are signed; 0 = stop. Camera adapters translate these."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PanTilt:
    pan: int    # + right, - left
    tilt: int   # + up, - down


@dataclass(frozen=True)
class Zoom:
    speed: int  # + in (tele), - out (wide)


@dataclass(frozen=True)
class Preset:
    number: int


Command = PanTilt | Zoom | Preset   # everything a camera adapter must handle
