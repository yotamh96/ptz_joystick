"""The rules every adapter must keep (the Camera and Controller docstrings), as tests.

An adapter's test class subclasses one of these and fills in its hooks: see test_ptzoptics.py, test_winmm.py and
test_keyboard.py. Import the module ("import contracts"), not the classes: unittest runs every TestCase it finds
in a test module, and a contract on its own has no hooks to run.
"""
import unittest
from typing import get_args

from ptz_joystick.cameras import Camera
from ptz_joystick.config import AXES
from ptz_joystick.controllers import ControllerState
from ptz_joystick.core.commands import (
    Command,
    PanTilt,
    Preset,
    SavePreset,
    Tracking,
    Zoom,
)

EXAMPLES: list[Command] = [PanTilt(3, -4), Zoom(-3), Preset(4), SavePreset(4), Tracking(True)]    # one of each command type
STOPS: list[Command] = [PanTilt(0, 0), Zoom(0)]


class CameraContract(unittest.TestCase):
    top_speeds: dict[str, int]          # the adapter module's TOP_SPEEDS

    def make(self, up: bool) -> Camera:
        """A camera whose connection always works (up) or always fails (camera down)."""
        raise NotImplementedError

    def test_examples_cover_every_command(self):
        self.assertEqual({type(c) for c in EXAMPLES}, set(get_args(Command)), "new command type? add an example")

    def test_stops_always_work(self):
        for cmd in STOPS:
            with self.subTest(cmd=cmd):
                self.assertIs(self.make(up=True).send(cmd), True)

    def test_every_command_is_sent_or_type_error(self):
        """TypeError = this camera can't do this kind of command at all; the sender drops it."""
        tops = self.top_speeds
        for cmd in [*EXAMPLES, PanTilt(tops["pan_max"], -tops["tilt_max"]), Zoom(tops["zoom_max"])]:
            with self.subTest(cmd=cmd):
                try:
                    self.assertIs(self.make(up=True).send(cmd), True)
                except TypeError:
                    pass

    def test_camera_down_returns_false_and_logs_once(self):
        cam = self.make(up=False)
        with self.assertLogs(level="WARNING") as logs:
            results = [cam.send(PanTilt(0, 0)) for _ in range(3)]
        self.assertEqual(results, [False] * 3)
        self.assertEqual(len(logs.records), 1, logs.output)

    def test_top_speeds_cover_every_speed_setting(self):
        self.assertEqual(set(self.top_speeds), {"pan_max", "tilt_max", "zoom_max"})
        self.assertTrue(all(isinstance(v, int) and v >= 1 for v in self.top_speeds.values()), self.top_speeds)


class ControllerContract(unittest.TestCase):
    def at_rest(self) -> ControllerState:
        """A reading with every stick centred and nothing held."""
        raise NotImplementedError

    def full_push(self) -> ControllerState:
        """A reading with every axis pushed to one end and only button 1 held."""
        raise NotImplementedError

    def unplugged(self) -> ControllerState | None:
        """A reading with the device gone. Skip if it can't be unplugged."""
        self.skipTest("this controller can't be unplugged")

    def test_axes_are_known_letters_and_stay_put(self):
        rest, push = self.at_rest(), self.full_push()
        self.assertLessEqual(set(rest.axes), set(AXES))
        self.assertEqual(set(rest.axes), set(push.axes), "an axis must not come and go")

    def test_rest_reads_centred_and_released(self):
        state = self.at_rest()
        self.assertTrue(all(v == 0.0 for v in state.axes.values()), state.axes)
        self.assertEqual(state.buttons, 0)

    def test_full_push_reads_one_and_button_1_is_bit_0(self):
        state = self.full_push()
        self.assertTrue(all(abs(v) == 1.0 for v in state.axes.values()), state.axes)
        self.assertEqual(state.buttons, 0b1)

    def test_unplugged_reads_none(self):
        self.assertIsNone(self.unplugged())
