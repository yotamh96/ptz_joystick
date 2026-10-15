"""Start with Windows: one value under the user's Run key (Task Manager lists it under Startup apps). Windows only."""
import winreg

RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "ptz_joystick"


def command_for(exe: str) -> str:
    """The Run value for an exe: quoted, so a path with spaces (OneDrive - Draco) still starts."""
    return f'"{exe}"'


def enabled(command: str, key: str = RUN) -> bool:
    """True if Windows runs exactly this command at sign-in. Another copy's path doesn't count."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            return winreg.QueryValueEx(k, NAME)[0] == command
    except OSError:                     # no such key or value
        return False


def enable(command: str, key: str = RUN):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
        winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, command)


def disable(key: str = RUN):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, NAME)
    except FileNotFoundError:           # already off
        pass
