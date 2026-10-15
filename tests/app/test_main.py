import unittest
from pathlib import Path
from unittest import mock

import ptz_joystick.app.main as app_main
from ptz_joystick.core.problem import Problem


class MainTest(unittest.TestCase):
    """Shared setUp: no real log file, no real mutex, no message box, no waiting on the keyboard. Already admin unless
    a test says otherwise, so no test pops up a real UAC prompt."""

    def setUp(self):
        self.is_admin = self.enterContext(mock.patch.object(app_main.elevation, "is_admin", return_value=True))
        self.setup_logging = self.enterContext(mock.patch.object(app_main, "setup_logging"))
        self.claim = self.enterContext(mock.patch.object(app_main.single_instance, "claim", return_value=True))
        self.box = self.enterContext(mock.patch.object(app_main, "message_box"))
        self.owns = self.enterContext(mock.patch.object(app_main, "owns_console", return_value=False))
        self.input = self.enterContext(mock.patch("builtins.input"))

    def fails(self, argv, error=None) -> list[str]:
        """main(argv) with the console (or, with --tray, the tray) raising error; None = main raises its own.
        Checks it exits 1. -> the log lines."""
        target = "run_tray" if "--tray" in argv else "_console"
        with mock.patch.object(app_main, target, side_effect=error), \
                self.assertLogs("ptz_joystick", "ERROR") as logs, self.assertRaises(SystemExit) as stopped:
            app_main.main(argv)
        self.assertEqual(stopped.exception.code, 1)
        return logs.output


class AlreadyRunningTest(MainTest):
    def setUp(self):
        super().setUp()
        self.claim.return_value = False

    def test_console_logs_it_with_the_fix(self):
        lines = self.fails([])
        self.assertIn("Another ptz_joystick is already running. Quit it first", lines[0])
        self.box.assert_not_called()                    # the console shows the log line itself

    def test_tray_also_shows_a_message_box(self):
        self.fails(["--tray"])
        self.box.assert_called_once_with("Another ptz_joystick is already running. Quit it first: its tray icon or "
                                         "console window, then run ptz_joystick again.")


class ProblemTest(MainTest):
    PASSWORD = Problem("The camera password is not set", fix='Run setx PTZ_PASSWORD "..." in a terminal')

    def test_console_logs_the_problem_with_the_restart_step(self):
        lines = self.fails([], self.PASSWORD)
        self.assertIn('The camera password is not set. Run setx PTZ_PASSWORD "..." in a terminal, then run '
                      'ptz_joystick again.', lines[0])
        self.input.assert_not_called()                  # run from a terminal: the prompt comes back at once
        self.box.assert_not_called()

    def test_double_clicked_console_waits_for_enter(self):
        self.owns.return_value = True
        self.fails([], self.PASSWORD)
        self.input.assert_called_once_with("Press Enter to close.")

    def test_no_keyboard_to_wait_for_still_exits(self):
        self.owns.return_value = True
        self.input.side_effect = EOFError
        self.fails([], self.PASSWORD)

    def test_tray_shows_the_problem_in_a_message_box(self):
        self.fails(["--tray"], Problem("A", fix="B"))
        self.box.assert_called_once_with("A. B, then run ptz_joystick again.")
        self.input.assert_not_called()

    def test_crash_logs_the_traceback_and_shows_a_plain_sentence(self):
        lines = self.fails(["--tray"], RuntimeError("boom"))
        self.assertTrue(lines[0].startswith("CRITICAL"), lines[0])
        self.assertIn("(RuntimeError('boom'))", lines[0])
        self.assertIn("Traceback", lines[0])
        self.box.assert_called_once_with("Unexpected error in ptz_joystick. See the log for details, then run "
                                         "ptz_joystick again.")

    def test_ctrl_c_is_not_a_crash(self):
        with mock.patch.object(app_main, "_console", side_effect=KeyboardInterrupt), \
                self.assertNoLogs("ptz_joystick", "ERROR"), self.assertRaises(KeyboardInterrupt):
            app_main.main([])


class TrayFlagTest(MainTest):
    def test_tray_flag_hands_over_to_the_tray(self):
        with mock.patch.object(app_main, "run_tray") as run_tray:
            app_main.main(["--tray", "--keyboard", "--config", "x.toml"])
        run_tray.assert_called_once_with(Path("x.toml"), True)

    def test_logging_starts_before_the_settings_are_read(self):
        with mock.patch.object(app_main, "run_tray"):
            app_main.main(["--tray", "--config", r"C:\tools\ptz_joystick.toml"])
        [settings] = self.setup_logging.call_args.args
        self.assertEqual(settings.log_file, r"C:\tools\ptz_joystick.log")



class TrayAsAdminTest(MainTest):
    """Zao Virtual Cabin runs as admin, and Windows hides keys typed into it from a program that isn't."""

    def main(self, argv, relaunched=True):
        """main(argv) as a non-admin; relaunched: what the UAC prompt answers. Returns (relaunch mock, run_tray mock)."""
        self.is_admin.return_value = False
        with mock.patch.object(app_main.elevation, "relaunch_as_admin", return_value=relaunched) as relaunch,                 mock.patch.object(app_main, "run_tray") as run_tray:
            app_main.main(argv)
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
        with mock.patch.object(app_main.elevation, "relaunch_as_admin") as relaunch,                 mock.patch.object(app_main, "run_tray") as run_tray:
            app_main.main(["--tray"])
        relaunch.assert_not_called()
        run_tray.assert_called_once()


if __name__ == "__main__":
    unittest.main()
