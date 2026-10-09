"""What the tray shows: the dot's color, the status text, and which events pop up a message. Plain rules with no
Windows calls; app/tray.py feeds them events and draws the result."""
from dataclasses import dataclass

GREEN, YELLOW, RED = (0x22, 0xA0, 0x45), (0xF0, 0xB0, 0x00), (0xD0, 0x30, 0x30)


@dataclass(frozen=True)
class Popup:
    text: str
    kind: str           # "info", "warning" or "error": the pop-up's icon


class Status:
    """One per tray app, used on the window's thread. Event methods return the pop-up to show, if any."""

    def __init__(self, log_file: str):
        self.color, self.text = YELLOW, "Starting…"
        self.log_file = log_file                # what Open log opens; "" = there is no log file
        self._host: str | None = None           # set while driving
        self._waiting_for_stick = self._prompted = False
        self._controller_ok = self._camera_ok = True
        self._camera_why = ""

    @property
    def tooltip(self) -> str:
        return f"ptz_joystick: {self.text}"

    def starting(self) -> None:
        """A new session: its "move the stick" pop-up may show again."""
        self._phase(YELLOW, "Starting…")
        self._prompted = False

    def log_to(self, log_file: str) -> None:
        self.log_file = log_file

    def waiting_for_camera(self, host: str, why: str) -> None:
        self._phase(YELLOW, f"Waiting for camera at {host}: {why}" if why else f"Waiting for camera at {host}")

    def waiting_for_stick(self) -> None:
        self._phase(YELLOW, "Move the left stick to start")
        self._waiting_for_stick = True

    def stick_prompt(self) -> Popup | None:
        """The session has waited a second for a stick move: pop up, once per session."""
        if not self._waiting_for_stick or self._prompted:
            return None
        self._prompted = True
        return Popup("Move the left stick to start", "info")

    def no_controller(self, message: str) -> None:
        self._phase(YELLOW, message)

    def driving(self, host: str) -> None:
        self._phase(GREEN, f"Driving {host}")
        self._host = host
        self._controller_ok = self._camera_ok = True

    def controller(self, ok: bool) -> Popup | None:
        if self._host is None:                  # only while driving
            return None
        unplugged = self._controller_ok and not ok
        self._controller_ok = ok
        self._show_driving()
        return Popup("Controller unplugged. Camera stopped. Plug it back in.", "warning") if unplugged else None

    def camera(self, ok: bool, why: str) -> None:
        """Icon only: the camera drops every minute or two on this network, a pop-up each time would be noise."""
        if self._host is None:
            return
        self._camera_ok, self._camera_why = ok, why
        self._show_driving()

    def stopped(self, message: str) -> Popup:
        self._phase(RED, message)
        return Popup(message, "error")

    def update(self, tag: str) -> Popup:
        return Popup(f"Update available: {tag}", "info")

    def _phase(self, color: tuple[int, int, int], text: str):
        self.color, self.text = color, text
        self._host, self._waiting_for_stick = None, False

    def _show_driving(self):
        if not self._controller_ok:             # an unplugged controller explains more than a silent camera
            self.color, self.text = YELLOW, "Controller unplugged: plug it back in"
        elif not self._camera_ok:
            self.color = YELLOW
            self.text = f"Camera not answering: {self._camera_why}" if self._camera_why else "Camera not answering"
        else:
            self.color, self.text = GREEN, f"Driving {self._host}"
