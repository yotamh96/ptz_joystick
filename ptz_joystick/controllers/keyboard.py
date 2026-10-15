"""Keyboard as a controller, for testing without a gamepad. Windows only.

Arrows = left stick (pan / tilt), W / S = right stick up / down (zoom), keys 1-4 = buttons 1-4.
A key reads as the stick pushed fully, so moves run at pan_max / tilt_max / zoom_max.
Keys count only while TARGET_EXE's window is in front (windows/focus.py); otherwise it reads as sticks centred,
nothing held.
"""
import ctypes
import logging

from ..config import Settings
from ..windows.elevation import is_admin
from ..windows.focus import AppInFront
from . import ControllerState

log = logging.getLogger(__name__)

TARGET_EXE = "Zao Virtual Cabin.exe"       # ponytail: hardcoded; make it a setting when a second app needs keys
VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN = 0x25, 0x26, 0x27, 0x28
BUTTON_KEYS = "1234"       # a digit's or letter's virtual-key code is its ASCII code
HELP = ("Keyboard controller: arrows pan/tilt, W/S zoom in/out, 1-4 = presets. "
        "Keys work while Zao Virtual Cabin is in front.")
NOT_ADMIN = ("Not running as administrator: Zao Virtual Cabin runs as admin, so Windows hides the keys typed into it "
             "from this program. Run it as administrator.")

user32 = ctypes.WinDLL("user32")


def _held(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


class KeyboardController:
    def __init__(self, settings: Settings):
        self._pan, self._tilt, self._zoom = settings.pan_axis, settings.tilt_axis, settings.zoom_axis
        self._window = AppInFront(TARGET_EXE)

    def read(self) -> ControllerState:
        def axis(minus: int, plus: int) -> float:
            return float(_held(plus) - _held(minus))

        if not self._window.in_front():
            return ControllerState(dict.fromkeys((self._pan, self._tilt, self._zoom), 0.0), 0)
        # Up reads low, like the real pad (hence invert_tilt / invert_zoom = true), so the same settings work.
        axes = {self._pan: axis(VK_LEFT, VK_RIGHT), self._tilt: axis(VK_UP, VK_DOWN), self._zoom: axis(ord("W"), ord("S"))}
        buttons = sum(_held(ord(k)) << i for i, k in enumerate(BUTTON_KEYS))
        return ControllerState(axes, buttons)


def start(settings: Settings) -> KeyboardController:
    log.info(HELP)
    if not is_admin():
        log.warning(NOT_ADMIN)
    return KeyboardController(settings)
