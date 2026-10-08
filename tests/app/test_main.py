import unittest
from pathlib import Path
from unittest import mock

import ptz_joystick.app.main as app_main


class AlreadyRunningTest(unittest.TestCase):
    def test_second_copy_stops_with_the_fix(self):
        with mock.patch.object(app_main.single_instance, "claim", return_value=False), \
                mock.patch.object(app_main, "message_box") as box, \
                self.assertRaisesRegex(SystemExit, "already running. Quit it first"):
            app_main.main([])
        box.assert_not_called()                     # the console shows the message itself

    def test_second_tray_copy_also_says_so_in_a_message_box(self):
        with mock.patch.object(app_main.single_instance, "claim", return_value=False), \
                mock.patch.object(app_main, "message_box") as box, self.assertRaises(SystemExit):
            app_main.main(["--tray"])
        box.assert_called_once_with(app_main.ALREADY_RUNNING)


class TrayFlagTest(unittest.TestCase):
    def test_tray_flag_hands_over_to_the_tray(self):
        with mock.patch.object(app_main.single_instance, "claim", return_value=True), \
                mock.patch.object(app_main, "run_tray") as run_tray:
            app_main.main(["--tray", "--keyboard", "--config", "x.toml"])
        run_tray.assert_called_once_with(Path("x.toml"), True)


if __name__ == "__main__":
    unittest.main()
