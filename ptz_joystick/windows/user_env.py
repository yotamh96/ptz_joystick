"""A user environment variable as setx left it, for a program that started before setx ran. Windows only.

A running program keeps the environment it started with. setx writes HKCU\\Environment, so reading there finds a
password set after the tray app started."""
import winreg

KEY = "Environment"


def user_env(name: str, key: str = KEY) -> str | None:
    """The variable from HKCU\\<key>, expanded the way Windows expands it for new programs. None if not there."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            value, kind = winreg.QueryValueEx(k, name)
    except OSError:                     # no such key or value
        return None
    if not isinstance(value, str):
        return None
    return winreg.ExpandEnvironmentStrings(value) if kind == winreg.REG_EXPAND_SZ else value
