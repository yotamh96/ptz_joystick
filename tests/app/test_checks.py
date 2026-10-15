import unittest
from pathlib import Path
from typing import Any

from ptz_joystick.app.checks import check_axes, check_camera, check_types
from ptz_joystick.app.registry import CAMERAS
from ptz_joystick.config import Settings
from ptz_joystick.controllers import ControllerState
from ptz_joystick.core.commands import PanTilt
from ptz_joystick.core.problem import Problem
from tests.fakes import RecordingCamera, ScriptedController, moving


class CheckCameraTest(unittest.TestCase):
    def test_camera_that_refuses_stops_startup_with_its_reason(self):
        class Refusing(RecordingCamera):
            def send(self, cmd):
                super().send(cmd)
                self.problem = Problem("The camera refused the login", fix="Check user and PTZ_PASSWORD")
                return False

        cam = Refusing()
        with self.assertRaises(Problem) as cm:
            check_camera(cam, "http://cam", Path("ptz_joystick.toml"))
        self.assertIs(cm.exception, cam.problem)
        self.assertEqual(cam.calls, [PanTilt(0, 0)])     # probe is a harmless stop

    def test_a_camera_that_gives_no_reason_still_names_the_checks(self):
        class Silent(RecordingCamera):
            def send(self, cmd):
                return False

        with self.assertRaises(Problem) as cm:
            check_camera(Silent(), "http://cam", Path("ptz_joystick.toml"))
        self.assertEqual(cm.exception.text(), "The camera at http://cam didn't answer. Check host in "
                                              "ptz_joystick.toml, the network, and PTZ_PASSWORD.")

    def test_camera_that_answers_passes(self):
        check_camera(RecordingCamera(), "http://cam", Path("ptz_joystick.toml"))


class CheckTypesTest(unittest.TestCase):
    PATH = Path("ptz_joystick.toml")

    def test_defaults_pass(self):
        check_types(Settings(), self.PATH)
        check_types(Settings(controller="keyboard"), self.PATH)

    def test_unknown_type_names_the_setting_and_the_choices(self):
        cases: list[tuple[dict[str, Any], str]] = [
            ({"camera": "sony"}, "camera must be one of ptzoptics, got 'sony'"),
            ({"controller": "xbox"}, "controller must be one of winmm, keyboard, got 'xbox'")]
        for bad, words in cases:
            with self.subTest(bad=bad), self.assertRaisesRegex(Problem, words):
                check_types(Settings(**bad), self.PATH)

    def test_speed_above_the_camera_top_is_refused(self):
        tops: dict[str, Any] = CAMERAS["ptzoptics"].top_speeds
        check_types(Settings(**tops), self.PATH)                # the top itself is fine
        for name, top in tops.items():
            with self.subTest(name=name), self.assertRaisesRegex(Problem, f"{name} can be at most {top}"):
                check_types(Settings(**{**tops, name: top + 1}), self.PATH)


class CheckAxesTest(unittest.TestCase):
    PATH = Path("ptz_joystick.toml")

    def test_axes_the_settings_name_pass(self):
        check_axes(ScriptedController(moving()), Settings(), self.PATH)

    def test_missing_axis_is_named(self):
        no_r = ScriptedController(ControllerState({"X": 0.0, "Y": 0.0}, 0))
        with self.assertRaisesRegex(Problem, r"no axis R \(it has X, Y\)"):
            check_axes(no_r, Settings(), self.PATH)

    def test_unplugged_at_start_is_not_checked(self):
        check_axes(ScriptedController(None), Settings(), self.PATH)


if __name__ == "__main__":
    unittest.main()
