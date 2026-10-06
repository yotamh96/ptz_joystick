"""Camera port. Any object with send() fits; the core never imports an adapter."""
from typing import Protocol, runtime_checkable

from ..commands import Command


@runtime_checkable
class Camera(Protocol):
    def send(self, cmd: Command) -> bool:
        """Send one command from commands.py. True = camera accepted it."""
