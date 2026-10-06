import os
import unittest
from unittest import mock

from ptz_joystick import config
from ptz_joystick.config import Settings


class ValidationTest(unittest.TestCase):
    def test_defaults_are_valid(self):
        Settings()

    def test_bad_values_named_in_error(self):
        for bad, word in [
            (dict(full_speed_at=0.15), "full_speed_at"),      # == deadzone: would divide by zero
            (dict(deadzone=0.8), "deadzone"),                 # above full_speed_at
            (dict(full_speed_at=1.2), "full_speed_at"),
            (dict(pan_axis="x"), "pan_axis"),
            (dict(zoom_axis="W"), "zoom_axis"),
            (dict(tilt_max=0), "tilt_max"),
            (dict(timeout=0), "timeout"),
            (dict(host="192.168.77.3"), "host"),              # missing http://
            (dict(buttons={0: 1}), "buttons"),                # not a command
        ]:
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, word):
                Settings(**bad)

    def test_load_turns_bad_config_into_clean_exit(self):
        with mock.patch.dict(os.environ, {"PTZ_PASSWORD": "x"}), \
                mock.patch.object(config, "Settings", side_effect=ValueError("deadzone must be ...")), \
                self.assertRaisesRegex(SystemExit, "config.py: deadzone must be"):
            config.load()


if __name__ == "__main__":
    unittest.main()
