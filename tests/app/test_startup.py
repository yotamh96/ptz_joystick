import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ptz_joystick import config
from ptz_joystick.app.startup import prepare
from tests.fakes import reset_logging


class PrepareTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(tempfile.TemporaryDirectory())) / config.FILE_NAME
        self.addCleanup(reset_logging)          # runs before the folder is deleted: cleanups go last-in, first-out
        self.enterContext(mock.patch.dict(os.environ, {"PTZ_PASSWORD": "pw"}))

    def test_first_run_writes_the_template_and_says_so(self):
        with self.assertLogs("ptz_joystick.app.startup", "INFO") as logs:
            s = prepare(self.path, keyboard=False)
        self.assertTrue(self.path.exists())
        self.assertEqual(s.controller, "winmm")
        self.assertTrue(any("Wrote default settings" in line for line in logs.output))

    def test_keyboard_flag_picks_the_keyboard_controller(self):
        with self.assertLogs("ptz_joystick.app.startup", "INFO"):
            self.assertEqual(prepare(self.path, keyboard=True).controller, "keyboard")

    def test_unknown_type_stops_naming_the_setting(self):
        self.path.write_text('controller = "xbox"', encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "controller must be one of"):
            prepare(self.path, keyboard=False)

    def test_missing_password_stops_with_the_fix(self):
        del os.environ["PTZ_PASSWORD"]
        with self.assertRaisesRegex(SystemExit, "Set the camera password first"):
            prepare(self.path, keyboard=False)


if __name__ == "__main__":
    unittest.main()
