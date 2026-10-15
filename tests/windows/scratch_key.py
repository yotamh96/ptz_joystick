"""A throwaway registry key for tests, so they never touch the real Run or Environment keys."""
import os
import unittest
import winreg

PARENT = r"Software\ptz_joystick_tests"


def scratch_key(test: unittest.TestCase, name: str) -> str:
    """Create HKCU\\Software\\ptz_joystick_tests\\<name>-<pid>, deleted when the test ends. -> its path."""
    path = rf"{PARENT}\{name}-{os.getpid()}"
    winreg.CreateKey(winreg.HKEY_CURRENT_USER, path).Close()
    test.addCleanup(_delete, path)
    return path


def _delete(path: str):
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)          # its values go with it
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, PARENT)
    except OSError:                     # another test's key is still in it
        pass
