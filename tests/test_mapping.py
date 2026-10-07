import unittest
from dataclasses import replace

from ptz_joystick.config import Settings
from ptz_joystick.controllers import ControllerState
from ptz_joystick.core.commands import PanTilt, Preset, Zoom
from ptz_joystick.core.mapping import Mapper, changed, scale


def state(x=0.0, y=0.0, r=0.0, buttons=0):
    return ControllerState({"X": x, "Y": y, "R": r}, buttons)


class ScaleTest(unittest.TestCase):
    def test_deadzone_is_zero(self):
        self.assertEqual(scale(0.1, 0.15, 24), 0)
        self.assertEqual(scale(-0.15, 0.15, 24), 0)

    def test_full_and_half_stick(self):
        self.assertEqual(scale(1.0, 0.15, 24), 24)
        self.assertEqual(scale(-1.0, 0.15, 20), -20)
        self.assertEqual(scale(0.5, 0.15, 24), 10)

    def test_full_speed_before_end_of_travel(self):
        # this pad only reaches ~0.75, so full_speed_at=0.7 must give top speed
        self.assertEqual(scale(0.7, 0.15, 24, full=0.7), 24)
        self.assertEqual(scale(-0.78, 0.15, 20, full=0.7), -20)
        self.assertEqual(scale(0.425, 0.15, 24, full=0.7), 12)   # halfway between deadzone and full

    def test_just_past_deadzone_is_one(self):
        self.assertEqual(scale(0.16, 0.15, 24), 1)


class ChangedTest(unittest.TestCase):
    def test_wobble_ignored(self):
        self.assertFalse(changed(PanTilt(10, 0), PanTilt(9, 0)))

    def test_stop_direction_and_big_step(self):
        self.assertTrue(changed(PanTilt(10, 0), PanTilt(0, 0)))
        self.assertTrue(changed(PanTilt(1, 0), PanTilt(-1, 0)))
        self.assertTrue(changed(PanTilt(10, 0), PanTilt(12, 0)))
        self.assertTrue(changed(None, Zoom(0)))


class MapperTest(unittest.TestCase):
    def setUp(self):
        self.m = Mapper(Settings())

    def test_first_reading_sends_stops(self):
        self.assertEqual(self.m.update(state()), [PanTilt(0, 0), Zoom(0)])

    def test_stick_up_left_is_full_speed_up_left(self):
        # Y reads low when pushed up; invert_tilt flips it
        self.assertEqual(self.m.update(state(x=-1, y=-1))[0], PanTilt(-24, 20))

    def test_real_stick_max_reaches_full_speed(self):
        # values seen on the real pad, 2026-10-06
        self.assertEqual(self.m.update(state(x=-0.78, y=-0.69, r=-0.75)),
                         [PanTilt(-24, 20), Zoom(7)])

    def test_zoom_stick_up_zooms_in(self):
        self.assertEqual(self.m.update(state(r=-1))[1], Zoom(7))

    def test_unchanged_reading_sends_nothing(self):
        self.m.update(state(x=0.5))
        self.assertEqual(self.m.update(state(x=0.49)), [])

    def test_button_fires_once_on_press(self):
        self.m.update(state())
        self.assertEqual(self.m.update(state(buttons=0b10)), [Preset(2)])
        self.assertEqual(self.m.update(state(buttons=0b10)), [])
        self.m.update(state())
        self.assertEqual(self.m.update(state(buttons=0b10)), [Preset(2)])

    def test_lost_controller_stops_and_keeps_buttons(self):
        self.m.update(state(x=1, buttons=0b1))
        self.assertEqual(self.m.update(None), [PanTilt(0, 0)])
        self.assertEqual(self.m.update(state(buttons=0b1)), [])   # held through unplug: no re-fire

    def test_invert_off(self):
        m = Mapper(replace(Settings(), invert_tilt=False))
        self.assertEqual(m.update(state(y=1))[0], PanTilt(0, 20))


if __name__ == "__main__":
    unittest.main()
