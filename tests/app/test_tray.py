import threading
import time
import unittest
from pathlib import Path
from typing import Any, cast
from unittest import mock

from ptz_joystick.app import tray
from ptz_joystick.app.status import GREEN, RED, YELLOW

SETTINGS = Path(r"C:\Users\op\OneDrive - Draco\ptz_joystick.toml")
WM_MOUSEMOVE, WM_RBUTTONUP = 0x0200, 0x0205


class FakeWindow:
    """Stands in for HiddenWindow: post() queues the call; pump() runs the queue, as the message loop would."""

    def __init__(self, on_tray, on_end_session, on_taskbar_created, on_close):
        self.on_tray, self.on_end_session, self.on_taskbar_created = on_tray, on_end_session, on_taskbar_created
        self.on_close = on_close
        self.hwnd = 1
        self.queued: list = []
        self.closed = False

    def post(self, fn):
        self.queued.append(fn)

    def pump(self):
        while self.queued:
            self.queued.pop(0)()

    def quit(self):
        self.closed = True


class FakeIcon:
    """Stands in for TrayIcon: records what it was asked to show."""

    def __init__(self, hwnd, callback_message, later):
        self.shown: list[tuple] = []        # (dot, hover text); a dot is its color here (see setUp)
        self.popups: list[tuple] = []       # (text, kind)
        self.removed = False
        self.readded = 0

    def set(self, hicon, tip):
        self.shown.append((hicon, tip))

    def popup(self, title, text, kind):
        self.popups.append((text, kind))

    def remove(self):
        self.removed = True

    def taskbar_created(self):
        self.readded += 1


class FakeSessions:
    """Stands in for run_session: records each session's (stop, report, check_updates) and runs until stopped."""

    def __init__(self):
        self.started: list[tuple[threading.Event, Any, bool]] = []
        self.ended: list[threading.Event] = []

    def __call__(self, path, keyboard, stop, report, check_updates=False):
        self.started.append((stop, report, check_updates))
        stop.wait(5)
        self.ended.append(stop)


