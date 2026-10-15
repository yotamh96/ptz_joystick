import gc
import tempfile
import threading
import time
import tkinter as tk
import unittest
import weakref
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
        return settings_dialog.open_dialog(self.path, {n: t.top_speeds for n, t in CAMERAS.items()},
                                           list(CONTROLLERS), type_error, lambda: None,
                                           lambda: self.notepads.append(True))

    def shown(self, handle):
        """Wait until the dialog's window exists."""
        deadline = time.monotonic() + 5
        while not handle.hwnd and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(handle.hwnd and handle.alive)

    def test_a_broken_file_offers_notepad_instead(self):
        self.path.write_text('hots = "x"', encoding="utf-8")
        with mock.patch.object(settings_dialog, "ask", return_value=True) as ask:
            self.assertTrue(self.open().done.wait(5))
        text = ask.call_args.args[0]
        self.assertTrue(text.startswith(f"Bad setting in {config.FILE_NAME}: unknown setting 'hots'"), text)
        self.assertTrue(text.endswith("\n\nOpen it in Notepad?"), text)
        self.assertEqual(self.notepads, [True])

    def test_no_to_the_offer_opens_nothing(self):
        self.path.write_text('hots = "x"', encoding="utf-8")
        with mock.patch.object(settings_dialog, "ask", return_value=False):
            self.assertTrue(self.open().done.wait(5))
        self.assertEqual(self.notepads, [])

    def test_opens_on_its_own_thread_and_closes_when_the_tray_asks(self):
        handle = self.open()                    # no file yet: the template is written first
        self.shown(handle)
        self.assertTrue(self.path.exists())
        handle.close()
        self.assertFalse(handle.alive)
        gc.collect()                            # nothing of Tk left for this thread to free: Tcl would abort

    def test_a_closed_dialog_frees_its_tcl_interpreter(self):
        roots: list[weakref.ref] = []

        class Recorded(tk.Tk):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                roots.append(weakref.ref(self))

        with mock.patch.object(settings_dialog.tk, "Tk", Recorded):
            handle = self.open()
            self.shown(handle)
            handle.close()
        self.assertFalse(handle.alive)
        self.assertIsNone(roots[0](), "the dialog's thread left its Tcl interpreter alive: ~2 MB per open")

    def test_every_open_runs_on_the_same_thread(self):
        threads: list[int] = []

        class Recorded(tk.Tk):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                threads.append(threading.get_ident())

        with mock.patch.object(settings_dialog.tk, "Tk", Recorded):
            for _ in range(2):
                handle = self.open()
                self.shown(handle)
                handle.close()
        self.assertEqual(len(threads), 2)
        self.assertEqual(threads[0], threads[1], "Tcl keeps ~0.5 MB for every thread that ran Tk, for good")

    def test_when_tk_cant_start_settings_opens_in_notepad(self):
        broken = mock.Mock(side_effect=tk.TclError("Can't find a usable init.tcl"))
        with mock.patch.object(settings_dialog.tk, "Tk", broken), mock.patch.object(settings_dialog.log, "exception"):
            self.assertTrue(self.open().done.wait(5))
        self.assertEqual(self.notepads, [True])


if __name__ == "__main__":
    unittest.main()
