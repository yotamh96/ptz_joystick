import threading
import time
import unittest
from dataclasses import dataclass

from ptz_joystick.core.commands import PanTilt, Preset, Zoom
from ptz_joystick.core.sender import CommandSender


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


class RaisingCamera(FakeCamera):
    """An adapter that forgot to turn its network errors into False."""

    def __init__(self, raise_first=10**6, error=TimeoutError):
        super().__init__()
        self.raise_first, self.error = raise_first, error

    def send(self, cmd):
        with self.lock:
            self.calls.append(cmd)
            if len(self.calls) <= self.raise_first:
                raise self.error("timed out")
            return True


def wait_idle(s, timeout=2):
    """Wait until the camera took everything pending (drain_with would drop it instead)."""
    with s._cv:
        return s._cv.wait_for(lambda: not s._pending, timeout)


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
        with self.assertLogs("ptz_joystick.core.sender", "ERROR") as logs:
            s.send(Preset(9))
            self.assertTrue(tried.wait(1))
            self.assertTrue(s.drain_with([PanTilt(0, 0)], timeout=1))
        self.assertEqual(cam.calls[-1], PanTilt(0, 0))
        self.assertIn("Preset(number=9)", logs.output[0])

    def test_refused_command_does_not_block_stop(self):
        class NoPresets(FakeCamera):          # e.g. camera answers 500 to poscall
            def send(self, cmd):
                return super().send(cmd) and not isinstance(cmd, Preset)

        cam = NoPresets()
        s = CommandSender(cam, backoff=0.01)
        s.send(PanTilt(24, 0))
        self.assertTrue(wait_idle(s))
        s.send(Preset(3))
        s.send(PanTilt(0, 0))
        deadline = time.time() + 1
        while PanTilt(0, 0) not in cam.calls and time.time() < deadline:
            time.sleep(0.01)
        self.assertIn(PanTilt(0, 0), cam.calls)

    def test_refused_preset_dropped_after_3_tries(self):
        cam = FakeCamera(fail_first=10**6)
        s = CommandSender(cam, backoff=0.01)
        with self.assertLogs("ptz_joystick.core.sender", "WARNING") as logs:
            s.send(Preset(3))
            self.assertTrue(wait_idle(s, timeout=1))
        self.assertEqual(cam.calls, [Preset(3)] * 3)
        self.assertIn("Preset(number=3)", logs.output[-1])

    def test_refused_moves_keep_retrying_with_backoff(self):
        cam = FakeCamera(fail_first=10**6)
        s = CommandSender(cam, backoff=0.05)
        s.send(PanTilt(5, 0))
        time.sleep(0.3)
        self.assertGreater(len(cam.calls), 3)          # never gives up on a move (it is current state)
        self.assertLess(len(cam.calls), 12)            # but backs off instead of hammering the camera
        self.assertEqual(s._pending, {PanTilt: PanTilt(5, 0)})

    def test_nothing_sent_after_drain(self):
        cam = FakeCamera()
        s = CommandSender(cam, backoff=0.01)
        self.assertTrue(s.drain_with([PanTilt(0, 0)], timeout=1))
        s.send(PanTilt(24, 0))                         # main loop still running while the console closes
        time.sleep(0.05)
        self.assertEqual(cam.calls, [PanTilt(0, 0)])

    def test_drain_gives_up_on_dead_camera(self):
        s = CommandSender(FakeCamera(fail_first=10**6), backoff=0.01)
        self.assertFalse(s.drain_with([PanTilt(0, 0)], timeout=0.2))

    def test_adapter_error_is_retried_not_dropped(self):
        cam = RaisingCamera(raise_first=2, error=OSError)
        s = CommandSender(cam, backoff=0.01)
        with self.assertLogs("ptz_joystick.core.sender", "ERROR") as logs:
            self.assertTrue(s.drain_with([PanTilt(0, 0)], timeout=1))
        self.assertEqual(cam.calls, [PanTilt(0, 0)] * 3)
        self.assertEqual(len(logs.records), 1)          # traceback once, not on every retry

    def test_adapter_error_on_stop_is_not_reported_as_stopped(self):
        cam = RaisingCamera()
        s = CommandSender(cam, backoff=0.01)
        with self.assertLogs("ptz_joystick.core.sender", "ERROR") as logs:
            self.assertFalse(s.drain_with([PanTilt(0, 0), Zoom(0)], timeout=0.3))
        self.assertGreater(len(cam.calls), 2)            # stops kept retrying
        self.assertEqual(len(logs.records), 2)          # one traceback per command

    def test_refused_unhashable_command_does_not_kill_sender(self):
        @dataclass(frozen=True)
        class Odd:                                     # frozen, but the list makes it unhashable
            items: list

        class NoOdd(FakeCamera):
            def send(self, cmd):
                return super().send(cmd) and not isinstance(cmd, Odd)

        cam = NoOdd()
        s = CommandSender(cam, backoff=0.01)
        with self.assertLogs("ptz_joystick.core.sender", "WARNING"):
            s.send(Odd([1]))                           # type: ignore[arg-type]  # deliberately not a Command
            self.assertTrue(wait_idle(s, timeout=1))
        self.assertTrue(s.drain_with([PanTilt(0, 0)], timeout=1))
        self.assertEqual(cam.calls[-1], PanTilt(0, 0))

    def test_new_action_type_gives_up_without_sender_change(self):
        @dataclass(frozen=True)
        class Home:                                    # a button action the sender has never heard of
            pass

        cam = FakeCamera(fail_first=10**6)
        s = CommandSender(cam, backoff=0.01)
        with self.assertLogs("ptz_joystick.core.sender", "WARNING") as logs:
            s.send(Home())                             # type: ignore[arg-type]  # deliberately not a Command
            self.assertTrue(wait_idle(s, timeout=1))
        self.assertEqual(cam.calls, [Home()] * 3)
        self.assertIn("gave up", logs.output[-1])

    def test_stale_command_not_sent_after_drain(self):
        started, release = threading.Event(), threading.Event()

        class SlowFirst(FakeCamera):
            def send(self, cmd):
                if not started.is_set():
                    started.set()
                    release.wait(1)
                return super().send(cmd)

        cam = SlowFirst()
        s = CommandSender(cam, backoff=0.01)
        with s._cv:                                     # both go out in one batch
            s.send(PanTilt(5, 0))
            s.send(Zoom(3))
        self.assertTrue(started.wait(1))               # PanTilt(5, 0) is in flight...
        threading.Timer(0.05, release.set).start()     # ...when the console closes
        self.assertTrue(s.drain_with([PanTilt(0, 0), Zoom(0)], timeout=2))
        self.assertNotIn(Zoom(3), cam.calls)
        self.assertEqual(cam.calls[-2:], [PanTilt(0, 0), Zoom(0)])


if __name__ == "__main__":
    unittest.main()
