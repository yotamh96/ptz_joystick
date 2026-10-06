import unittest

from ptz_joystick.cameras.ptzoptics import to_query
from ptz_joystick.commands import PanTilt, Preset, Zoom


class ToQueryTest(unittest.TestCase):
    def test_pantilt(self):
        self.assertEqual(to_query(PanTilt(0, 0)), "ptzcmd&ptzstop&0&0")
        self.assertEqual(to_query(PanTilt(-24, 20)), "ptzcmd&leftup&24&20")
        self.assertEqual(to_query(PanTilt(10, 0)), "ptzcmd&right&10&1")    # idle axis still needs speed 1
        self.assertEqual(to_query(PanTilt(0, -5)), "ptzcmd&down&1&5")
        self.assertEqual(to_query(PanTilt(3, -4)), "ptzcmd&rightdown&3&4")

    def test_zoom(self):
        self.assertEqual(to_query(Zoom(0)), "ptzcmd&zoomstop&0")
        self.assertEqual(to_query(Zoom(7)), "ptzcmd&zoomin&7")
        self.assertEqual(to_query(Zoom(-3)), "ptzcmd&zoomout&3")

    def test_preset(self):
        self.assertEqual(to_query(Preset(4)), "ptzcmd&poscall&4")


if __name__ == "__main__":
    unittest.main()
