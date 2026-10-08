import unittest

from ptz_joystick.windows.tray import dots


class DotPixelsTest(unittest.TestCase):
    def test_middle_has_the_color_and_corners_are_clear(self):
        px = dots.dot_pixels((0x22, 0xA0, 0x45), 16)
        self.assertEqual(len(px), 16 * 16 * 4)
        middle = (8 * 16 + 8) * 4
        self.assertEqual(px[middle:middle + 4], bytes((0x45, 0xA0, 0x22, 255)))      # blue, green, red, alpha
        for corner in (0, 15, 15 * 16, 16 * 16 - 1):
            self.assertEqual(px[corner * 4 + 3], 0, corner)


class DotIconTest(unittest.TestCase):
    def test_makes_an_icon(self):
        icon = dots.dot_icon((0xD0, 0x30, 0x30))
        self.assertTrue(icon)
        self.assertTrue(dots.user32.DestroyIcon(icon))


if __name__ == "__main__":
    unittest.main()
