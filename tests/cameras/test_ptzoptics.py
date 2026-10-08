import unittest
from types import SimpleNamespace
from unittest import mock

import requests

from ptz_joystick.cameras import ptzoptics
from ptz_joystick.cameras.ptzoptics import PtzOpticsCamera, to_query
from ptz_joystick.core.commands import PanTilt, Preset, SavePreset, Tracking, Zoom
from tests import contracts


class ToQueryTest(unittest.TestCase):
    def test_every_command_type_translates(self):
        for cmd in contracts.EXAMPLES:
            with self.subTest(cmd=cmd):
                self.assertTrue(to_query(cmd).startswith(("ptzctrl.cgi?ptzcmd&", "param.cgi?")))

    def test_pantilt(self):
        self.assertEqual(to_query(PanTilt(0, 0)), "ptzctrl.cgi?ptzcmd&ptzstop&0&0")
        self.assertEqual(to_query(PanTilt(-24, 20)), "ptzctrl.cgi?ptzcmd&leftup&24&20")
        self.assertEqual(to_query(PanTilt(10, 0)), "ptzctrl.cgi?ptzcmd&right&10&1")    # idle axis still needs speed 1
        self.assertEqual(to_query(PanTilt(0, -5)), "ptzctrl.cgi?ptzcmd&down&1&5")
        self.assertEqual(to_query(PanTilt(3, -4)), "ptzctrl.cgi?ptzcmd&rightdown&3&4")

    def test_zoom(self):
        self.assertEqual(to_query(Zoom(0)), "ptzctrl.cgi?ptzcmd&zoomstop&0")
        self.assertEqual(to_query(Zoom(7)), "ptzctrl.cgi?ptzcmd&zoomin&7")
        self.assertEqual(to_query(Zoom(-3)), "ptzctrl.cgi?ptzcmd&zoomout&3")

    def test_preset(self):
        self.assertEqual(to_query(Preset(4)), "ptzctrl.cgi?ptzcmd&poscall&4")
        self.assertEqual(to_query(SavePreset(4)), "ptzctrl.cgi?ptzcmd&posset&4")

    def test_tracking_uses_param_cgi(self):
        self.assertEqual(to_query(Tracking(True)), "param.cgi?set_overlay&autotracking&on")
        self.assertEqual(to_query(Tracking(False)), "param.cgi?set_overlay&autotracking&off")

    def test_full_url(self):
        cam = camera_answering(200, 200)
        cam.send(PanTilt(0, 0))
        cam.send(Tracking(True))
        urls = [c.args[0] for c in cam._session.get.call_args_list]
        self.assertEqual(urls, ["http://cam/cgi-bin/ptzctrl.cgi?ptzcmd&ptzstop&0&0",
                                "http://cam/cgi-bin/param.cgi?set_overlay&autotracking&on"])


def camera_answering(*answers):
    """Camera whose HTTP replies are the given status codes / exceptions, in order."""
    session = mock.Mock()
    session.get.side_effect = [a if isinstance(a, Exception) else SimpleNamespace(status_code=a) for a in answers]
    return PtzOpticsCamera("http://cam", "admin", "pw", session=session)


class SendTest(contracts.CameraContract):
    top_speeds = ptzoptics.TOP_SPEEDS

    def make(self, up):
        session = mock.Mock()
        if up:
            session.get.return_value = SimpleNamespace(status_code=200)
        else:
            session.get.side_effect = requests.ConnectTimeout("timed out")
        return PtzOpticsCamera("http://cam", "admin", "pw", session=session)

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
