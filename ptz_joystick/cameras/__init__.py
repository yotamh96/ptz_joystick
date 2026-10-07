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

        mypy (in CI) checks that adapters match this signature. The "/" means the parameter's name is free.
        """
