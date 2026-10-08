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


class FakeShell:
    """Stands in for Shell_NotifyIconW: records each call; the first fail_adds NIM_ADDs fail (no taskbar yet)."""

    def __init__(self, fail_adds=0):
        self.calls: list[tuple[int, int, str, str]] = []
        self.fail_adds = fail_adds

    def __call__(self, message, data):
        self.calls.append((message, data.uFlags, data.szTip, data.szInfo))
        if message == icon.NIM_ADD and self.fail_adds:
            self.fail_adds -= 1
            return False
        return True

    def messages(self):
        return [c[0] for c in self.calls]


class TrayIconTest(unittest.TestCase):
    def make(self, shell):
        self.timers: list[tuple[float, Callable[[], None]]] = []
        self.enterContext(mock.patch.object(icon, "_notify", shell))
        return icon.TrayIcon(hwnd=1, callback_message=0x8002, later=lambda s, fn: self.timers.append((s, fn)))

    def test_first_set_adds_later_sets_change(self):
        shell = FakeShell()
        tray = self.make(shell)
        tray.set(5, "ptz_joystick: Starting…")
        tray.set(6, "ptz_joystick: Driving http://cam")
        self.assertEqual(shell.messages(), [icon.NIM_ADD, icon.NIM_MODIFY])
        self.assertEqual(shell.calls[-1][2], "ptz_joystick: Driving http://cam")

    def test_add_retries_every_2_s_until_the_taskbar_is_there(self):
        shell = FakeShell(fail_adds=2)
        tray = self.make(shell)
        tray.set(5, "a")
        tray.set(6, "b")                                # a retry is already due: no extra attempt
        self.assertEqual([s for s, _ in self.timers], [2.0])
        self.timers.pop()[1]()                          # fails again: one more timer
        self.timers.pop()[1]()                          # works
        self.assertEqual(shell.messages(), [icon.NIM_ADD] * 3)
        self.assertEqual(shell.calls[-1][2], "b")
        self.assertEqual(self.timers, [])

    def test_popup_asked_for_before_the_icon_shows_once_it_does(self):
        shell = FakeShell(fail_adds=1)
        tray = self.make(shell)
        tray.set(5, "a")
        tray.popup("ptz_joystick", "Move the left stick to start", icon.NIIF_INFO)
        self.timers.pop()[1]()
        self.assertEqual(shell.messages(), [icon.NIM_ADD, icon.NIM_ADD, icon.NIM_MODIFY])
        self.assertEqual(shell.calls[-1][3], "Move the left stick to start")

    def test_explorer_restart_adds_the_icon_again(self):
        shell = FakeShell()
        tray = self.make(shell)
        tray.set(5, "a")
        tray.taskbar_created()
        self.assertEqual(shell.messages(), [icon.NIM_ADD, icon.NIM_ADD])

    def test_a_removed_icon_stays_removed(self):
        shell = FakeShell()
        tray = self.make(shell)
        tray.set(5, "a")
        tray.remove()
        tray.taskbar_created()
        tray.set(6, "b")
        self.assertEqual(shell.messages(), [icon.NIM_ADD, icon.NIM_DELETE])


if __name__ == "__main__":
    unittest.main()
