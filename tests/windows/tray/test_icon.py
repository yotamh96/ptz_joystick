import ctypes
import unittest
from collections.abc import Callable
from unittest import mock

from ptz_joystick.windows.tray import icon

# A real line from ptz_joystick.log, as the camera-not-answering status shows it.
CAMERA_WARNING = ("Camera not answering: camera unreachable: HTTPConnectionPool(host='192.168.77.3', port=80): Max "
                  "retries exceeded with url: /cgi-bin/ptzctrl.cgi?ptzcmd&right&24&1 (Caused by ConnectTimeoutError("
                  "<HTTPConnection(host='192.168.77.3', port=80) at 0x1edee31d150>, 'Connection to 192.168.77.3 timed "
                  "out. (connect timeout=1.0)'))")


def units(text):
    return len(text.encode("utf-16-le")) // 2


class StructTest(unittest.TestCase):
    def test_size_matches_windows(self):
        self.assertEqual(ctypes.sizeof(icon.NOTIFYICONDATAW), 976 if ctypes.sizeof(ctypes.c_void_p) == 8 else 956)


class FitTest(unittest.TestCase):
    def test_short_text_is_kept(self):
        self.assertEqual(icon.fit("ptz_joystick: Driving http://192.168.77.3", 128),
                         "ptz_joystick: Driving http://192.168.77.3")

    def test_a_long_camera_warning_is_cut_to_the_field(self):
        cut = icon.fit("ptz_joystick: " + CAMERA_WARNING, 128)
        self.assertEqual(units(cut), 127)
        self.assertTrue(cut.endswith("…"))
        icon.NOTIFYICONDATAW().szTip = cut              # fits the real field: no ValueError

    def test_two_unit_characters_are_never_split(self):
        cut = icon.fit("😀" * 100, 128)
        self.assertEqual(cut, "😀" * 63 + "…")
        icon.NOTIFYICONDATAW().szTip = cut


class FakeExplorer:
    """Stands in for Shell_NotifyIconW, answering as Explorer does: nothing works without a taskbar, NIM_ADD fails
    while our icon is already there, NIM_MODIFY needs it there. timeouts: that many adds report failure although
    the icon was added (Explorer busy at sign-in)."""

    def __init__(self, taskbar=True, timeouts=0):
        self.taskbar, self.timeouts, self.has_icon = taskbar, timeouts, False
        self.calls: list[tuple[int, int, str, str]] = []

    def __call__(self, message, data):
        self.calls.append((message, data.uFlags, data.szTip, data.szInfo))
        if not self.taskbar:
            return False
        if message == icon.NIM_ADD:
            if self.has_icon:
                return False
            self.has_icon = True
            if self.timeouts:
                self.timeouts -= 1
                return False
            return True
        if message == icon.NIM_DELETE:
            self.has_icon = False
            return True
        return self.has_icon                    # NIM_MODIFY

    def messages(self):
        return [c[0] for c in self.calls]


class TrayIconTest(unittest.TestCase):
    def make(self, explorer):
        self.timers: list[tuple[float, Callable[[], None]]] = []
        self.enterContext(mock.patch.object(icon, "_notify", explorer))
        return icon.TrayIcon(hwnd=1, callback_message=0x8002, later=lambda s, fn: self.timers.append((s, fn)))

    def test_first_set_adds_later_sets_change(self):
        explorer = FakeExplorer()
        tray = self.make(explorer)
        tray.set(5, "ptz_joystick: Starting…")
        tray.set(6, "ptz_joystick: Driving http://cam")
        self.assertEqual(explorer.messages(), [icon.NIM_ADD, icon.NIM_MODIFY])
        self.assertEqual(explorer.calls[-1][2], "ptz_joystick: Driving http://cam")

    def test_add_retries_every_2_s_until_the_taskbar_is_there(self):
        explorer = FakeExplorer(taskbar=False)
        tray = self.make(explorer)
        tray.set(5, "a")
        tray.set(6, "b")                                # a retry is already due: no extra attempt
        self.assertEqual([s for s, _ in self.timers], [2.0])
        self.timers.pop()[1]()                          # still no taskbar: one more timer
        explorer.taskbar = True
        self.timers.pop()[1]()                          # works
        self.assertEqual(explorer.messages(), [icon.NIM_ADD, icon.NIM_MODIFY] * 2 + [icon.NIM_ADD])
        self.assertEqual(explorer.calls[-1][2], "b")
        self.assertEqual(self.timers, [])

    def test_popup_asked_for_before_the_icon_shows_once_it_does(self):
        explorer = FakeExplorer(taskbar=False)
        tray = self.make(explorer)
        tray.set(5, "a")
        tray.popup("ptz_joystick", "Move the left stick to start", icon.NIIF_INFO)
        explorer.taskbar = True
        self.timers.pop()[1]()
        self.assertEqual(explorer.calls[-1][0], icon.NIM_MODIFY)
        self.assertEqual(explorer.calls[-1][3], "Move the left stick to start")

    def test_explorer_restart_adds_the_icon_again(self):
        explorer = FakeExplorer()
        tray = self.make(explorer)
        tray.set(5, "a")
        explorer.has_icon = False                       # Explorer restarted, and our icon went with it
        tray.taskbar_created()
        self.assertEqual(explorer.messages(), [icon.NIM_ADD, icon.NIM_ADD])

    def test_taskbar_created_with_our_icon_still_there_keeps_it_updating(self):
        """Explorer also broadcasts TaskbarCreated on DPI and monitor changes, with our icon still in place."""
        explorer = FakeExplorer()
        tray = self.make(explorer)
        tray.set(5, "a")
        tray.taskbar_created()
        tray.set(6, "b")
        self.assertEqual(self.timers, [])
        message, _, tip, _ = explorer.calls[-1]
        self.assertEqual((message, tip), (icon.NIM_MODIFY, "b"))

    def test_an_add_that_timed_out_but_worked_is_taken_over(self):
        """At sign-in Shell_NotifyIconW can report a timeout although the icon was added."""
        explorer = FakeExplorer(timeouts=1)
        tray = self.make(explorer)
        tray.set(5, "a")
        tray.popup("ptz_joystick", "Move the left stick to start", icon.NIIF_INFO)
        self.assertEqual(self.timers, [])
        self.assertEqual(explorer.calls[-1][3], "Move the left stick to start")

    def test_a_removed_icon_stays_removed(self):
        explorer = FakeExplorer()
        tray = self.make(explorer)
        tray.set(5, "a")
        tray.remove()
        tray.taskbar_created()
        tray.set(6, "b")
        self.assertEqual(explorer.messages(), [icon.NIM_ADD, icon.NIM_DELETE])


if __name__ == "__main__":
    unittest.main()
