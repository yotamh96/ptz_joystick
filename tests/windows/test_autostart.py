import unittest

from ptz_joystick.windows import autostart
from tests.windows.scratch_key import scratch_key

EXE = r"C:\Users\op\OneDrive - Draco\ptz_joystick_tray.exe"


class AutostartTest(unittest.TestCase):
    def setUp(self):
        self.key = scratch_key(self, "run")

    def test_enable_then_disable(self):
        command = autostart.command_for(EXE)
        self.assertFalse(autostart.enabled(command, self.key))
        autostart.enable(command, self.key)
        self.assertTrue(autostart.enabled(command, self.key))
        autostart.disable(self.key)
        self.assertFalse(autostart.enabled(command, self.key))

    def test_an_entry_for_another_copy_is_not_ours(self):
        autostart.enable(autostart.command_for(r"C:\old\ptz_joystick_tray.exe"), self.key)
        self.assertFalse(autostart.enabled(autostart.command_for(EXE), self.key))

    def test_disable_when_already_off(self):
        autostart.disable(self.key)

    def test_command_quotes_a_path_with_spaces(self):
        self.assertEqual(autostart.command_for(EXE), f'"{EXE}"')


if __name__ == "__main__":
    unittest.main()
