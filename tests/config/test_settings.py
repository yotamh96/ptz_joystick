import unittest
from typing import Any

from ptz_joystick.config import Settings
from ptz_joystick.core.commands import PanTilt


class ValidationTest(unittest.TestCase):
    def test_defaults_are_valid(self):
        Settings()

    def test_bad_values_named_in_error(self):
        cases: list[tuple[dict[str, Any], str]] = [
            ({"full_speed_at": 0.15}, "full_speed_at"),      # == deadzone: would divide by zero
            ({"deadzone": 0.8}, "deadzone"),                 # above full_speed_at
            ({"full_speed_at": 1.2}, "full_speed_at"),
            ({"pan_axis": "x"}, "pan_axis"),
            ({"zoom_axis": "W"}, "zoom_axis"),
            ({"tilt_max": 0}, "tilt_max"),
            ({"zoom_max": 2.5}, "zoom_max"),                 # each camera's own top: app.checks.check_types
            ({"timeout": 0}, "timeout"),
            ({"timeout": 2.5}, "timeout"),                   # would eat the 3 s shutdown window
            ({"timeout": float("inf")}, "timeout"),
            ({"save_hold_seconds": -1}, "save_hold_seconds"),
            ({"save_hold_seconds": 11}, "save_hold_seconds"),
            ({"host": "192.168.77.3"}, "host"),              # missing http://
            ({"buttons": {0: 1}}, "buttons"),                # not a command
            ({"buttons": {0: PanTilt(1, 0)}}, "buttons"),    # a button-started move would never stop
        ]
        for bad, word in cases:
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, word):
                Settings(**bad)


if __name__ == "__main__":
    unittest.main()
