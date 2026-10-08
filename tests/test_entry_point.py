import runpy
import unittest
from unittest import mock


class CrashTest(unittest.TestCase):
    def test_crash_reason_goes_to_log(self):
        with mock.patch("ptz_joystick.app.main.main", side_effect=RuntimeError("boom")), \
                self.assertLogs("ptz_joystick", "CRITICAL") as logs, self.assertRaises(SystemExit):
            runpy.run_module("ptz_joystick", run_name="__main__")
        self.assertIn("boom", logs.output[0])

    def test_ctrl_c_and_clean_exit_stay_quiet(self):
        for exc in (KeyboardInterrupt(), SystemExit("No controller found.")):
            with self.subTest(exc=exc), mock.patch("ptz_joystick.app.main.main", side_effect=exc), \
                    self.assertNoLogs("ptz_joystick", "CRITICAL"):
                try:
                    runpy.run_module("ptz_joystick", run_name="__main__")
                except SystemExit as e:
                    self.assertEqual(str(e), "No controller found.")


if __name__ == "__main__":
    unittest.main()
