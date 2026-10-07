import unittest
from dataclasses import replace

from ptz_joystick.config import Settings
from ptz_joystick.controllers import ControllerState
from ptz_joystick.core.commands import PanTilt, Preset, SavePreset, Tracking, Zoom
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


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class MapperTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.m = Mapper(Settings(), clock=self.clock)

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

    def test_tap_goes_to_preset_on_release(self):
        self.m.update(state())
        self.assertEqual(self.m.update(state(buttons=0b10)), [])          # tap or hold? not known yet
        self.clock.now = 0.3
        self.assertEqual(self.m.update(state()), [Preset(2)])
        self.m.update(state(buttons=0b10))
        self.clock.now = 0.5
        self.assertEqual(self.m.update(state()), [Preset(2)])             # every tap fires

    def test_hold_saves_once_and_release_does_nothing(self):
        self.m.update(state())
        self.m.update(state(buttons=0b10))
        self.clock.now = 1.9
        self.assertEqual(self.m.update(state(buttons=0b10)), [])
        self.clock.now = 2.0
        self.assertEqual(self.m.update(state(buttons=0b10)), [SavePreset(2)])
        self.clock.now = 9.0
        self.assertEqual(self.m.update(state(buttons=0b10)), [])          # still held: no second save
        self.assertEqual(self.m.update(state()), [])                      # release after a save: no recall

    def test_saving_off_fires_on_press(self):
        m = Mapper(replace(Settings(), save_hold_seconds=0), clock=self.clock)
        m.update(state())
        self.assertEqual(m.update(state(buttons=0b10)), [Preset(2)])
        self.clock.now = 30.0
        self.assertEqual(m.update(state(buttons=0b10)), [])
        self.assertEqual(m.update(state()), [])

    def test_tracking_button_alternates_on_off(self):
        m, button5 = Mapper(Settings(buttons={4: Tracking(True)})), 0b10000
        m.update(state())
        self.assertEqual(m.update(state(buttons=button5)), [Tracking(True)])
        self.assertEqual(m.update(state(buttons=button5)), [])              # held: nothing more
        self.assertEqual(m.update(state()), [])                             # release: nothing
        self.assertEqual(m.update(state(buttons=button5)), [Tracking(False)])

    def test_lost_controller_stops_and_cancels_hold(self):
        self.m.update(state(x=1, buttons=0b1))
        self.assertEqual(self.m.update(None), [PanTilt(0, 0)])
        self.clock.now = 10.0
        self.assertEqual(self.m.update(state(buttons=0b1)), [])   # held through unplug: no save
        self.assertEqual(self.m.update(state()), [])              # and no recall on release

    def test_invert_off(self):
        m = Mapper(replace(Settings(), invert_tilt=False))
        self.assertEqual(m.update(state(y=1))[0], PanTilt(0, 20))


if __name__ == "__main__":
    unittest.main()
