import runpy
import unittest
from unittest import mock


class EntryPointTest(unittest.TestCase):
    def test_ctrl_c_and_clean_exit_stay_quiet(self):
        for exc in (KeyboardInterrupt(), SystemExit(1)):
            with self.subTest(exc=exc), mock.patch("ptz_joystick.app.main.main", side_effect=exc), \
                    self.assertNoLogs("ptz_joystick", "CRITICAL"):
                try:
                    runpy.run_module("ptz_joystick", run_name="__main__")
                except SystemExit as e:
                    self.assertEqual(e.code, 1)


if __name__ == "__main__":
    unittest.main()
