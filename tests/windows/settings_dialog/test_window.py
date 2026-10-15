import tempfile
import threading
import tkinter as tk
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from ptz_joystick import config
from ptz_joystick.app.checks import type_error
from ptz_joystick.app.registry import CAMERAS, CONTROLLERS
from ptz_joystick.config import Settings
from ptz_joystick.core.problem import Problem
from ptz_joystick.windows.settings_dialog import window
from ptz_joystick.windows.settings_dialog.window import SettingsWindow

PATH = Path(r"C:\Users\op\OneDrive - Draco\ptz_joystick.toml")
OLD = replace(Settings(), password="pw")


class WindowTest(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.written: list[Settings] = []
        self.restarts: list[bool] = []
        self.notepads: list[bool] = []
        self.window = SettingsWindow(self.root, PATH, OLD, {n: t.top_speeds for n, t in CAMERAS.items()},
                                     list(CONTROLLERS), type_error, self.written.append,
                                     lambda: self.restarts.append(True), lambda: self.notepads.append(True))
        self.addCleanup(self.window.close)
        self.ask = self.enterContext(mock.patch.object(window.messagebox, "askyesno", return_value=True))
        self.show = self.enterContext(mock.patch.object(window.messagebox, "showerror"))
        self.root.update()

    def type(self, setting, text):
        self.window.tabs.vars[setting].set(text)

    def test_save_writes_the_change_then_asks_to_restart(self):
        self.type("host", "http://10.0.0.9")
        self.window.save()
        self.assertEqual(self.written, [replace(OLD, host="http://10.0.0.9")])
        self.assertEqual(self.ask.call_args.args[1], "Settings saved. Restart now to use them?")
        self.assertEqual((self.restarts, self.window.closed), ([True], True))

    def test_no_means_saved_but_not_restarted(self):
        self.ask.return_value = False
        self.type("user", "operator")
        self.window.save()
        self.assertEqual((len(self.written), self.restarts, self.window.closed), (1, [], True))

    def test_a_bad_value_opens_its_tab_and_keeps_the_dialog_open(self):
        self.type("deadzone", "0.8")
        self.window.save()
        tabs = self.window.tabs
        self.assertEqual(tabs.notebook.select(), str(tabs.pages["Controller"]))
        assert tabs.error is not None
        self.assertIn("deadzone", tabs.error.cget("text"))
        self.assertEqual((self.written, self.window.closed), ([], False))
        self.type("deadzone", "0.1")                # fixed: the next Save goes through
        self.window.save()
        self.assertEqual(len(self.written), 1)

    def test_nothing_changed_just_closes(self):
        self.window.save()
        self.assertEqual(self.written, [])
        self.ask.assert_not_called()
        self.assertTrue(self.window.closed)

    def test_a_failed_write_says_why_and_stays_open(self):
        def refuse(s):
            raise Problem("Can't save ptz_joystick.toml", fix="Check that you can write to its folder", detail="denied")

        self.window._write = refuse
        self.type("user", "operator")
        self.window.save()
        self.assertIn("denied", self.show.call_args.args[1])
        self.assertFalse(self.window.closed)

    def test_open_in_notepad_closes_without_saving(self):
        self.type("user", "operator")
        self.window.notepad()
        self.assertEqual((self.written, self.notepads, self.window.closed), ([], [True], True))

    def test_the_tray_can_close_it(self):
        closing = threading.Event()
        self.window.watch(closing)
        self.assertFalse(self.window.closed)
        closing.set()
        self.window.watch(closing)
        self.assertTrue(self.window.closed)


class WriteTest(unittest.TestCase):
    def test_the_password_is_saved_only_when_it_changed(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(window, "set_user_env") as set_env:
            path = Path(d) / config.FILE_NAME
            window.write(path, OLD, "pw")
            set_env.assert_not_called()
            window.write(path, replace(OLD, password="new"), "pw")
            set_env.assert_called_once_with("PTZ_PASSWORD", "new")
            self.assertEqual(config.read(path), Settings())         # the file never holds the password


if __name__ == "__main__":
    unittest.main()
