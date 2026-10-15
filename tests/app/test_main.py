import unittest
from pathlib import Path
from unittest import mock

import ptz_joystick.app.main as app_main


class AdminTestCase(unittest.TestCase):
    """Already admin unless a test says otherwise, so no test pops up a real UAC prompt."""

    def setUp(self):
        patcher = mock.patch.object(app_main.elevation, "is_admin", return_value=True)
        self.is_admin = patcher.start()
        self.addCleanup(patcher.stop)


class AlreadyRunningTest(AdminTestCase):
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


class TrayFlagTest(AdminTestCase):
    def test_tray_flag_hands_over_to_the_tray(self):
        with mock.patch.object(app_main.single_instance, "claim", return_value=True), \
                mock.patch.object(app_main, "run_tray") as run_tray:
            app_main.main(["--tray", "--keyboard", "--config", "x.toml"])
        run_tray.assert_called_once_with(Path("x.toml"), True)


class TrayAsAdminTest(AdminTestCase):
    """Zao Virtual Cabin runs as admin, and Windows hides keys typed into it from a program that isn't."""

    def main(self, argv, relaunched=True):
        """main(argv) as a non-admin; relaunched: what the UAC prompt answers. Returns (relaunch mock, run_tray mock)."""
        self.is_admin.return_value = False
        with mock.patch.object(app_main.elevation, "relaunch_as_admin", return_value=relaunched) as relaunch, \
                mock.patch.object(app_main.single_instance, "claim", return_value=True) as claim, \
                mock.patch.object(app_main, "run_tray") as run_tray:
            app_main.main(argv)
        self.claim = claim
        return relaunch, run_tray

    def test_restarts_as_admin_and_leaves_the_instance_to_it(self):
        relaunch, run_tray = self.main(["--tray", "--config", "x.toml"])
        relaunch.assert_called_once_with(["--tray", "--config", "x.toml", "--elevated"])
        run_tray.assert_not_called()
        self.claim.assert_not_called()          # or the new copy would find this one still running

    def test_no_on_the_uac_prompt_runs_without_admin(self):
        _, run_tray = self.main(["--tray"], relaunched=False)
        run_tray.assert_called_once()

    def test_a_relaunched_copy_never_relaunches_again(self):
        """UAC off and not an admin: "runas" gives no admin rights, and must not loop."""
        relaunch, run_tray = self.main(["--tray", "--elevated"])
        relaunch.assert_not_called()
        run_tray.assert_called_once()

    def test_already_admin_just_runs(self):
        with mock.patch.object(app_main.elevation, "relaunch_as_admin") as relaunch, \
                mock.patch.object(app_main.single_instance, "claim", return_value=True), \
                mock.patch.object(app_main, "run_tray") as run_tray:
            app_main.main(["--tray"])
        relaunch.assert_not_called()
        run_tray.assert_called_once()


if __name__ == "__main__":
    unittest.main()
