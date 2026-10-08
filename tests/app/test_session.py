import logging
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from ptz_joystick import config
from ptz_joystick.app import session
from ptz_joystick.app.registry import CAMERAS, CONTROLLERS, CameraType
from ptz_joystick.cameras import ptzoptics
from ptz_joystick.core.commands import PanTilt, Zoom
from tests.fakes import (
    RecordingCamera,
    ScriptedController,
    SetsStop,
    moving,
    reset_logging,
)

HOST = config.Settings().host
NO_PAD = "No controller found. Check that it shows in joy.cpl."
STOPS = {PanTilt: PanTilt(0, 0), Zoom: Zoom(0)}


class FlakyCamera(RecordingCamera):
    """Answers from a script (True = took it), then `then`. Logs why it refused, like a real adapter."""

    def __init__(self, *answers, then=True):
        super().__init__()
        self.answers, self.then = list(answers), then

    def send(self, cmd):
        super().send(cmd)
        ok = self.answers.pop(0) if self.answers else self.then
        if not ok:
            logging.getLogger("ptz_joystick.cameras.fake").warning("camera unreachable: timed out")
        return ok


def _recorder(name):
    def record(self, *args):
        self.calls.append((name, *args))
    return record


class RecordingReport:
    """A session's report, as tuples: ("driving", host), ("camera", ok, why), ..."""

    def __init__(self):
        self.calls: list[tuple] = []

    log_to = _recorder("log_to")
    waiting_for_camera = _recorder("waiting_for_camera")
    waiting_for_stick = _recorder("waiting_for_stick")
    stick_prompt = _recorder("stick_prompt")
    no_controller = _recorder("no_controller")
    driving = _recorder("driving")
    controller = _recorder("controller")
    camera = _recorder("camera")
    stopped = _recorder("stopped")
    update = _recorder("update")