class TrayAppTest(unittest.TestCase):
    def setUp(self):
        self.sessions = FakeSessions()
        self.enterContext(mock.patch.object(tray, "HiddenWindow", FakeWindow))
        self.enterContext(mock.patch.object(tray, "TrayIcon", FakeIcon))
        self.enterContext(mock.patch.object(tray.dots, "dot_icon", lambda color: color))
        self.enterContext(mock.patch.object(tray, "run_session", self.sessions))
        self.app = tray.TrayApp(SETTINGS, keyboard=False)
        self.addCleanup(self.app.shutdown)          # ends the fake session's thread
        self.window = cast(FakeWindow, self.app._window)
        self.icon = cast(FakeIcon, self.app._icon)

    def session(self, n):
        """Session n's (stop, report, check_updates), once its thread has started."""
        deadline = time.monotonic() + 2
        while len(self.sessions.started) < n:
            if time.monotonic() > deadline:
                self.fail(f"session {n} never started")
            time.sleep(0.01)
        return self.sessions.started[n - 1]

    def entry(self, text):
        return next(e for e in self.app._entries() if e and e.text == text)

    def pick(self, text):
        action = self.entry(text).action
        assert action is not None, text
        action()

    def test_starts_yellow_then_green_once_the_session_drives(self):
        self.assertEqual(self.icon.shown[-1], (YELLOW, "ptz_joystick: Starting…"))
        self.app.start_session()
        _, report, _ = self.session(1)
        report.driving("http://cam")
        self.window.pump()
        self.assertEqual(self.icon.shown[-1], (GREEN, "ptz_joystick: Driving http://cam"))

    def test_red_pops_up_as_an_error(self):
        self.app.start_session()
        _, report, _ = self.session(1)
        report.stopped("Set the camera password first")
        self.window.pump()
        self.assertEqual(self.icon.shown[-1][0], RED)
        self.assertEqual(self.icon.popups, [("Set the camera password first", tray.NIIF_ERROR)])

    def test_restart_stops_the_old_session_and_starts_a_new_one(self):
        self.app.start_session()
        old_stop, _, first_asks_github = self.session(1)
        self.app.restart()
        new_stop, _, second_asks_github = self.session(2)
        self.assertIn(old_stop, self.sessions.ended)            # joined: it really finished
        self.assertFalse(new_stop.is_set())
        self.assertEqual((first_asks_github, second_asks_github), (True, False))     # once per process

    def test_a_stopped_sessions_late_news_is_dropped(self):
        self.app.start_session()
        _, old, _ = self.session(1)
        self.app.restart()
        _, new, _ = self.session(2)
        new.driving("http://cam")
        old.stopped("Crashed: RuntimeError('late'). See the log.")
        self.window.pump()
        self.assertEqual(self.icon.shown[-1][0], GREEN)
        self.assertEqual(self.icon.popups, [])

    def test_the_update_notice_survives_a_restart(self):
        self.app.start_session()
        _, old, _ = self.session(1)
        self.app.restart()
        self.session(2)
        old.update("v0.4.0", "https://example/v0.4.0")
        self.window.pump()
        self.assertEqual(self.icon.popups, [("Update available: v0.4.0", tray.NIIF_INFO)])

    def test_quit_stops_the_session_removes_the_icon_and_closes_the_window(self):
        self.app.start_session()
        stop, _, _ = self.session(1)
        self.app.quit()
        self.assertIn(stop, self.sessions.ended)
        self.assertTrue(self.icon.removed)
        self.assertTrue(self.window.closed)

    def test_logoff_stops_the_session_before_windows_ends_us(self):
        self.app.start_session()
        stop, _, _ = self.session(1)
        self.window.on_end_session()
        self.assertIn(stop, self.sessions.ended)
        self.assertTrue(self.icon.removed)

    def test_a_close_request_quits(self):
        self.app.start_session()
        stop, _, _ = self.session(1)
        self.window.on_close()                                  # taskkill without /f
        self.assertIn(stop, self.sessions.ended)                # the camera was stopped
        self.assertTrue(self.icon.removed)
        self.assertTrue(self.window.closed)

    def test_explorer_restart_re_adds_the_icon(self):
        self.window.on_taskbar_created()
        self.assertEqual(self.icon.readded, 1)

    def test_a_click_opens_the_menu_and_runs_the_pick(self):
        with mock.patch.object(tray.menu, "show", side_effect=lambda hwnd, entries: entries[-1]) as show:   # Quit
            self.window.on_tray(WM_MOUSEMOVE)                   # the mouse passing over: nothing
            show.assert_not_called()
            self.window.on_tray(WM_RBUTTONUP)
        self.assertTrue(self.window.closed)

    def test_menu_in_a_source_run(self):
        self.assertEqual([e.text if e else "---" for e in self.app._entries()],
                         ["Starting…", "---", "Open settings", "Open log", "Restart", "---", "Quit"])

    def test_open_settings_keeps_a_path_with_spaces_whole(self):
        with mock.patch.object(tray.subprocess, "Popen") as popen:
            self.pick("Open settings")
        popen.assert_called_once_with(["notepad.exe", str(SETTINGS)])

    def test_open_log_is_grayed_without_a_log_file(self):
        self.assertTrue(self.entry("Open log").enabled)
        self.app._status.log_to("")
        self.assertFalse(self.entry("Open log").enabled)

    def test_start_with_windows_writes_the_quoted_exe_path(self):
        exe = r"C:\Users\op\OneDrive - Draco\ptz_joystick_tray.exe"
        with mock.patch.object(tray.sys, "frozen", True, create=True), \
                mock.patch.object(tray.sys, "executable", exe), \
                mock.patch.object(tray.autostart, "enabled", return_value=False), \
                mock.patch.object(tray.autostart, "enable") as enable:
            self.assertFalse(self.entry("Start with Windows").checked)
            self.pick("Start with Windows")
        enable.assert_called_once_with(f'"{exe}"')

    def test_start_with_windows_ticked_turns_it_off(self):
        with mock.patch.object(tray.sys, "frozen", True, create=True), \
                mock.patch.object(tray.autostart, "enabled", return_value=True), \
                mock.patch.object(tray.autostart, "disable") as disable:
            self.assertTrue(self.entry("Start with Windows").checked)
            self.pick("Start with Windows")
        disable.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
