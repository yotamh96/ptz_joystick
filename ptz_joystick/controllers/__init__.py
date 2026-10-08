"""Controller port: the one thing the core needs from a controller. The core never imports an adapter."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ControllerState:
    axes: dict[str, float]  # axis letter ("X", "Y", "R", ...) -> -1..1, only axes the device has
    buttons: int            # bitmask, bit n = button n held


class Controller(Protocol):
    def read(self) -> ControllerState | None:
        """The current sticks and buttons, or None if the controller is unplugged. Called every 50 ms.

        Rules for an adapter:
        - Return at once; never wait for input.
        - Unplugged: return None, and states again once it's back. The camera stops and the session waits.
          Raising instead ends the session.
        - axes: only axes the device really has. The startup check relies on that to catch a pan_axis /
          tilt_axis / zoom_axis the device lacks. Values -1..1, 0 = centred. Keys are letters from
          config.AXES (the ones joy.cpl shows), because those are what the settings name.
        - buttons: bit n = button n held. Bit 0 is "button 1" in joy.cpl.

        Each adapter module also has a function that returns a ready controller, like winmm.discover(). It
        may wait for the user. With no device, it raises SystemExit("<what to check>"). Annotate its return
        type, so mypy (in CI) can check the controller against this Protocol where CONTROLLERS lists it.

        To add a controller: write the adapter, add a line to CONTROLLERS in app/registry.py, and subclass
        tests/contracts.py ControllerContract in its tests.
        """
