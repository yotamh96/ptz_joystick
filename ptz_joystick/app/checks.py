"""Startup checks: catch a wrong setting or a missing device now, with a message naming the fix, instead of
mid-session."""
from pathlib import Path

from ..cameras import Camera
from ..config import Settings, bad_setting
from ..controllers import Controller
from ..core.commands import PanTilt
from ..core.problem import Problem
from .registry import CAMERAS, CONTROLLERS


def type_error(s: Settings) -> str | None:
    """What's wrong with camera, controller or the speeds for that camera, or None. No file name: the settings
    dialog shows it under the field; check_types adds the file."""
    for name, table in (("camera", CAMERAS), ("controller", CONTROLLERS)):
        if getattr(s, name) not in table:
            return f"{name} must be one of {', '.join(table)}, got {getattr(s, name)!r}"
    for name, top in CAMERAS[s.camera].top_speeds.items():
        if getattr(s, name) > top:
            return f"{name} can be at most {top} for camera {s.camera!r}, got {getattr(s, name)}"
    return None


def check_types(s: Settings, settings_path: Path):
    """camera and controller name known types, and the speeds fit that camera. Before anything connects."""
    if message := type_error(s):
        raise bad_setting(settings_path, message)


def check_camera(camera: Camera, host: str, settings_path: Path):
    """Send a harmless stop, so a wrong address or password fails now instead of mid-session."""
    if not camera.send(PanTilt(0, 0)):
        raise camera.problem or Problem(f"The camera at {host} didn't answer",
                                        fix=f"Check host in {settings_path.name}, the network, and PTZ_PASSWORD")


def check_axes(controller: Controller, s: Settings, settings_path: Path):
    """The controller has the axes the settings name."""
    if state := controller.read():
        missing = [a for a in (s.pan_axis, s.tilt_axis, s.zoom_axis) if a not in state.axes]
        if missing:
            raise bad_setting(settings_path, f"the controller has no axis {', '.join(missing)} "
                                             f"(it has {', '.join(state.axes)})")
