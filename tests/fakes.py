"""Stand-ins for a controller and a camera, shared by the app tests."""
from ptz_joystick.controllers import ControllerState


class ScriptedController:
    """Plays back readings, then raises KeyboardInterrupt like Ctrl+C."""

    def __init__(self, *readings):
        self.readings = list(readings)

    def read(self):
        if not self.readings:
            raise KeyboardInterrupt
        return self.readings.pop(0)


class RecordingCamera:
    def __init__(self):
        self.calls = []

    def send(self, cmd):
        self.calls.append(cmd)
        return True


def moving(x=0.0, r=0.0):
    return ControllerState({"X": x, "Y": 0.0, "R": r}, 0)
