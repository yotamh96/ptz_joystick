import unittest
from unittest import mock

from ptz_joystick.config import Settings
from ptz_joystick.controllers import keyboard
from ptz_joystick.controllers.keyboard import VK_DOWN, VK_LEFT, VK_RIGHT, VK_UP
from ptz_joystick.core.commands import PanTilt, Zoom
from ptz_joystick.core.mapping import Mapper
from tests import contracts


def read(*keys, settings=None, in_front=True):
    """One read() with these virtual-key codes held, and Zao in front or not (see tests/windows/test_focus.py)."""
    with mock.patch.object(keyboard, "AppInFront") as app:
        app.return_value.in_front.return_value = in_front
        c = keyboard.KeyboardController(settings or Settings())
    with mock.patch.object(keyboard, "_held", side_effect=lambda vk: vk in keys):
        return c.read()


class KeyboardControllerTest(contracts.ControllerContract):
    def at_rest(self):
        return read()

    def full_push(self):
        return read(VK_RIGHT, VK_DOWN, ord("S"), ord("1"))

    def test_nothing_held_reads_centred(self):
        state = read()
        self.assertEqual(state.axes, {"X": 0.0, "Y": 0.0, "R": 0.0})
        self.assertEqual(state.buttons, 0)

    def test_keys_move_the_camera_the_way_they_point(self):
        """Through the mapper with default settings: up arrow = tilt up, right = pan right, W = zoom in."""
        s = Settings()
        self.assertIn(PanTilt(s.pan_max, s.tilt_max), Mapper(s).update(read(VK_RIGHT, VK_UP)))
        self.assertIn(Zoom(s.zoom_max), Mapper(s).update(read(ord("W"))))
        self.assertIn(Zoom(-s.zoom_max), Mapper(s).update(read(ord("S"))))

    def test_opposite_keys_cancel(self):
        self.assertEqual(read(VK_LEFT, VK_RIGHT).axes["X"], 0.0)

    def test_digit_keys_are_buttons(self):
        self.assertEqual(read(ord("1"), ord("4")).buttons, 0b1001)

    def test_axes_follow_settings(self):
        state = read(VK_RIGHT, settings=Settings(pan_axis="U", tilt_axis="V", zoom_axis="Z"))
        self.assertEqual(state.axes, {"U": 1.0, "V": 0.0, "Z": 0.0})

    def test_another_app_in_front_reads_centred_and_released(self):
        state = read(VK_RIGHT, ord("1"), in_front=False)
        self.assertEqual(state.axes, {"X": 0.0, "Y": 0.0, "R": 0.0})
        self.assertEqual(state.buttons, 0)


class StartTest(unittest.TestCase):
    def start(self, admin):
        with mock.patch.object(keyboard, "is_admin", return_value=admin), mock.patch.object(keyboard, "AppInFront"):
            keyboard.start(Settings())

    def test_warns_when_not_admin_as_zao_keys_are_hidden(self):
        with self.assertLogs("ptz_joystick.controllers.keyboard", "WARNING") as logs:
            self.start(admin=False)
        self.assertIn(keyboard.NOT_ADMIN, logs.output[-1])

    def test_no_warning_as_admin(self):
        with self.assertNoLogs("ptz_joystick.controllers.keyboard", "WARNING"):
            self.start(admin=True)


if __name__ == "__main__":
    unittest.main()
