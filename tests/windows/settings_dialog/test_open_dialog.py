import gc
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from ptz_joystick import config
from ptz_joystick.app.checks import type_error
from ptz_joystick.app.registry import CAMERAS, CONTROLLERS
from ptz_joystick.windows import settings_dialog


class OpenDialogTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(tempfile.TemporaryDirectory())) / config.FILE_NAME
        self.notepads: list[bool] = []

    def open(self):
        handle = settings_dialog.open_dialog(self.path, {n: t.top_speeds for n, t in CAMERAS.items()},
                                             list(CONTROLLERS), type_error, lambda: None,
                                             lambda: self.notepads.append(True))
        assert handle.thread is not None
        return handle, handle.thread

    def test_a_broken_file_offers_notepad_instead(self):
        self.path.write_text('hots = "x"', encoding="utf-8")
        with mock.patch.object(settings_dialog, "ask", return_value=True) as ask:
            _, thread = self.open()
            thread.join(5)
        text = ask.call_args.args[0]
        self.assertTrue(text.startswith(f"Bad setting in {config.FILE_NAME}: unknown setting 'hots'"), text)
        self.assertTrue(text.endswith("\n\nOpen it in Notepad?"), text)
        self.assertEqual(self.notepads, [True])

    def test_no_to_the_offer_opens_nothing(self):
        self.path.write_text('hots = "x"', encoding="utf-8")
        with mock.patch.object(settings_dialog, "ask", return_value=False):
            _, thread = self.open()
            thread.join(5)
        self.assertEqual(self.notepads, [])

    def test_opens_on_its_own_thread_and_closes_when_the_tray_asks(self):
        handle, _ = self.open()                 # no file yet: the template is written first
        deadline = time.monotonic() + 5
        while not handle.hwnd and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(handle.hwnd and handle.alive)
        self.assertTrue(self.path.exists())
        handle.close()
        self.assertFalse(handle.alive)
        gc.collect()                            # nothing of Tk left for this thread to free: Tcl would abort


if __name__ == "__main__":
    unittest.main()
