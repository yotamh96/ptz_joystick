import functools
import os
import unittest
from unittest import mock

from ptz_joystick.windows import console
from ptz_joystick.windows.console import (
    CTRL_CLOSE_EVENT,
    CTRL_LOGOFF_EVENT,
    CTRL_SHUTDOWN_EVENT,
    make_handler,
)

CTRL_C_EVENT, CTRL_BREAK_EVENT = 0, 1


class HandlerTest(unittest.TestCase):
    def test_close_logoff_shutdown_run_callback(self):
        for event in (CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT):
            calls: list[int] = []
            handler = make_handler(functools.partial(calls.append, 1))
            with self.subTest(event=event):
                self.assertTrue(handler(event))
                self.assertEqual(calls, [1])

    def test_ctrl_c_left_to_python(self):
        calls = []
        handler = make_handler(lambda: calls.append(1))
        self.assertFalse(handler(CTRL_C_EVENT))       # False = next handler: Python's KeyboardInterrupt
        self.assertFalse(handler(CTRL_BREAK_EVENT))
        self.assertEqual(calls, [])

    def test_callback_error_is_logged_not_raised(self):
        def boom():
            raise RuntimeError("camera gone")

        with self.assertLogs("ptz_joystick.windows.console", "ERROR"):
            self.assertTrue(make_handler(boom)(CTRL_CLOSE_EVENT))


class OwnsConsoleTest(unittest.TestCase):
    def owns(self, pids):
        with mock.patch.object(console, "_console_pids", return_value=pids):
            return console.owns_console()

    def test_double_clicked_exe_owns_its_window(self):
        self.assertTrue(self.owns([os.getpid()]))
        self.assertTrue(self.owns([os.getppid(), os.getpid()]))     # onefile exe: the bootloader is our parent

    def test_a_shell_on_the_console_means_a_terminal(self):
        shell = max(os.getpid(), os.getppid()) + 1
        self.assertFalse(self.owns([shell, os.getppid(), os.getpid()]))

    def test_no_console_is_not_ours(self):
        self.assertFalse(self.owns([]))

    def test_the_real_list_reads(self):
        self.assertIsInstance(console._console_pids(), list)


if __name__ == "__main__":
    unittest.main()
