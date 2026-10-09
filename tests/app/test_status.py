import unittest

from ptz_joystick.app.status import GREEN, RED, YELLOW, Popup, Status

HOST = "http://192.168.77.3"
UNPLUGGED = Popup("Controller unplugged. Camera stopped. Plug it back in.", "warning")


def driving():
    s = Status("ptz_joystick.log")
    s.driving(HOST)
    return s


class BeforeDrivingTest(unittest.TestCase):
    def test_starts_yellow_with_the_app_name_in_the_hover_text(self):
        s = Status("ptz_joystick.log")
        self.assertEqual((s.color, s.text), (YELLOW, "Starting…"))
        self.assertEqual(s.tooltip, "ptz_joystick: Starting…")

    def test_waiting_for_camera_says_why(self):
        s = Status("ptz_joystick.log")
        s.waiting_for_camera(HOST, "camera rejected the login (401): check user in ptz_joystick.toml and PTZ_PASSWORD")
        self.assertEqual(s.color, YELLOW)
        self.assertEqual(s.text, f"Waiting for camera at {HOST}: camera rejected the login (401): check user in "
                                 "ptz_joystick.toml and PTZ_PASSWORD")

    def test_waiting_for_camera_before_any_warning(self):
        s = Status("ptz_joystick.log")
        s.waiting_for_camera(HOST, "")
        self.assertEqual(s.text, f"Waiting for camera at {HOST}")

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

    def test_no_controller_shows_the_factory_message(self):
        s = Status("ptz_joystick.log")
        s.no_controller("No controller found. Check that it shows in joy.cpl.")
        self.assertEqual((s.color, s.text), (YELLOW, "No controller found. Check that it shows in joy.cpl."))

    def test_controller_and_camera_news_before_driving_is_ignored(self):
        s = Status("ptz_joystick.log")
        s.waiting_for_stick()
        self.assertIsNone(s.controller(False))
        s.camera(False, "timed out")
        self.assertEqual(s.text, "Move the left stick to start")


class DrivingTest(unittest.TestCase):
    def test_driving_is_green(self):
        s = driving()
        self.assertEqual((s.color, s.text), (GREEN, f"Driving {HOST}"))

    def test_unplugged_controller_pops_up_once_per_unplug(self):
        s = driving()
        self.assertEqual(s.controller(False), UNPLUGGED)
        self.assertEqual((s.color, s.text), (YELLOW, "Controller unplugged: plug it back in"))
        self.assertIsNone(s.controller(False))
        self.assertIsNone(s.controller(True))
        self.assertEqual(s.color, GREEN)
        self.assertEqual(s.controller(False), UNPLUGGED)    # unplugged again: pops up again

    def test_camera_drop_changes_the_icon_only(self):
        s = driving()
        s.camera(False, "camera unreachable: timed out")
        self.assertEqual((s.color, s.text), (YELLOW, "Camera not answering: camera unreachable: timed out"))
        s.camera(True, "camera unreachable: timed out")
        self.assertEqual((s.color, s.text), (GREEN, f"Driving {HOST}"))

    def test_unplugged_controller_wins_over_a_silent_camera(self):
        s = driving()
        s.camera(False, "timed out")
        s.controller(False)
        self.assertEqual(s.text, "Controller unplugged: plug it back in")
        s.controller(True)
        self.assertEqual(s.text, "Camera not answering: timed out")


class StoppedTest(unittest.TestCase):
    def test_red_pops_up_every_time(self):
        s = driving()
        crash = "Crashed: RuntimeError('boom'). See the log."
        self.assertEqual(s.stopped(crash), Popup(crash, "error"))
        self.assertEqual((s.color, s.text), (RED, crash))
        self.assertEqual(s.stopped("again"), Popup("again", "error"))
        self.assertIsNone(s.controller(False))              # a stopped session drives nothing

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
