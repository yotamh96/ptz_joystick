import os
import unittest
import winreg

from ptz_joystick.windows.user_env import user_env
from tests.windows.scratch_key import scratch_key


class UserEnvTest(unittest.TestCase):
    def setUp(self):
        self.key = scratch_key(self, "env")

    def set(self, value, kind=winreg.REG_SZ):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "PTZ_PASSWORD", 0, kind, value)

    def test_plain_value_comes_back_as_typed(self):
        self.set("pa%ss$$word")
        self.assertEqual(user_env("PTZ_PASSWORD", self.key), "pa%ss$$word")

    def test_expandable_value_is_expanded_like_windows_does(self):
        self.set("%USERNAME%-$x", winreg.REG_EXPAND_SZ)
        self.assertEqual(user_env("PTZ_PASSWORD", self.key), os.environ["USERNAME"] + "-$x")

    def test_missing_value_is_none(self):
        self.assertIsNone(user_env("PTZ_PASSWORD", self.key))


if __name__ == "__main__":
    unittest.main()