def wait_until(condition, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("timed out")
        time.sleep(0.01)


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(tempfile.TemporaryDirectory())) / config.FILE_NAME
        self.addCleanup(reset_logging)          # before the folder is deleted: cleanups go last-in, first-out
        self.enterContext(mock.patch.dict(os.environ, {"PTZ_PASSWORD": "pw"}))
        self.enterContext(mock.patch.object(session, "user_env", return_value=None))   # never the real registry
        self.report, self.stop, self.camera = RecordingReport(), threading.Event(), FlakyCamera()
        self.enterContext(mock.patch.dict(CAMERAS, {"ptzoptics": CameraType(lambda s: self.camera,
                                                                            ptzoptics.TOP_SPEEDS)}))
        self.controllers: list[Any] = [SetsStop(self.stop, moving(), moving())]   # the factory's answers, in turn
        self.enterContext(mock.patch.dict(CONTROLLERS, {"winmm": self.factory}))

    def factory(self, s):
        answer = self.controllers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def run_session(self, keyboard=False, **kw):
        with self.assertLogs("ptz_joystick", "INFO") as logs:      # keeps the run's log lines out of the output
            session.run_session(self.path, keyboard, self.stop, self.report, retry_every=0.01, **kw)
        return logs

    def names(self):
        """The calls in order, without the sender's camera news: that comes from its own thread, at any time."""
        return [c[0] for c in self.report.calls if c[0] != "camera"]

    def test_drives_once_the_camera_answers(self):
        self.camera.answers = [False, False]
        self.run_session()
        self.assertEqual(self.names(), ["log_to", "waiting_for_camera", "waiting_for_camera", "waiting_for_stick",
                                        "driving"])
        self.assertIn(("waiting_for_camera", HOST, "camera unreachable: timed out"), self.report.calls)
        self.assertEqual({type(c): c for c in self.camera.calls}, STOPS)

    def test_missing_password_is_red_with_the_fix(self):
        del os.environ["PTZ_PASSWORD"]
        self.run_session()
        [(name, message)] = self.report.calls
        self.assertEqual(name, "stopped")
        self.assertIn("Set the camera password first", message)

    def test_a_password_set_with_setx_after_start_is_used(self):
        del os.environ["PTZ_PASSWORD"]
        with mock.patch.object(session, "user_env", return_value="from-setx"):
            self.run_session()
        self.assertIn("driving", self.names())
        self.assertEqual(os.environ["PTZ_PASSWORD"], "from-setx")

    def test_keyboard_is_red_in_the_tray(self):
        self.run_session(keyboard=True)
        self.assertEqual(self.report.calls[-1], ("stopped", session.KEYBOARD_IN_TRAY))
        self.assertEqual(self.camera.calls, [])

    def test_no_controller_waits_and_tries_again(self):
        self.controllers.insert(0, SystemExit(NO_PAD))
        self.run_session()
        self.assertEqual(self.names(), ["log_to", "waiting_for_stick", "no_controller", "waiting_for_stick", "driving"])
        self.assertIn(("no_controller", NO_PAD), self.report.calls)

    def test_a_crash_while_driving_stops_the_camera_and_goes_red(self):
        class Breaks(ScriptedController):
            def read(self):
                if not self.readings:
                    raise RuntimeError("boom")
                return super().read()

        self.controllers = [Breaks(moving(x=1), moving(x=1))]
        logs = self.run_session()
        self.assertEqual(self.report.calls[-1], ("stopped", "Crashed: RuntimeError('boom'). See the log."))
        self.assertTrue(any(line.startswith("CRITICAL") and "boom" in line for line in logs.output))
        self.assertEqual({type(c): c for c in self.camera.calls}, STOPS)

    def test_camera_drops_while_driving_come_with_the_reason(self):
        self.camera.answers = [True, False]             # takes the startup stop, refuses the first move
        self.controllers = [SetsStop(self.stop, *[moving(x=1)] * 20)]
        self.run_session()
        self.assertIn(("camera", False, "camera unreachable: timed out"), self.report.calls)

    def test_stop_while_waiting_for_the_camera_ends_the_session_at_once(self):
        self.camera.then = False
        t = threading.Thread(target=session.run_session, args=(self.path, False, self.stop, self.report),
                             kwargs={"retry_every": 5.0})
        with self.assertLogs("ptz_joystick", "INFO"):
            t.start()
            wait_until(lambda: "waiting_for_camera" in self.names())
            self.stop.set()
            t.join(0.2)
        self.assertFalse(t.is_alive())
        self.assertNotIn("driving", self.names())

    def test_stopped_while_waiting_for_the_stick_never_drives(self):
        moved = threading.Event()

        def waits_for_a_stick_move(s):
            moved.wait(2)
            return SetsStop(self.stop, moving())

        self.enterContext(mock.patch.dict(CONTROLLERS, {"winmm": waits_for_a_stick_move}))
        t = threading.Thread(target=session.run_session, args=(self.path, False, self.stop, self.report))
        with self.assertLogs("ptz_joystick", "INFO"):
            t.start()
            wait_until(lambda: "waiting_for_stick" in self.names())
            self.stop.set()                             # Restart or Quit while discover() waits...
            moved.set()                                 # ...then someone moves the stick
            t.join(2)
        self.assertFalse(t.is_alive())
        self.assertNotIn("driving", self.names())
        self.assertEqual(self.camera.calls, [PanTilt(0, 0)])     # only the startup check

    def test_stick_prompt_after_a_while_without_a_stick_move(self):
        def slow_stick_move(s):
            time.sleep(0.2)
            return SetsStop(self.stop, moving())

        self.enterContext(mock.patch.dict(CONTROLLERS, {"winmm": slow_stick_move}))
        self.enterContext(mock.patch.object(session, "STICK_PROMPT_AFTER", 0.02))
        self.run_session()
        self.assertEqual(self.names(), ["log_to", "waiting_for_stick", "stick_prompt", "driving"])

    def test_github_is_asked_only_when_the_tray_says_so(self):
        for check_updates in (True, False):
            self.controllers = [SetsStop(self.stop, moving())]
            self.stop.clear()
            with self.subTest(check_updates=check_updates), \
                    mock.patch.object(session.updates, "check_in_background") as check:
                self.run_session(check_updates=check_updates)
                self.assertEqual(check.called, check_updates)


if __name__ == "__main__":
    unittest.main()
