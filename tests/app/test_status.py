import unittest
from pathlib import Path

from ptz_joystick.app.status import GREEN, RED, YELLOW, Popup, Status
from ptz_joystick.config import bad_setting
from ptz_joystick.core.problem import Problem, crashed

HOST = "http://192.168.77.3"
UNPLUGGED_TEXT = "The controller is unplugged and the camera stopped. Plug it back in."
UNPLUGGED = Popup(UNPLUGGED_TEXT, "warning")
LOGIN = Problem("The camera refused the login", fix="Check user in ptz_joystick.toml and PTZ_PASSWORD",
                detail="HTTP 401")
UNREACHABLE = Problem(f"Can't reach the camera at {HOST}", fix="Check host in ptz_joystick.toml and the network",
                      detail="timed out")


def driving():
    s = Status("ptz_joystick.log")
    s.driving(HOST)
    return s


class BeforeDrivingTest(unittest.TestCase):
    def test_starts_yellow_with_the_app_name_in_the_hover_text(self):
        s = Status("ptz_joystick.log")
        self.assertEqual((s.color, s.text), (YELLOW, "Starting…"))
        self.assertEqual(s.tooltip, "ptz_joystick: Starting…")

    def test_waiting_for_camera_says_why_without_the_detail(self):
        s = Status("ptz_joystick.log")
        s.waiting_for_camera(HOST, LOGIN)
        self.assertEqual((s.color, s.text),
                         (YELLOW, "The camera refused the login. Check user in ptz_joystick.toml and PTZ_PASSWORD."))

    def test_waiting_for_camera_before_it_says_why(self):
        s = Status("ptz_joystick.log")
        s.waiting_for_camera(HOST, None)
        self.assertEqual(s.text, f"Waiting for the camera at {HOST}")

    def test_stick_prompt_once_per_session_and_only_while_waiting(self):
        s = Status("ptz_joystick.log")
        self.assertIsNone(s.stick_prompt())                 # not waiting yet
        s.waiting_for_stick()
        self.assertEqual((s.color, s.text), (YELLOW, "Move the left stick to start"))
        self.assertEqual(s.stick_prompt(), Popup("Move the left stick to start", "info"))
        self.assertIsNone(s.stick_prompt())
        s.starting()                                        # Restart: a new session may prompt again
        s.waiting_for_stick()
        self.assertIsNotNone(s.stick_prompt())

    def test_a_late_stick_prompt_after_the_stick_moved_is_dropped(self):
        s = Status("ptz_joystick.log")
        s.waiting_for_stick()
        s.driving(HOST)
        self.assertIsNone(s.stick_prompt())

    def test_no_controller_shows_the_problem(self):
        s = Status("ptz_joystick.log")
        s.no_controller(Problem("No controller found", fix="Plug it in and check that it shows in joy.cpl"))
        self.assertEqual((s.color, s.text),
                         (YELLOW, "No controller found. Plug it in and check that it shows in joy.cpl."))

    def test_controller_and_camera_news_before_driving_is_ignored(self):
        s = Status("ptz_joystick.log")
        s.waiting_for_stick()
        self.assertIsNone(s.controller(False))
        s.camera(False, UNREACHABLE)
        self.assertEqual(s.text, "Move the left stick to start")


class DrivingTest(unittest.TestCase):
    def test_driving_is_green(self):
        s = driving()
        self.assertEqual((s.color, s.text), (GREEN, f"Driving the camera at {HOST}"))

    def test_unplugged_controller_pops_up_once_per_unplug(self):
        s = driving()
        self.assertEqual(s.controller(False), UNPLUGGED)
        self.assertEqual((s.color, s.text), (YELLOW, UNPLUGGED_TEXT))      # the status and the pop-up agree
        self.assertIsNone(s.controller(False))
        self.assertIsNone(s.controller(True))
        self.assertEqual(s.color, GREEN)
        self.assertEqual(s.controller(False), UNPLUGGED)    # unplugged again: pops up again

    def test_camera_drop_changes_the_icon_only(self):
        s = driving()
        s.camera(False, UNREACHABLE)
        self.assertEqual((s.color, s.text), (YELLOW, UNREACHABLE.text()))
        s.camera(True, None)
        self.assertEqual((s.color, s.text), (GREEN, f"Driving the camera at {HOST}"))

    def test_camera_drop_without_a_reason(self):
        s = driving()
        s.camera(False, None)
        self.assertEqual(s.text, "The camera is not answering")

    def test_unplugged_controller_wins_over_a_silent_camera(self):
        s = driving()
        s.camera(False, UNREACHABLE)
        s.controller(False)
        self.assertEqual(s.text, UNPLUGGED_TEXT)
        s.controller(True)
        self.assertEqual(s.text, UNREACHABLE.text())


class StoppedTest(unittest.TestCase):
    def test_red_adds_the_restart_step_and_pops_up_every_time(self):
        s = driving()
        text = "Unexpected error in ptz_joystick. See the log for details, then click Restart."
        self.assertEqual(s.stopped(crashed(RuntimeError("boom"))), Popup(text, "error"))
        self.assertEqual((s.color, s.text), (RED, text))
        self.assertEqual(s.stopped(Problem("A", fix="B")), Popup("A. B, then click Restart.", "error"))
        self.assertIsNone(s.controller(False))              # a stopped session drives nothing

    def test_a_long_message_stays_whole_for_the_pop_up(self):
        problem = bad_setting(Path("ptz_joystick.toml"),
                              "bad command 'presset 1', use one of: " + ", ".join(["preset <n>"] * 8))
        popup = driving().stopped(problem)
        self.assertGreater(len(popup.text), 128)            # longer than the hover text holds
        self.assertTrue(popup.text.endswith(", then click Restart."), popup.text)

    def test_update_pops_up_without_changing_the_icon(self):
        s = driving()
        self.assertEqual(s.update("v0.4.0"), Popup("Update available: v0.4.0", "info"))
        self.assertEqual(s.color, GREEN)

    def test_log_file_follows_the_settings(self):
        s = Status(r"C:\tools\ptz_joystick.log")
        s.log_to("")
        self.assertEqual(s.log_file, "")


if __name__ == "__main__":
    unittest.main()
