import ctypes
import unittest
from ctypes import wintypes

from ptz_joystick.windows.tray import menu

MF_BYPOSITION = 0x0400
user32 = ctypes.WinDLL("user32")        # own copy, for reading the menu back
user32.GetMenuItemCount.argtypes = [wintypes.HMENU]
user32.GetMenuState.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]
user32.GetMenuStringW.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.LPWSTR, ctypes.c_int, wintypes.UINT]
user32.DestroyMenu.argtypes = [wintypes.HMENU]


def nothing():
    pass


class BuildTest(unittest.TestCase):
    def build(self, entries):
        h = menu.build(entries)
        self.addCleanup(user32.DestroyMenu, h)
        return h

    def test_status_line_separator_grayed_and_checked_items(self):
        h = self.build([menu.Item("Driving http://cam"), None, menu.Item("Restart", nothing),
                        menu.Item("Open log", nothing, enabled=False),
                        menu.Item("Start with Windows", nothing, checked=True)])
        self.assertEqual(user32.GetMenuItemCount(h), 5)
        state = [user32.GetMenuState(h, i, MF_BYPOSITION) for i in range(5)]
        self.assertTrue(state[0] & menu.MF_GRAYED)              # no action: can't be picked
        self.assertTrue(state[1] & menu.MF_SEPARATOR)
        self.assertFalse(state[2] & (menu.MF_GRAYED | menu.MF_CHECKED))
        self.assertTrue(state[3] & menu.MF_GRAYED)
        self.assertTrue(state[4] & menu.MF_CHECKED)

    def test_ampersands_show_as_typed(self):
        h = self.build([menu.Item("ptzcmd&right&24")])
        text = ctypes.create_unicode_buffer(64)
        user32.GetMenuStringW(h, 0, text, 64, MF_BYPOSITION)
        self.assertEqual(text.value, "ptzcmd&&right&&24")      # stored doubled: Windows draws one &


if __name__ == "__main__":
    unittest.main()
