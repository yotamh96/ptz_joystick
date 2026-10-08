"""Camera port: the one thing the core needs from a camera. The core never imports an adapter."""
from typing import Protocol

from ..core.commands import Command


class Camera(Protocol):
    def send(self, cmd: Command, /) -> bool:
        """Send one command from core/commands.py. True = the camera took it.

        Rules for an adapter:
        - PanTilt(0, 0) is "stop" and must always work: it is the startup check and the last thing sent.
        - Camera down, timeout, refused: return False, and log it once per outage, not per call (see
          ptzoptics.py). The sender retries stick moves until taken and drops a button action after 3
          refusals.
        - A command type this camera can't do at all (a camera without zoom, say): raise TypeError. The
          sender drops it.
        - Return within about a second (use a timeout): at shutdown the stops get 3 s in total.
        - Called from one thread at a time, so no locking needed.

        Each adapter module also has TOP_SPEEDS: the most pan_max / tilt_max / zoom_max may be for this camera,
        e.g. {"pan_max": 24, "tilt_max": 20, "zoom_max": 7}. Startup refuses settings above them.

        To add a camera: write the adapter, add a line to CAMERAS in app/registry.py, and subclass
        tests/contracts.py CameraContract in its tests. mypy (in CI) checks the adapter against this signature
        where CAMERAS lists it. The "/" means the parameter's name is free.
        """
