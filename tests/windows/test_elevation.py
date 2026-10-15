import unittest
from unittest import mock

from ptz_joystick.windows import elevation

EXE = r"C:\Users\op\OneDrive - Draco\ptz_joystick_tray.exe"


class CommandTest(unittest.TestCase):
    def test_the_exe_restarts_itself(self):
        with mock.patch.object(elevation.sys, "frozen", True, create=True), \
                mock.patch.object(elevation.sys, "executable", EXE):
            self.assertEqual(elevation.command(["--tray", "--config", r"C:\a b\x.toml"]),
                             (EXE, r'--tray --config "C:\a b\x.toml"'))

    def test_from_source_it_restarts_the_module(self):
        with mock.patch.object(elevation.sys, "executable", r"C:\Python314\pythonw.exe"):
            self.assertEqual(elevation.command(["--tray"]), (r"C:\Python314\pythonw.exe", "-m ptz_joystick --tray"))


class RelaunchTest(unittest.TestCase):
    def relaunch(self, result):
        """relaunch_as_admin() with ShellExecuteW returning result: above 32 is success, 5 is "No" on the UAC prompt."""
        with mock.patch.object(elevation, "shell32") as shell32, \
                mock.patch.object(elevation, "command", return_value=(EXE, "--tray")), \
                mock.patch.object(elevation.os, "getcwd", return_value=r"C:\here"):
            shell32.ShellExecuteW.return_value = result
            return elevation.relaunch_as_admin(["--tray"]), shell32.ShellExecuteW.call_args.args

    def test_asks_windows_to_run_it_as_admin_from_the_same_folder(self):
        ok, args = self.relaunch(42)
        self.assertTrue(ok)
        self.assertEqual(args, (None, "runas", EXE, "--tray", r"C:\here", elevation.SW_SHOWNORMAL))

    def test_no_on_the_uac_prompt(self):
        self.assertFalse(self.relaunch(5)[0])


if __name__ == "__main__":
    unittest.main()
