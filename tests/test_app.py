import logging
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ptz_joystick.app import check_camera, run, setup_logging
from ptz_joystick.cameras import Camera
from ptz_joystick.cameras.ptzoptics import PtzOpticsCamera
from ptz_joystick.commands import PanTilt, Zoom
from ptz_joystick.config import Settings
from ptz_joystick.controllers import Controller, ControllerState
from ptz_joystick.controllers.winmm import WinmmController
from ptz_joystick.sender import CommandSender


class ScriptedController:
    """Plays back readings, then raises KeyboardInterrupt like Ctrl+C."""

    def __init__(self, *readings):
        self.readings = list(readings)

    def read(self):
        if not self.readings:
            raise KeyboardInterrupt
        return self.readings.pop(0)


class RecordingCamera:
    def __init__(self):
        self.calls = []

    def send(self, cmd):
        self.calls.append(cmd)
        return True


def moving(x=0.0, r=0.0):
    return ControllerState({"X": x, "Y": 0.0, "R": r}, 0)


class InterfacesTest(unittest.TestCase):
    def test_adapters_fit_the_ports(self):
        self.assertTrue(issubclass(PtzOpticsCamera, Camera))
        self.assertTrue(issubclass(WinmmController, Controller))
        self.assertTrue(issubclass(RecordingCamera, Camera))
        self.assertTrue(issubclass(ScriptedController, Controller))


class RunTest(unittest.TestCase):
    def test_ctrl_c_mid_pan_stops_camera(self):
        cam = RecordingCamera()
        with self.assertRaises(KeyboardInterrupt):
            run(Settings(), ScriptedController(moving(x=1), moving(x=1, r=-1)), CommandSender(cam), period=0.01)
        last = {type(c): c for c in cam.calls}
        self.assertEqual(last, {PanTilt: PanTilt(0, 0), Zoom: Zoom(0)})

    def test_unplug_mid_pan_stops_camera_and_warns(self):
        cam = RecordingCamera()
        sender = CommandSender(cam)
        with self.assertLogs("ptz_joystick.app", "WARNING") as logs, self.assertRaises(KeyboardInterrupt):
            run(Settings(), ScriptedController(moving(x=1), None, moving(x=1)), sender, period=0.01)
        self.assertIn("Controller lost", logs.output[0])
        self.assertIn(PanTilt(0, 0), cam.calls[cam.calls.index(PanTilt(24, 0)) + 1:])

    def test_debug_logs_axes(self):
        s = Settings(debug=True)
        with self.assertLogs("ptz_joystick.app", "DEBUG") as logs, self.assertRaises(KeyboardInterrupt):
            run(s, ScriptedController(moving(x=0.5)), CommandSender(RecordingCamera()), period=0.01)
        self.assertTrue(any("'X': 0.5" in line for line in logs.output))


class CheckCameraTest(unittest.TestCase):
    def test_camera_that_refuses_stops_startup(self):
        class Refusing(RecordingCamera):
            def send(self, cmd):
                super().send(cmd)
                return False

        cam = Refusing()
        with self.assertRaisesRegex(SystemExit, "Camera"):
            check_camera(cam, "http://cam", Path("ptz_joystick.toml"))
        self.assertEqual(cam.calls, [PanTilt(0, 0)])     # probe is a harmless stop

    def test_camera_that_answers_passes(self):
        check_camera(RecordingCamera(), "http://cam", Path("ptz_joystick.toml"))


class CrashTest(unittest.TestCase):
    def test_crash_reason_goes_to_log(self):
        with mock.patch("ptz_joystick.app.main", side_effect=RuntimeError("boom")),                 self.assertLogs("ptz_joystick", "CRITICAL") as logs, self.assertRaises(SystemExit):
            runpy.run_module("ptz_joystick", run_name="__main__")
        self.assertIn("boom", logs.output[0])

    def test_ctrl_c_and_clean_exit_stay_quiet(self):
        for exc in (KeyboardInterrupt(), SystemExit("No controller found.")):
            with self.subTest(exc=exc), mock.patch("ptz_joystick.app.main", side_effect=exc),                     self.assertNoLogs("ptz_joystick", "CRITICAL"):
                try:
                    runpy.run_module("ptz_joystick", run_name="__main__")
                except SystemExit as e:
                    self.assertEqual(str(e), "No controller found.")


class SetupLoggingTest(unittest.TestCase):
    def test_writes_timestamped_lines_to_log_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ptz.log")
            setup_logging(Settings(log_file=path))
            try:
                logging.getLogger("ptz_joystick.test").info("hello camera")
            finally:
                for h in logging.getLogger().handlers[:]:
                    h.close()
                    logging.getLogger().removeHandler(h)
            with open(path, encoding="utf-8") as f:
                line = f.read()
        self.assertRegex(line, r"^\d\d:\d\d:\d\d INFO +hello camera")

    def test_unwritable_log_file_falls_back_to_terminal(self):
        with tempfile.TemporaryDirectory() as d:          # a folder can't be opened as a log file
            with self.assertLogs("ptz_joystick.app", "WARNING") as logs:
                setup_logging(Settings(log_file=d))
            for h in logging.getLogger().handlers[:]:
                logging.getLogger().removeHandler(h)
        self.assertIn("terminal only", logs.output[0])

    def test_no_file_when_log_file_empty(self):
        setup_logging(Settings(log_file=""))
        try:
            self.assertFalse(any(isinstance(h, logging.FileHandler) for h in logging.getLogger().handlers))
        finally:
            for h in logging.getLogger().handlers[:]:
                logging.getLogger().removeHandler(h)


if __name__ == "__main__":
    unittest.main()
