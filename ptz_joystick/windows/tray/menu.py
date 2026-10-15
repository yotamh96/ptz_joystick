"""The tray icon's menu: built from a list of entries, shown at the mouse, returns the one picked. Windows only."""
import ctypes
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass

MF_STRING, MF_GRAYED, MF_CHECKED, MF_SEPARATOR = 0x0000, 0x0001, 0x0008, 0x0800
TPM_RIGHTBUTTON, TPM_NONOTIFY, TPM_RETURNCMD = 0x0002, 0x0080, 0x0100
WM_NULL = 0x0000

user32 = ctypes.WinDLL("user32", use_last_error=True)       # own copy: we set prototypes below
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  wintypes.HWND, wintypes.LPVOID]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


@dataclass(frozen=True)
class Item:
    text: str
    action: Callable[[], None] | None = None    # None: a line of text that can't be picked (the status)
    enabled: bool = True
    checked: bool = False


Entry = Item | None                 # None: a separator line


def build(entries: list[Entry]) -> int:
    """The menu (an HMENU); entry i is command i + 1. Free it with user32.DestroyMenu."""
    menu = user32.CreatePopupMenu()
    for i, item in enumerate(entries, 1):
        if item is None:
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        else:
            flags = MF_STRING | (0 if item.enabled and item.action else MF_GRAYED) | (MF_CHECKED if item.checked else 0)
            user32.AppendMenuW(menu, flags, i, item.text.replace("&", "&&"))    # one & would underline a letter
    return menu


def show(hwnd: int, entries: list[Entry]) -> Item | None:
    """Show the menu at the mouse and wait. -> the item picked, or None if the menu was dismissed."""
    menu = build(entries)
    try:
        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        user32.SetForegroundWindow(hwnd)            # without this and the WM_NULL below, the menu stays open
        picked = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_NONOTIFY | TPM_RETURNCMD, point.x, point.y, 0, hwnd,
                                       None)        # after a click elsewhere
        user32.PostMessageW(hwnd, WM_NULL, 0, 0)
    finally:
        user32.DestroyMenu(menu)
    return entries[picked - 1] if picked else None
