"""The tray app's hidden window. Its message loop runs on the main thread, and only that thread touches the icon
and the menu: other threads hand work over with post(). Windows only.

A top-level window, never shown. Not a message-only window (HWND_MESSAGE): those miss WM_QUERYENDSESSION /
WM_ENDSESSION (logoff, shutdown) and the TaskbarCreated broadcast (Explorer restarted)."""
import ctypes
import logging
import queue
from collections.abc import Callable
from ctypes import wintypes

log = logging.getLogger(__name__)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
WM_CLOSE, WM_QUERYENDSESSION, WM_ENDSESSION = 0x0010, 0x0011, 0x0016
WM_APP_CALL = 0x8001                # WM_APP + 1: "run the next call post() queued"
WM_APP_TRAY = 0x8002                # WM_APP + 2: the tray icon's mouse messages (icon.py asks for this number)
MSGFLT_ALLOW = 1


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]


user32 = ctypes.WinDLL("user32", use_last_error=True)       # own copies: we set prototypes below
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.RegisterClassExW.restype = wintypes.ATOM
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU,
                                   wintypes.HINSTANCE, wintypes.LPVOID]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.RegisterWindowMessageW.restype = wintypes.UINT
user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
user32.ChangeWindowMessageFilterEx.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.DWORD, wintypes.LPVOID]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


class HiddenWindow:
    """Make it on the thread that will call run(): Windows hands a window's messages to the thread that made it."""

    def __init__(self, on_tray: Callable[[int], None], on_end_session: Callable[[], None],
                 on_taskbar_created: Callable[[], None], on_close: Callable[[], None]):
        # Everything _handle() uses is set before CreateWindowExW, which already sends the window messages.
        self._on_tray, self._on_end_session, self._on_taskbar_created = on_tray, on_end_session, on_taskbar_created
        self._on_close = on_close
        self._calls: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()
        self.taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
        self._proc = WNDPROC(self._handle)      # kept alive here: Windows calls it as long as the window exists
        self._instance = kernel32.GetModuleHandleW(None)
        self._class = f"ptz_joystick_tray_{id(self):x}"     # unique, so tests can make several
        wc = WNDCLASSEXW(cbSize=ctypes.sizeof(WNDCLASSEXW), lpfnWndProc=self._proc, hInstance=self._instance,
                         lpszClassName=self._class)
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.hwnd = user32.CreateWindowExW(0, self._class, "ptz_joystick", 0, 0, 0, 0, 0, None, None, self._instance,
                                           None)
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self._alive, self._running = True, False
        user32.ChangeWindowMessageFilterEx(self.hwnd, self.taskbar_created, MSGFLT_ALLOW, None)  # in case elevated

    def post(self, fn: Callable[[], None]):
        """Run fn on the window's thread, soon. Safe from any thread."""
        self._calls.put(fn)
        user32.PostMessageW(self.hwnd, WM_APP_CALL, 0, 0)

    def run(self):
        """Handle messages until quit()."""
        if not self._alive:
            return
        msg = wintypes.MSG()
        self._running = True
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:      # 0: the WM_QUIT from quit()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            self._running = False

    def quit(self):
        """Close the window and end run(). On the window's thread; from another, post(window.quit)."""
        if self._alive:
            self._alive = False
            user32.DestroyWindow(self.hwnd)
            user32.UnregisterClassW(self._class, self._instance)
            if self._running:       # WM_QUIT wakes GetMessageW even when quit() runs inside it (a sent tray click)
                user32.PostQuitMessage(0)

    def _handle(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_APP_CALL:
                self._calls.get_nowait()()
            elif msg == WM_APP_TRAY:
                self._on_tray(lparam)
            elif msg == WM_QUERYENDSESSION:
                return 1                        # yes, Windows may end the session
            elif msg == WM_ENDSESSION:
                if wparam:                      # it really ends: stop the camera now, Windows ends us after this
                    self._on_end_session()
            elif msg == self.taskbar_created:
                self._on_taskbar_created()
            elif msg == WM_CLOSE:                   # taskkill without /f: quit properly, don't just lose the window
                self._on_close()
            else:
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        except Exception:                       # ctypes would swallow it: log it instead
            log.exception("tray window: message %#x failed", msg)
        return 0
