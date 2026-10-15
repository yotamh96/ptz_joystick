import os
import unittest
import winreg
from unittest import mock

import ptz_joystick.windows.user_env as env_module
from ptz_joystick.windows.user_env import set_user_env, user_env
from tests.windows.scratch_key import scratch_key


class UserEnvTest(unittest.TestCase):
    def setUp(self):
        self.key = scratch_key(self, "env")

    def test_set_then_read_back_as_typed(self):
        password = 'p%a"ss wörd מ'                     # % is not expanded, quotes and Hebrew survive
        with mock.patch.object(env_module.user32, "SendMessageTimeoutW") as broadcast:
            set_user_env("PTZ_PASSWORD", password, self.key)
        self.assertEqual(user_env("PTZ_PASSWORD", self.key), password)
        broadcast.assert_called_once()                  # Explorer hears of it, as after setx

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
