"""Camera-agnostic commands. Speeds are signed; 0 = stop. Camera adapters translate these.

Rules for a new command:
- A frozen dataclass of plain values (numbers, text).
- A complete instruction that is safe to send twice: "go to preset 3", "zoom in at speed 5". Not "focus one
  step nearer" or "toggle autofocus": the sender keeps only the newest command of each type, and may resend
  one after a lost reply.
- Add it to Command. If a button may fire it, give it a name in config.BUTTON_COMMANDS.
- Add a case for it to every camera adapter (to_query in cameras/ptzoptics.py), or let that camera raise
  TypeError.
"""
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


Command = PanTilt | Zoom | Preset   # everything a camera adapter may be sent
MOVES = PanTilt | Zoom              # what the sticks send: current state, retried until the camera takes it.
                                    # Every other command is a one-shot action (a button press).
