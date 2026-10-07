import unittest
from types import SimpleNamespace
from typing import get_args
from unittest import mock

import requests

from ptz_joystick.cameras.ptzoptics import PtzOpticsCamera, to_query
from ptz_joystick.core.commands import Command, PanTilt, Preset, SavePreset, Zoom

EXAMPLES: list[Command] = [PanTilt(3, -4), Zoom(-3), Preset(4), SavePreset(4)]    # one of each command type


class ToQueryTest(unittest.TestCase):
    def test_every_command_type_translates(self):
        self.assertEqual({type(c) for c in EXAMPLES}, set(get_args(Command)), "new command type? add an example")
        for cmd in EXAMPLES:
            with self.subTest(cmd=cmd):
                self.assertTrue(to_query(cmd).startswith("ptzcmd&"))

    def test_pantilt(self):
        self.assertEqual(to_query(PanTilt(0, 0)), "ptzcmd&ptzstop&0&0")
        self.assertEqual(to_query(PanTilt(-24, 20)), "ptzcmd&leftup&24&20")
        self.assertEqual(to_query(PanTilt(10, 0)), "ptzcmd&right&10&1")    # idle axis still needs speed 1
        self.assertEqual(to_query(PanTilt(0, -5)), "ptzcmd&down&1&5")
        self.assertEqual(to_query(PanTilt(3, -4)), "ptzcmd&rightdown&3&4")

    def test_zoom(self):
        self.assertEqual(to_query(Zoom(0)), "ptzcmd&zoomstop&0")
        self.assertEqual(to_query(Zoom(7)), "ptzcmd&zoomin&7")
        self.assertEqual(to_query(Zoom(-3)), "ptzcmd&zoomout&3")

    def test_preset(self):
        self.assertEqual(to_query(Preset(4)), "ptzcmd&poscall&4")
        self.assertEqual(to_query(SavePreset(4)), "ptzcmd&posset&4")


def camera_answering(*answers):
    """Camera whose HTTP replies are the given status codes / exceptions, in order."""
    session = mock.Mock()
    session.get.side_effect = [a if isinstance(a, Exception) else SimpleNamespace(status_code=a) for a in answers]
    return PtzOpticsCamera("http://cam", "admin", "pw", session=session)


class SendTest(unittest.TestCase):
    def test_outage_logs_once_then_recovery(self):
        down = requests.ConnectTimeout("timed out")
        cam = camera_answering(down, down, down, 200)
        with self.assertLogs("ptz_joystick.cameras.ptzoptics", "INFO") as logs:
            results = [cam.send(PanTilt(0, 0)) for _ in range(4)]
        self.assertEqual(results, [False, False, False, True])
        self.assertEqual(len(logs.output), 2, logs.output)
        self.assertIn("unreachable", logs.output[0])
        self.assertIn("back", logs.output[1])

    def test_wrong_password_says_so(self):
        cam = camera_answering(401)
        with self.assertLogs("ptz_joystick.cameras.ptzoptics", "WARNING") as logs:
            self.assertFalse(cam.send(PanTilt(0, 0)))
        self.assertIn("PTZ_PASSWORD", logs.output[0])

    def test_new_kind_of_failure_is_logged(self):
        cam = camera_answering(requests.ConnectTimeout("x"), 500)
        with self.assertLogs("ptz_joystick.cameras.ptzoptics", "WARNING") as logs:
            cam.send(PanTilt(0, 0))
            cam.send(PanTilt(0, 0))
        self.assertEqual(len(logs.output), 2)
        self.assertIn("500", logs.output[1])


if __name__ == "__main__":
    unittest.main()
