import unittest
from unittest import mock

from ptz_joystick.windows import focus

ZAO, OTHER = 7, 8
PROCS = {ZAO: (1, "Zao Virtual Cabin.exe"), OTHER: (1, "notepad.exe")}


class AppInFrontTest(unittest.TestCase):
    def setUp(self):
        self.app = focus.AppInFront("zao virtual cabin.exe")

    def in_front(self, pid, procs=PROCS):
        """in_front() with a window of process pid in front."""
        with mock.patch.object(focus, "_foreground", return_value=(100, pid)), \
                mock.patch.object(focus, "_processes", return_value=procs) as processes:
            return self.app.in_front(), processes.call_count

    def test_the_app_in_front_ignoring_case(self):
        self.assertTrue(self.in_front(ZAO)[0])

    def test_another_app_in_front(self):
        self.assertFalse(self.in_front(OTHER)[0])

    def test_no_window_or_a_gone_process(self):
        self.assertFalse(self.in_front(0)[0])
        self.assertFalse(self.in_front(999)[0])

    def test_snapshots_only_when_the_front_process_changes(self):
        self.assertEqual(self.in_front(ZAO), (True, 1))
        self.assertEqual(self.in_front(ZAO), (True, 0))
        self.assertEqual(self.in_front(OTHER), (False, 1))


if __name__ == "__main__":
    unittest.main()
