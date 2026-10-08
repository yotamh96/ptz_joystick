import unittest
from unittest import mock

import ptz_joystick.app.main as app_main


class AlreadyRunningTest(unittest.TestCase):
    def test_second_copy_stops_with_the_fix(self):
        with mock.patch.object(app_main.single_instance, "claim", return_value=False), \
                self.assertRaisesRegex(SystemExit, "already running. Quit it first"):
            app_main.main([])


if __name__ == "__main__":
    unittest.main()
