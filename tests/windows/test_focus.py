import unittest
from unittest import mock

from ptz_joystick.windows import focus

CONSOLE, TERMINAL_PID = 100, 5        # our console window, and one of our parent processes (say VS Code)


class OwnWindowTest(unittest.TestCase):
    def in_front(self, hwnd, pid):
        """in_front() with this window, owned by this process, in front."""
        with mock.patch.object(focus, "_console_windows", return_value={CONSOLE}), \
                mock.patch.object(focus, "_ancestor_pids", return_value={TERMINAL_PID}):
            own = focus.OwnWindow()
        with mock.patch.object(focus, "_foreground", return_value=(hwnd, pid)):
            return own.in_front()

    def test_our_console_window(self):
        self.assertTrue(self.in_front(CONSOLE, 999))

    def test_a_window_of_a_parent_process(self):
        self.assertTrue(self.in_front(None, TERMINAL_PID))

    def test_another_window(self):
        self.assertFalse(self.in_front(200, 999))


class AncestorPidsTest(unittest.TestCase):
    def ancestors(self, procs, me):
        with mock.patch.object(focus, "_processes", return_value=procs), \
                mock.patch.object(focus.os, "getpid", return_value=me):
            return focus._ancestor_pids()

    def test_walks_up_to_explorer_and_stops(self):
        procs = {9: (8, "python.exe"), 8: (7, "pwsh.exe"), 7: (6, "Code.exe"), 6: (1, "explorer.exe"), 1: (0, "x")}
        self.assertEqual(self.ancestors(procs, 9), {9, 8, 7})

    def test_a_reused_parent_pid_loop_ends(self):
        self.assertEqual(self.ancestors({9: (8, "a.exe"), 8: (9, "b.exe")}, 9), {9, 8})


if __name__ == "__main__":
    unittest.main()
