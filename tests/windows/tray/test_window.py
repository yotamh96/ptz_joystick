import ctypes
import threading
import time
import unittest
from ctypes import wintypes

from ptz_joystick.windows.tray import window

user32 = ctypes.WinDLL("user32")        # own copy, for sending messages the way Windows does
user32.SendMessageW.restype = window.LRESULT
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendNotifyMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.IsWindow.argtypes = [wintypes.HWND]
WM_NULL, WM_RBUTTONUP = 0x0000, 0x0205


def nothing():
    pass


class HiddenWindowTest(unittest.TestCase):
    def setUp(self):
        self.calls: list[tuple] = []
        self.window = window.HiddenWindow(on_tray=lambda event: self.calls.append(("tray", event)),
                                          on_end_session=lambda: self.calls.append(("end",)),
                                          on_taskbar_created=lambda: self.calls.append(("taskbar",)),
                                          on_close=lambda: self.calls.append(("close",)))
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

    def test_quit_from_a_tray_click_ends_the_loop(self):
        """Explorer sends tray clicks (SendNotifyMessage), so the menu's Quit runs inside GetMessageW. It must still
        end run(), or the process lives on with no window and keeps the 'already running' claim."""
        def quit_on_click(event):
            w.quit()

        w = window.HiddenWindow(on_tray=quit_on_click, on_end_session=nothing, on_taskbar_created=nothing,
                                on_close=nothing)
        self.addCleanup(w.quit)
        nudge = threading.Timer(3, user32.PostThreadMessageW, args=(threading.get_native_id(), WM_NULL, 0, 0))
        nudge.start()                           # a stuck loop wakes after 3 s instead of hanging the test run
        self.addCleanup(nudge.cancel)
        threading.Thread(target=user32.SendNotifyMessageW, args=(w.hwnd, window.WM_APP_TRAY, 0, WM_RBUTTONUP)).start()
        started = time.monotonic()
        w.run()
        self.assertLess(time.monotonic() - started, 1.5)

    def test_logoff_and_shutdown_reach_the_handler(self):
        self.assertEqual(self.send(window.WM_QUERYENDSESSION), 1)
        self.send(window.WM_ENDSESSION, wparam=0)        # cancelled: nothing to do
        self.send(window.WM_ENDSESSION, wparam=1)
        self.assertEqual(self.calls, [("end",)])

    def test_tray_clicks_and_explorer_restarts_reach_their_handlers(self):
        self.send(window.WM_APP_TRAY, lparam=WM_RBUTTONUP)
        self.send(self.window.taskbar_created)
        self.assertEqual(self.calls, [("tray", WM_RBUTTONUP), ("taskbar",)])

    def test_a_close_request_goes_to_its_handler(self):
        """taskkill without /f sends WM_CLOSE. The app must quit (stopping the camera); left to Windows, the
        window would just be destroyed while the session drove on."""
        self.send(window.WM_CLOSE)
        self.assertEqual(self.calls, [("close",)])
        self.assertTrue(user32.IsWindow(self.window.hwnd))

    def test_a_failing_handler_is_logged_and_the_window_lives_on(self):
        def boom():
            raise RuntimeError("icon gone")

        w = window.HiddenWindow(on_tray=lambda event: None, on_end_session=boom, on_taskbar_created=boom,
                                on_close=boom)
        self.addCleanup(w.quit)
        with self.assertLogs("ptz_joystick.windows.tray.window", "ERROR"):
            user32.SendMessageW(w.hwnd, window.WM_ENDSESSION, 1, 0)
        self.assertEqual(user32.SendMessageW(w.hwnd, window.WM_QUERYENDSESSION, 0, 0), 1)


if __name__ == "__main__":
    unittest.main()
