"""Pure stick -> command logic. No I/O, so every rule here is unit-tested."""
from dataclasses import astuple

from ..config import Settings
from ..controllers import ControllerState
from .commands import Command, PanTilt, Zoom


def scale(v, deadzone, top, full=1.0):
    """|v| <= deadzone -> 0, else speed 1..top carrying v's sign. |v| >= full -> top."""
    if abs(v) <= deadzone:
        return 0
    speed = max(1, min(top, round((abs(v) - deadzone) / (full - deadzone) * top)))
    return speed if v > 0 else -speed


def _sign(n):
    return (n > 0) - (n < 0)


def changed(old, new):
    """Resend on stop<->move, direction flip, or a speed step of 2+ (ignores 9<->10 stick wobble)."""
    if old is None or type(old) is not type(new):
        return True
    return any(_sign(a) != _sign(b) or abs(a - b) > 1 for a, b in zip(astuple(old), astuple(new)))


class Mapper:
    """Turns each controller reading into the commands that need sending: button presses and changes only."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._last: dict[type, Command] = {}    # command type -> last command sent
        self._buttons = 0

    def update(self, state: ControllerState | None):
        """state=None means the controller is gone: stick reads centred, buttons unchanged."""
        s, cmds = self._settings, []
        axes = state.axes if state else {}
        if state:
            pressed = state.buttons & ~self._buttons
            self._buttons = state.buttons
            cmds += [cmd for b, cmd in s.buttons.items() if pressed >> b & 1]

        def axis(name, invert=False):
            return axes.get(name, 0.0) * (-1 if invert else 1)

        def speed(name, top, invert=False):
            return scale(axis(name, invert), s.deadzone, top, s.full_speed_at)

        for cmd in (PanTilt(speed(s.pan_axis, s.pan_max), speed(s.tilt_axis, s.tilt_max, s.invert_tilt)),
                    Zoom(speed(s.zoom_axis, s.zoom_max, s.invert_zoom))):
            if changed(self._last.get(type(cmd)), cmd):
                self._last[type(cmd)] = cmd
                cmds.append(cmd)
        return cmds
