"""Every camera and controller type the settings can name in camera = / controller =.

A new adapter is one line here; see docs/extending.md for the steps. Each entry also says, for mypy,
that the adapter fits its Protocol. Only app/ imports this, so the core and the ports never see an adapter.
"""
from collections.abc import Callable
from typing import NamedTuple

from ..cameras import Camera, ptzoptics
from ..config import Settings
from ..controllers import Controller, keyboard, winmm


class CameraType(NamedTuple):
    connect: Callable[[Settings], Camera]
    top_speeds: dict[str, int]          # the adapter module's TOP_SPEEDS


CAMERAS: dict[str, CameraType] = {
    "ptzoptics": CameraType(lambda s: ptzoptics.PtzOpticsCamera(s.host, s.user, s.password, s.timeout),
                            ptzoptics.TOP_SPEEDS),
}
CONTROLLERS: dict[str, Callable[[Settings], Controller]] = {
    "winmm": lambda s: winmm.discover(),
    "keyboard": keyboard.start,
}
