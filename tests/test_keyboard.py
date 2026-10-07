import unittest
from unittest import mock

from ptz_joystick.config import Settings
from ptz_joystick.controllers import keyboard
from ptz_joystick.controllers.keyboard import VK_LEFT, VK_RIGHT, VK_UP
from ptz_joystick.core.commands import PanTilt, Zoom
from ptz_joystick.core.mapping import Mapper

CONSOLE, TERMINAL_PID = 100, 5        # our console window, and one of our parent processes (say VS Code)


def read(*keys, settings=None, front=(None, TERMINAL_PID)):
    """One read() with these virtual-key codes held and front = (window, its process) in front."""
    with mock.patch.object(keyboard, "_console_windows", return_value={CONSOLE}),          mock.patch.object(keyboard, "_ancestor_pids", return_value={TERMINAL_PID}):
        c = keyboard.KeyboardController(settings or Settings())
    with mock.patch.object(keyboard, "_held", side_effect=lambda vk: vk in keys),          mock.patch.object(keyboard, "_foreground", return_value=front):
        return c.read()


class KeyboardControllerTest(unittest.TestCase):
    def test_nothing_held_reads_centred(self):
        state = read()
        self.assertEqual(state.axes, {"X": 0.0, "Y": 0.0, "R": 0.0})
        self.assertEqual(state.buttons, 0)

    def test_keys_move_the_camera_the_way_they_point(self):
        """Through the mapper with default settings: up arrow = tilt up, right = pan right, W = zoom in."""
        s = Settings()
        self.assertIn(PanTilt(s.pan_max, s.tilt_max), Mapper(s).update(read(VK_RIGHT, VK_UP)))
        self.assertIn(Zoom(s.zoom_max), Mapper(s).update(read(ord("W"))))
        self.assertIn(Zoom(-s.zoom_max), Mapper(s).update(read(ord("S"))))

    def test_opposite_keys_cancel(self):
        self.assertEqual(read(VK_LEFT, VK_RIGHT).axes["X"], 0.0)

    def test_digit_keys_are_buttons(self):
        self.assertEqual(read(ord("1"), ord("4")).buttons, 0b1001)

    def test_axes_follow_settings(self):
        state = read(VK_RIGHT, settings=Settings(pan_axis="U", tilt_axis="V", zoom_axis="Z"))
        self.assertEqual(state.axes, {"U": 1.0, "V": 0.0, "Z": 0.0})

    def test_keys_count_with_the_console_window_in_front(self):
        self.assertEqual(read(VK_RIGHT, front=(CONSOLE, 999)).axes["X"], 1.0)

    def test_another_window_in_front_reads_centred_and_released(self):
        state = read(VK_RIGHT, ord("1"), front=(200, 999))
        self.assertEqual(state.axes, {"X": 0.0, "Y": 0.0, "R": 0.0})
        self.assertEqual(state.buttons, 0)


class AncestorPidsTest(unittest.TestCase):
    def ancestors(self, procs, me):
        with mock.patch.object(keyboard, "_processes", return_value=procs),              mock.patch.object(keyboard.os, "getpid", return_value=me):
            return keyboard._ancestor_pids()

    def test_walks_up_to_explorer_and_stops(self):
        procs = {9: (8, "python.exe"), 8: (7, "pwsh.exe"), 7: (6, "Code.exe"), 6: (1, "explorer.exe"), 1: (0, "x")}
        self.assertEqual(self.ancestors(procs, 9), {9, 8, 7})

    def test_a_reused_parent_pid_loop_ends(self):
        self.assertEqual(self.ancestors({9: (8, "a.exe"), 8: (9, "b.exe")}, 9), {9, 8})


if __name__ == "__main__":
    unittest.main()
