import threading
import unittest

from ptz_joystick.app.loop import run
from ptz_joystick.config import Settings
from ptz_joystick.controllers import ControllerState
from ptz_joystick.core.commands import PanTilt, SavePreset, Zoom
from ptz_joystick.core.sender import CommandSender
from tests.fakes import RecordingCamera, ScriptedController, SetsStop, moving


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
        with self.assertLogs("ptz_joystick.app.loop", "WARNING") as logs, self.assertRaises(KeyboardInterrupt):
            run(Settings(), ScriptedController(moving(x=1), None, moving(x=1)), sender, period=0.01)
        self.assertIn("Controller lost", logs.output[0])
        self.assertIn(PanTilt(0, 0), cam.calls[cam.calls.index(PanTilt(24, 0)) + 1:])

    def test_holding_preset_button_saves_and_says_so(self):
        cam = RecordingCamera()
        held = ControllerState({"X": 0.0, "Y": 0.0, "R": 0.0}, 0b1)        # button 1 = preset 1
        with self.assertLogs("ptz_joystick.app.loop", "INFO") as logs, self.assertRaises(KeyboardInterrupt):
            run(Settings(save_hold_seconds=0.03), ScriptedController(moving(), *[held] * 10), CommandSender(cam),
                period=0.01)
        self.assertIn(SavePreset(1), cam.calls)
        self.assertTrue(any("Saving the current position as preset 1" in line for line in logs.output))

    def test_debug_logs_axes(self):
        s = Settings(debug=True)
        with self.assertLogs("ptz_joystick.app.loop", "DEBUG") as logs, self.assertRaises(KeyboardInterrupt):
            run(s, ScriptedController(moving(x=0.5)), CommandSender(RecordingCamera()), period=0.01)
        self.assertTrue(any("'X': 0.5" in line for line in logs.output))

    def test_stop_ends_the_loop_with_the_camera_stopped(self):
        cam, stop = RecordingCamera(), threading.Event()
        with self.assertLogs("ptz_joystick.app.loop", "INFO"):
            run(Settings(), SetsStop(stop, moving(x=1), moving(x=1)), CommandSender(cam), period=0.01, stop=stop)
        last = {type(c): c for c in cam.calls}
        self.assertEqual(last, {PanTilt: PanTilt(0, 0), Zoom: Zoom(0)})

    def test_reports_controller_lost_and_back_once_each(self):
        seen: list[bool] = []
        with self.assertLogs("ptz_joystick.app.loop", "INFO"), self.assertRaises(KeyboardInterrupt):
            run(Settings(), ScriptedController(moving(), None, None, moving()), CommandSender(RecordingCamera()),
                period=0.01, on_controller=seen.append)
        self.assertEqual(seen, [False, True])


if __name__ == "__main__":
    unittest.main()
