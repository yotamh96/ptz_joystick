import functools
import unittest

from ptz_joystick.winconsole import (
    CTRL_CLOSE_EVENT,
    CTRL_LOGOFF_EVENT,
    CTRL_SHUTDOWN_EVENT,
    make_handler,
)

CTRL_C_EVENT, CTRL_BREAK_EVENT = 0, 1


class HandlerTest(unittest.TestCase):
    def test_close_logoff_shutdown_run_callback(self):
        for event in (CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT):
            calls = []
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

        with self.assertLogs("ptz_joystick.winconsole", "ERROR"):
            self.assertTrue(make_handler(boom)(CTRL_CLOSE_EVENT))


if __name__ == "__main__":
    unittest.main()
