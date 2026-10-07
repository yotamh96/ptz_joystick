import unittest
from unittest import mock

from ptz_joystick.controllers import ControllerState, winmm
from ptz_joystick.controllers.winmm import JOYCAPSW, JOYINFOEX, WinmmController


def caps(**extra):
    """A device with X and Y (0..100) plus any extra axes, e.g. caps(R=(0, 100))."""
    c = JOYCAPSW(wXmin=0, wXmax=100, wYmin=0, wYmax=100)
    for a, (lo, hi) in extra.items():
        setattr(c, f"w{a}min", lo)
        setattr(c, f"w{a}max", hi)
        c.wCaps |= winmm.HAS_AXIS[a]
    return c


def pos(buttons=0, **raw):
    return JOYINFOEX(dwButtons=buttons, **{f"dw{a}pos": v for a, v in raw.items()})


class WinmmControllerTest(unittest.TestCase):
    def read(self, device_caps, reading):
        """One read() from a device with these caps returning this reading (None = unplugged)."""
        with mock.patch.object(winmm, "_caps", return_value=device_caps):
            c = WinmmController(0)
        with mock.patch.object(winmm, "_pos", return_value=reading):
            return c.read()

    def test_reports_only_axes_the_device_has(self):
        self.assertEqual(set(self.read(caps(), pos(X=50, Y=50)).axes), {"X", "Y"})
        self.assertEqual(set(self.read(caps(R=(0, 100)), pos(X=50, Y=50, R=50)).axes), {"X", "Y", "R"})

    def test_scales_to_minus_one_one(self):
        state = self.read(caps(R=(0, 100)), pos(X=0, Y=50, R=100))
        self.assertEqual(state.axes, {"X": -1.0, "Y": 0.0, "R": 1.0})

    def test_out_of_range_is_clamped(self):
        state = self.read(caps(), pos(X=150, Y=50))
        self.assertEqual(state.axes["X"], 1.0)

    def test_flat_axis_reads_centred(self):
        state = self.read(caps(R=(7, 7)), pos(X=50, Y=50, R=7))
        self.assertEqual(state.axes["R"], 0.0)

    def test_buttons_pass_through(self):
        self.assertEqual(self.read(caps(), pos(buttons=0b101, X=50, Y=50)),
                         ControllerState({"X": 0.0, "Y": 0.0}, 0b101))

    def test_unplugged_reads_none(self):
        self.assertIsNone(self.read(caps(), None))

    def test_device_without_caps_is_rejected(self):
        with mock.patch.object(winmm, "_caps", return_value=None), self.assertRaises(OSError):
            WinmmController(3)


if __name__ == "__main__":
    unittest.main()
