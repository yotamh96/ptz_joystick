"""Startup checks: catch a wrong setting or a missing device now, with a message naming the fix, instead of
mid-session."""
from pathlib import Path

from ..cameras import Camera
from ..config import Settings
from ..controllers import Controller
from ..core.commands import PanTilt
from .registry import CAMERAS, CONTROLLERS


def check_types(s: Settings, settings_path: Path):
    """camera and controller name known types, and the speeds fit that camera. Before anything connects."""
    for name, table in (("camera", CAMERAS), ("controller", CONTROLLERS)):
        if getattr(s, name) not in table:
            raise SystemExit(f"{settings_path}: {name} must be one of {', '.join(table)}, got {getattr(s, name)!r}")
    for name, top in CAMERAS[s.camera].top_speeds.items():
        if getattr(s, name) > top:
            raise SystemExit(f"{settings_path}: {name} can be at most {top} for camera {s.camera!r}, "
                             f"got {getattr(s, name)}")


def check_camera(camera: Camera, host: str, settings_path: Path):
    """Send a harmless stop, so a wrong address or password fails now instead of mid-session."""
    if not camera.send(PanTilt(0, 0)):
        raise SystemExit(f"Camera at {host} did not accept a stop command (reason logged above). "
                         f"Check host in {settings_path}, the network, and PTZ_PASSWORD.")


def check_axes(controller: Controller, s: Settings, settings_path: Path):
    """The controller has the axes the settings name."""
    if state := controller.read():
        missing = [a for a in (s.pan_axis, s.tilt_axis, s.zoom_axis) if a not in state.axes]
        if missing:
            raise SystemExit(f"Controller has no axis {missing} (has {list(state.axes)}). "
                             f"Fix the axes in {settings_path}.")
