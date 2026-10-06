"""PTZOptics over HTTP-CGI with Digest auth (requests handles the SHA-256 variant)."""
import logging

import requests
from requests.auth import HTTPDigestAuth

from ..commands import Command, PanTilt, Preset, Zoom

log = logging.getLogger(__name__)


def to_query(cmd: Command) -> str:
    """Command -> the ptzctrl.cgi query string."""
    match cmd:
        case PanTilt(0, 0):
            parts = ("ptzstop", 0, 0)
        case PanTilt(pan, tilt):
            h = "right" if pan > 0 else "left" if pan < 0 else ""
            v = "up" if tilt > 0 else "down" if tilt < 0 else ""
            parts = (h + v, abs(pan) or 1, abs(tilt) or 1)   # camera wants a speed for the idle axis too
        case Zoom(0):
            parts = ("zoomstop", 0)
        case Zoom(speed):
            parts = ("zoomin" if speed > 0 else "zoomout", abs(speed))
        case Preset(number):
            parts = ("poscall", number)
        case _:
            raise TypeError(f"PTZOptics can't do {cmd!r}")
    return "&".join(map(str, ("ptzcmd", *parts)))


class PtzOpticsCamera:
    def __init__(self, host, user, password, timeout=1.0):
        self.url = f"{host}/cgi-bin/ptzctrl.cgi?"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = HTTPDigestAuth(user, password)
        self.failing = None     # kind of the current failure, so an outage logs once, not every retry

    def send(self, cmd: Command) -> bool:
        try:
            r = self.session.get(self.url + to_query(cmd), timeout=self.timeout)
        except requests.RequestException as e:
            return self._failed("unreachable", f"camera unreachable: {e}")
        if r.status_code == 200:
            if self.failing:
                log.info("camera back (was: %s)", self.failing)
                self.failing = None
            return True
        if r.status_code == 401:
            return self._failed(401, "camera rejected the login (401): check user in config.py and PTZ_PASSWORD")
        return self._failed(r.status_code, f"camera answered {r.status_code} to {cmd}")

    def _failed(self, kind, msg):
        if kind != self.failing:
            log.warning(msg)
            self.failing = kind
        else:
            log.debug(msg)
        return False
