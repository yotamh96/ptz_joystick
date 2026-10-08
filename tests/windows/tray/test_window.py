import ctypes
import threading
import unittest
from ctypes import wintypes

from ptz_joystick.windows.tray import window

user32 = ctypes.WinDLL("user32")        # own copy, for SendMessageW
user32.SendMessageW.restype = window.LRESULT
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
WM_RBUTTONUP = 0x0205


class HiddenWindowTest(unittest.TestCase):
    def setUp(self):
        self.calls: list[tuple] = []
        self.window = window.HiddenWindow(on_tray=lambda event: self.calls.append(("tray", event)),
                                          on_end_session=lambda: self.calls.append(("end",)),
                                          on_taskbar_created=lambda: self.calls.append(("taskbar",)))
        self.addCleanup(self.window.quit)

    def send(self, msg, wparam=0, lparam=0):
        """Deliver a message the way Windows does, straight to the window."""
        return user32.SendMessageW(self.window.hwnd, msg, wparam, lparam)

    def test_a_call_posted_from_another_thread_runs_on_the_window_thread(self):
        ran_on: list[int] = []
        safety = threading.Timer(5, self.window.post, args=(self.window.quit,))   # never hang the test run
        safety.start()
        self.addCleanup(safety.cancel)

        def elsewhere():
            self.window.post(lambda: ran_on.append(threading.get_ident()))
            self.window.post(self.window.quit)

        threading.Thread(target=elsewhere).start()
        self.window.run()                       # returns once the posted quit ran
        self.assertEqual(ran_on, [threading.get_ident()])

    def test_logoff_and_shutdown_reach_the_handler(self):
        self.assertEqual(self.send(window.WM_QUERYENDSESSION), 1)
        self.send(window.WM_ENDSESSION, wparam=0)        # cancelled: nothing to do
        self.send(window.WM_ENDSESSION, wparam=1)
        self.assertEqual(self.calls, [("end",)])

    def test_tray_clicks_and_explorer_restarts_reach_their_handlers(self):
        self.send(window.WM_APP_TRAY, lparam=WM_RBUTTONUP)
        self.send(self.window.taskbar_created)
        self.assertEqual(self.calls, [("tray", WM_RBUTTONUP), ("taskbar",)])

    def test_a_failing_handler_is_logged_and_the_window_lives_on(self):
        def boom():
            raise RuntimeError("icon gone")

        w = window.HiddenWindow(on_tray=lambda event: None, on_end_session=boom, on_taskbar_created=boom)
        self.addCleanup(w.quit)
        with self.assertLogs("ptz_joystick.windows.tray.window", "ERROR"):
            user32.SendMessageW(w.hwnd, window.WM_ENDSESSION, 1, 0)
        self.assertEqual(user32.SendMessageW(w.hwnd, window.WM_QUERYENDSESSION, 0, 0), 1)


if __name__ == "__main__":
    unittest.main()
