"""Controller port. Any object with read() fits; the core never imports an adapter."""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ControllerState:
    axes: dict      # axis letter ("X", "Y", "R", ...) -> -1..1, only axes the device has
    buttons: int    # bitmask, bit n = button n held


@runtime_checkable
class Controller(Protocol):
    def read(self) -> ControllerState | None:
        """None = controller unplugged."""
