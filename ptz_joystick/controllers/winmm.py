"""Windows joystick via the winmm API (same data as joy.cpl). Windows only."""
import ctypes
import logging
import time

from . import ControllerState

log = logging.getLogger(__name__)


class JOYINFOEX(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint32) for n in (
        "dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos", "dwUpos", "dwVpos",
        "dwButtons", "dwButtonNumber", "dwPOV", "dwReserved1", "dwReserved2")]


class JOYCAPSW(ctypes.Structure):
    _fields_ = ([("wMid", ctypes.c_uint16), ("wPid", ctypes.c_uint16), ("szPname", ctypes.c_wchar * 32)]
                + [(n, ctypes.c_uint32) for n in (
                    "wXmin", "wXmax", "wYmin", "wYmax", "wZmin", "wZmax", "wNumButtons", "wPeriodMin",
                    "wPeriodMax", "wRmin", "wRmax", "wUmin", "wUmax", "wVmin", "wVmax", "wCaps",
                    "wMaxAxes", "wNumAxes", "wMaxButtons")]
                + [("szRegKey", ctypes.c_wchar * 32), ("szOEMVxD", ctypes.c_wchar * 260)])


winmm = ctypes.WinDLL("winmm")
JOY_RETURNALL = 0xFF
HAS_AXIS = {"Z": 1, "R": 2, "U": 4, "V": 8}     # JOYCAPS_HASZ/R/U/V; X and Y always exist


def _caps(dev):
    caps = JOYCAPSW()
    return caps if winmm.joyGetDevCapsW(dev, ctypes.byref(caps), ctypes.sizeof(caps)) == 0 else None


def _pos(dev):
    info = JOYINFOEX(dwSize=ctypes.sizeof(JOYINFOEX), dwFlags=JOY_RETURNALL)
    return info if winmm.joyGetPosEx(dev, ctypes.byref(info)) == 0 else None


class WinmmController:
    def __init__(self, dev):
        caps = _caps(dev)
        if caps is None:
            raise OSError(f"joystick {dev}: no caps")
        self._dev = dev
        # a missing axis would read 0 = -1.0 = full speed forever, so only present axes are reported
        self._ranges = {a: (getattr(caps, f"w{a}min"), getattr(caps, f"w{a}max"))
                        for a in "XYZRUV" if a in "XY" or caps.wCaps & HAS_AXIS[a]}

    def read(self):
        info = _pos(self._dev)
        if info is None:
            return None
        axes = {a: max(-1.0, min(1.0, (getattr(info, f"dw{a}pos") - lo) / (hi - lo) * 2 - 1)) if hi > lo else 0.0
                for a, (lo, hi) in self._ranges.items()}
        return ControllerState(axes, info.dwButtons)


def discover():
    """Wait for the user to move a stick and return that device (Windows often lists phantom IDs)."""
    found = {}
    for d in range(16):
        if _pos(d):
            try:
                found[d] = WinmmController(d)
            except OSError:
                pass
    start = {d: st.axes for d, c in found.items() if (st := c.read())}
    if not start:
        raise SystemExit("No controller found. Check that it shows in joy.cpl.")
    log.info("Joystick IDs found: %s", list(start))
    log.info("Move the left stick now...")
    while True:
        for d, axes0 in start.items():
            st = found[d].read()
            if st and max(abs(st.axes[a] - axes0[a]) for a in axes0) > 0.3:
                log.info("Using joystick ID %s", d)
                return found[d]
        time.sleep(0.05)
