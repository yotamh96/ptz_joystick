"""Stand-ins for a controller and a camera, and helpers, shared by the app tests."""
import logging

from ptz_joystick.controllers import ControllerState


class ScriptedController:
    """Plays back readings, then raises KeyboardInterrupt like Ctrl+C."""

    def __init__(self, *readings):
        self.readings = list(readings)

    def read(self):
        if not self.readings:
            raise KeyboardInterrupt
        return self.readings.pop(0)


class SetsStop(ScriptedController):
    """Plays back readings and sets stop with the last one, so run() ends by itself instead of reading again."""

    def __init__(self, stop, *readings):
        super().__init__(*readings)
        self.stop = stop

    def read(self):
        state = super().read()
        if not self.readings:
            self.stop.set()
        return state


class RecordingCamera:
    def __init__(self):
        self.calls = []

    def send(self, cmd):
        self.calls.append(cmd)
        return True


def moving(x=0.0, r=0.0):
    return ControllerState({"X": x, "Y": 0.0, "R": r}, 0)


def reset_logging():
    """Close the log file setup_logging() opened, so a temp folder can be deleted (Windows keeps open files)."""
    root = logging.getLogger()
    for h in root.handlers[:]:
        h.close()
        root.removeHandler(h)
