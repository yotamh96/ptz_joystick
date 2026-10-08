"""The tray icon's status dot: a filled circle in one color, drawn in memory, so no image files ship. Windows only."""
import ctypes
from ctypes import wintypes

SM_CXSMICON = 49                # small-icon size: what the notification area shows
BI_RGB, DIB_RGB_COLORS = 0, 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]


user32 = ctypes.WinDLL("user32", use_last_error=True)       # own copies: we set prototypes below
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.CreateIconIndirect.restype = wintypes.HICON
user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
user32.DestroyIcon.argtypes = [wintypes.HICON]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
gdi32.CreateBitmap.restype = wintypes.HBITMAP
gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.UINT, ctypes.c_void_p]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]


def dot_pixels(rgb: tuple[int, int, int], size: int) -> bytes:
    """size x size pixels, top row first, 4 bytes each (blue, green, red, alpha): a soft-edged circle of rgb on
    transparent."""
    r, g, b = rgb
    middle, radius = (size - 1) / 2, size / 2 - 1
    out = bytearray()
    for y in range(size):
        for x in range(size):
            inside = radius + 0.5 - ((x - middle) ** 2 + (y - middle) ** 2) ** 0.5   # > 0 inside, fades over 1 px
            out += bytes((b, g, r, round(max(0.0, min(1.0, inside)) * 255)))
    return bytes(out)


def dot_icon(rgb: tuple[int, int, int]) -> int:
    """An icon handle (HICON) of the dot at the small-icon size. Free it with user32.DestroyIcon when done."""
    size = user32.GetSystemMetrics(SM_CXSMICON)
    header = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=size, biHeight=-size,  # -: top row first
                              biPlanes=1, biBitCount=32, biCompression=BI_RGB)
    bits = ctypes.c_void_p()
    color = gdi32.CreateDIBSection(None, ctypes.byref(header), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
    if not color:
        raise ctypes.WinError(ctypes.get_last_error())
    mask = gdi32.CreateBitmap(size, size, 1, 1, bytes((size + 15) // 16 * 2 * size))   # all 0: alpha shapes the icon
    try:
        ctypes.memmove(bits, dot_pixels(rgb, size), size * size * 4)
        icon = user32.CreateIconIndirect(ctypes.byref(ICONINFO(fIcon=True, hbmMask=mask, hbmColor=color)))
    finally:
        gdi32.DeleteObject(color)       # the icon keeps its own copies
        gdi32.DeleteObject(mask)
    if not icon:
        raise ctypes.WinError(ctypes.get_last_error())
    return icon
