import threading
import time
import unittest

from ptz_joystick.commands import PanTilt, Preset, Zoom
from ptz_joystick.sender import CommandSender


class FakeCamera:
    """Answers like the real one: False = camera said 500 / timed out."""

    def __init__(self, fail_first=0, delay=0.0):
        self.calls, self.fail_first, self.delay = [], fail_first, delay
        self.lock = threading.Lock()

    def send(self, cmd):
        time.sleep(self.delay)
        with self.lock:
            self.calls.append(cmd)
            return len(self.calls) > self.fail_first


def wait_idle(s, timeout=2):
    """Wait until the camera took everything pending (drain_with would drop it instead)."""
    with s.cv:
        return s.cv.wait_for(lambda: not s.pending, timeout)


class SenderTest(unittest.TestCase):
    def test_retries_until_camera_accepts(self):
        cam = FakeCamera(fail_first=2)
        s = CommandSender(cam, backoff=0.01)
        s.send(PanTilt(5, 0))
        self.assertTrue(wait_idle(s))
        self.assertEqual(cam.calls, [PanTilt(5, 0)] * 3)

    def test_latest_per_type_wins(self):
        cam = FakeCamera(delay=0.05)
        s = CommandSender(cam, backoff=0.01)
        for pan in range(1, 11):
            s.send(PanTilt(pan, 0))
        s.send(Preset(1))
        self.assertTrue(wait_idle(s))
        self.assertLess(len(cam.calls), 11)               # stale moves were skipped
        self.assertIn(PanTilt(10, 0), cam.calls)
        self.assertIn(Preset(1), cam.calls)

    def test_stop_arrives_last(self):
        cam = FakeCamera(delay=0.02)
        s = CommandSender(cam, backoff=0.01)
        for pan in range(1, 20):
            s.send(PanTilt(pan, 0))
            s.send(Zoom(pan % 7 + 1))
        self.assertTrue(s.drain_with([PanTilt(0, 0), Zoom(0)], timeout=3))
        last = {type(c): c for c in cam.calls}
        self.assertEqual(last, {PanTilt: PanTilt(0, 0), Zoom: Zoom(0)})

    def test_untranslatable_command_does_not_kill_sender(self):
        tried = threading.Event()

        class PickyCamera(FakeCamera):
            def send(self, cmd):
                if isinstance(cmd, Preset):
                    tried.set()
                    raise TypeError("camera can't do that")
                return super().send(cmd)

        cam = PickyCamera()
        s = CommandSender(cam, backoff=0.01)
        with self.assertLogs("ptz_joystick.sender", "ERROR") as logs:
            s.send(Preset(9))
            self.assertTrue(tried.wait(1))
            self.assertTrue(s.drain_with([PanTilt(0, 0)], timeout=1))
        self.assertEqual(cam.calls[-1], PanTilt(0, 0))
        self.assertIn("Preset(number=9)", logs.output[0])

    def test_drain_gives_up_on_dead_camera(self):
        s = CommandSender(FakeCamera(fail_first=10**6), backoff=0.01)
        self.assertFalse(s.drain_with([PanTilt(0, 0)], timeout=0.2))


if __name__ == "__main__":
    unittest.main()
