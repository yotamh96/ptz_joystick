# Tray app: design

2026-10-08 · Design approved in chat, section by section. This file is the reference for the implementation plan.

## Goal

Operators on Draco PCs run ptz_joystick without a console window:

- Nothing to close or Ctrl+C by mistake mid-session.
- Status at a glance: icon color and hover text. Pop-ups only when someone needs to act.
- "Start with Windows" as an opt-in toggle, off by default.

The console exe stays, unchanged, for troubleshooting (`debug = true`, live log in the terminal).

## Decisions

| Topic | Decision |
|---|---|
| Tray code | Own Win32 code through ctypes, like `winmm.py` and `console.py`. No new packages. |
| Rejected | pystray + Pillow: 3 new packages, no hook for logoff/shutdown, icon and menu changed from any thread without locking. Hiding the console exe's window: it flashes, and Windows Terminal ignores the hide. |
| Exes | Two, from the same code: `ptz_joystick.exe` (console, unchanged) and `ptz_joystick_tray.exe` (windowed, new). They share `ptz_joystick.toml` and the log. |
| Mode switch | `--tray`. `python -m ptz_joystick --tray` gives the tray plus live terminal logs, for development. |
| Autostart | Menu checkbox, off by default. One value under the HKCU Run key. Tray exe only. |
| Startup failures | Camera not answering, or no controller: yellow, retry every 5 s. Anything else: red, and the app stays running for Open settings → Restart. |

## What the operator sees

### Icon

A colored dot: green `#22A045`, yellow `#F0B000`, red `#D03030`. Hover text: `ptz_joystick: <status text>`, cut to 127 characters.

| Color | When | Status text |
|---|---|---|
| Yellow | Starting | `Starting…` |
| Yellow | Camera not answering at startup | `Waiting for camera at <host>: <last camera warning>` |
| Yellow | Waiting for a stick move | `Move the left stick to start` |
| Yellow | No controller found | The controller factory's message, e.g. `No controller found. Check that it shows in joy.cpl.` |
| Green | Driving | `Driving <host>` |
| Yellow | Controller unplugged while driving | `Controller unplugged: plug it back in` |
| Yellow | Camera stops answering while driving | `Camera not answering: <last camera warning>` |
| Red | Session ended with an error | The error: today's `SystemExit` text, or `Crashed: <exception repr>. See the log.` (e.g. `Crashed: RuntimeError('boom'). See the log.`, matching `__main__.py`'s `%r`) |

While driving, "controller unplugged" wins over "camera not answering". When both are fine again, the icon goes back to green.

`<last camera warning>` is the newest WARNING the camera adapter logged, e.g. `camera rejected the login (401): check user in ptz_joystick.toml and PTZ_PASSWORD`. A `logging.Handler` on the `ptz_joystick.cameras` logger keeps it, and each session start clears it. It sits on that logger, not the root, because `setup_logging` replaces the root handlers (`basicConfig(force=True)`).

### Pop-ups

| Event | Pop-up |
|---|---|
| Still waiting for a stick move after 1 s | `Move the left stick to start`, once per session |
| Controller unplugged | `Controller unplugged. Camera stopped. Plug it back in.`, once per unplug |
| Session ends red | The red status text, every time |
| Newer release on GitHub | `Update available: <tag>`, once per process |
| Camera not answering | None, icon only. On this network the camera drops every minute or two. |

The 1 s delay stops a wrong "move the stick" pop-up when no controller is plugged in: the factory then raises at once.

Pop-up icons (`NIIF_*`): info for "move the stick" and updates, warning for "controller unplugged", error for red.

### Menu

Right-click or left-click on the icon:

```
<status text>              grayed
───────────
Open settings              notepad.exe <settings file>
Open log                   notepad.exe <current log file>; grayed when there is none (log_file = "")
Restart                    stop the session, start a new one: re-reads the settings and PTZ_PASSWORD
Start with Windows         checkbox; shown only in the exe (sys.frozen)
───────────
Quit                       stop the camera, remove the icon, exit 0
```

Settings and log open in Notepad rather than the default app, because `.toml` often has no file association, and `docs/troubleshooting.md` already assumes Notepad. "Current log file" is the bootstrap log (see Tray) until the settings load, then `log_file`.

### Windows 11 note

Windows 11 puts new tray icons in the overflow (^). Each PC needs one manual step: Settings → Personalization → Taskbar → Other system tray icons → ptz_joystick_tray on. Apps can't do this themselves. It goes in the README and the manual check.

## How it's built

### Threads

| Thread | Job |
|---|---|
| Main | Hidden window plus message loop. The only thread that touches the icon, menu and pop-ups. |
| Session | Startup steps, then the control loop (`app/loop.py run`). Reports status by posting to the main thread. Daemon. |
| Sender, update check | Unchanged. |

Posting: `window.post(fn)` puts `fn` on a `queue.SimpleQueue` and calls `PostMessageW(hwnd, WM_APP_CALL, 0, 0)`. The window runs the queued calls on the main thread. `Status` is plain data, touched only there.

### Session: `app/session.py`

`run_session(path, keyboard, stop, report, retry_every=5.0)`. `stop` is a `threading.Event`; `report` posts events to the main thread.

1. If `HKCU\Environment` has `PTZ_PASSWORD`, copy it into `os.environ`, so the newest `setx` wins without signing out.
2. `startup.prepare(path, keyboard)` → `Settings`: write the template, load, apply `--keyboard`, `check_types`, `setup_logging`, the start-up log lines.
3. `controller = "keyboard"` → red: `The keyboard controller only works in the console version (ptz_joystick.exe).`
4. Camera: connect, then send `PanTilt(0, 0)` until accepted. Between tries: yellow, `stop.wait(retry_every)`.
5. Controller: yellow `Move the left stick to start`; start a 1 s `threading.Timer` for its pop-up, cancelled when the factory returns. Call `CONTROLLERS[s.controller](s)`. If it raises `SystemExit` (the Controller contract's "no device"): yellow with its message, `stop.wait(retry_every)`, try again.
6. `check_axes`.
7. `sender = CommandSender(camera, on_camera=…)`, green, `run(s, controller, sender, stop=stop, on_controller=…)`.

After every step that blocks: if `stop` is set, return without driving. `winmm.discover()` can't be interrupted, so a session stopped during discovery ends at the next stick move, before it drives.

Errors: `SystemExit` → log ERROR, red. Any other exception → log CRITICAL with the traceback, red `Crashed: …`. If it happened inside `run()`, its `finally` has already stopped the camera.

### Tray: `app/tray.py`

`run_tray(path, keyboard)`:

1. Log to the default log file before anything else (the bootstrap log): `setup_logging(Settings(log_file=str(path.parent / Settings().log_file)))`, then log `ptz_joystick <VERSION> (tray)`. Even a missing password lands in the log.
2. Build the window, the icon (yellow `Starting…`), the status and the menu.
3. Start the update check, once per process (`on_found` → pop-up).
4. If there is a console (`--tray` from a terminal): `on_console_close(quit)`.
5. Start the session thread, then run the message loop until Quit.

| Trigger | Action |
|---|---|
| Restart | `stop.set()`, join ≤ 4 s, new `stop`, new session thread |
| Quit | `stop.set()`, join ≤ 4 s, remove the icon, end the loop |
| `WM_ENDSESSION`, wParam TRUE | Same as Quit, before returning from the message |
| `WM_QUERYENDSESSION` | Return TRUE |
| `TaskbarCreated` | Add the icon again |

The joins wait ≤ 4 s because `drain_with` gives up after 3 s, and `Settings` caps `timeout` at 2 s for exactly this. Windows allows about 5 s after `WM_ENDSESSION`. Quit during discovery: the join times out, and the daemon session thread ends with the process. Nothing is moving at that point.

### New files

| File | Role |
|---|---|
| `windows/tray/window.py` | Hidden **top-level** window. Not `HWND_MESSAGE`: message-only windows miss `WM_ENDSESSION` and the `TaskbarCreated` broadcast. Message loop, `post(fn)`, routing of tray clicks, end-session and TaskbarCreated. Lets TaskbarCreated through UIPI (`ChangeWindowMessageFilterEx`) in case the app runs elevated. Catches and logs exceptions in callbacks, which ctypes would otherwise swallow. Keeps its WNDPROC object alive, like `console.py`'s `_registered`. |
| `windows/tray/icon.py` | `Shell_NotifyIconW`: add, update (icon and tip), pop-up (`NIF_INFO`), remove. Cuts text to the struct sizes: `szTip` 128, `szInfo` 256, `szInfoTitle` 64 WCHARs. If adding fails (taskbar not ready yet at login), retries every 2 s and on TaskbarCreated. |
| `windows/tray/menu.py` | `Item(text, action, enabled=True, checked=False)` and a separator. Builds a popup menu and shows it with `TrackPopupMenu(TPM_RETURNCMD)`. Calls `SetForegroundWindow` before and posts `WM_NULL` after, or the menu won't close on a click elsewhere. |
| `windows/tray/dots.py` | `dot_pixels(rgb, size)`: pure, a BGRA circle on transparent. `dot_icon(rgb)`: an HICON from a 32-bit DIB through `CreateIconIndirect`, sized `GetSystemMetrics(SM_CXSMICON)`. |
| `windows/single_instance.py` | `claim(name="Local\\ptz_joystick") -> bool`: `CreateMutexW`, False on `ERROR_ALREADY_EXISTS`. The handle stays open until exit. |
| `windows/autostart.py` | `enabled(command)`, `enable(command)`, `disable()` on `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, value `ptz_joystick`, data `"<exe path>"`. The key path is a parameter, for tests. Checked = the value exists and equals this exe's command. |
| `windows/user_env.py` | `user_env(name) -> str \| None` from `HKCU\Environment`. Expands `REG_EXPAND_SZ`. The key path is a parameter, for tests. |
| `windows/message_box.py` | `message_box(text)` through `MessageBoxW`. For "already running" in tray mode, which happens before there is a tray. |
| `app/status.py` | Pure: events → color, text and pop-up, as in the tables above. |
| `app/startup.py` | `prepare(path, keyboard) -> Settings`. Moved out of `main.py` so both modes share it. |
| `app/session.py` | See Session above. |
| `app/tray.py` | See Tray above. |

`windows/tray/` and `tests/windows/tray/` are packages, each with an empty `__init__.py`, like the existing folders.

### Changes to existing files

Every new parameter is optional, so console mode and the existing tests stay as they are.

| File | Change |
|---|---|
| `app/loop.py` | `run(..., stop=None, on_controller=None)`: loops until `stop` is set, waiting with `stop.wait(period)`. Calls `on_controller(ok)` where it logs lost / back. |
| `core/sender.py` | `CommandSender(..., on_camera=None)`: calls `on_camera(ok)` when the camera's answers switch between accepted and refused/raised. A `TypeError` (unsupported command) doesn't count. Callback errors are logged and never stop the thread. |
| `app/updates.py` | `check_in_background(..., on_found=None)`: called with `(tag, url)` after the log line. |
| `app/logs.py` | No `StreamHandler` when `sys.stderr` is None. |
| `app/main.py` | `--tray` → `tray.run_tray`. `single_instance.claim()` in both modes. Console: `SystemExit("ptz_joystick is already running. Quit it first: tray icon or its console window.")`. Tray: `message_box(...)` with the same text, then exit 1. The shared startup steps move to `startup.py`. |
| `config/template.py` | First comment line: `Edit, save, then restart ptz_joystick (tray: right-click → Restart).` |

## Build, CI, tests, docs

### CI: `.github/workflows/ci.yml`

- **build**: a second launcher, `launch_tray.py` = `import sys; sys.argv.insert(1, "--tray"); import ptz_joystick.__main__`, then `pyinstaller --onefile --windowed --name ptz_joystick_tray launch_tray.py`.
- **sign**: both exes.
- **smoke test, tray exe**: start it with no `PTZ_PASSWORD`. Poll up to 30 s until `dist\ptz_joystick.log` contains `Set the camera password first`. Check the log also has `ptz_joystick <want>`. Then stop every `ptz_joystick_tray` process (a onefile exe runs as two). Only the log is checked, so a runner without a taskbar is fine.
- **artifacts and release**: both exes.
- **lint**: unchanged. No new packages.

### Tests

They mirror the package (`tests/<folder>/test_<module>.py`), use unittest, and run on Windows CI as today.

| Test file | Covers |
|---|---|
| `tests/app/test_status.py` | Every row of the icon and pop-up tables. Precedence while driving. Text cut to 127. |
| `tests/app/test_session.py` | Missing password → red with today's text. Camera refuses twice → yellow, then green. Factory raises `SystemExit` → yellow, then retried. Crash in `read()` → CRITICAL logged, camera stopped, red. Keyboard → red. `stop` during the camera wait → returns within 0.2 s. Stopped during discovery → never drives. |
| `tests/app/test_tray.py` | With a fake window and icon: Restart stops the old session (camera stopped) and starts a new one. Quit and `WM_ENDSESSION` stop the camera before returning. TaskbarCreated re-adds the icon. |
| `tests/app/test_startup.py` | Template written on first run. `--keyboard`. Unknown type → `SystemExit`. |
| `tests/app/test_loop.py` (added to) | `stop` ends the loop with the camera stopped. `on_controller` gets False, then True. |
| `tests/core/test_sender.py` (added to) | `on_camera` fires only on change: refuse, refuse, accept → `[False, True]`. |
| `tests/app/test_updates.py` (added to) | `on_found` gets `(tag, url)`. |
| `tests/app/test_logs.py` (added to) | No `StreamHandler` when `sys.stderr` is None. |
| `tests/windows/tray/test_window.py` | A real hidden window. A call posted from another thread runs on the window's thread. A sent `WM_ENDSESSION` reaches the handler. |
| `tests/windows/tray/test_menu.py` | Menu built, not shown: item count, grayed, checked. |
| `tests/windows/tray/test_icon.py` | Text cut to the struct limits. A failed add retries. `Shell_NotifyIconW` is patched, the way `test_focus.py` patches `_foreground`. |
| `tests/windows/tray/test_dots.py` | Center pixel has the color, corners are transparent. `dot_icon` returns a handle. |
| `tests/windows/test_single_instance.py` | A second `claim` of the same unique name → False. |
| `tests/windows/test_autostart.py` | enable / enabled / disable on a scratch key under `HKCU\Software\ptz_joystick_tests`. Never the real Run key. |
| `tests/windows/test_user_env.py` | Reads a value from a scratch key. |

### Manual check

On a real PC with the camera and the pad, about 10 minutes:

1. Double-click the tray exe. Make its icon visible (Windows 11 note). Yellow, "Move the left stick" pop-up. Move it → green.
2. Unplug the pad → yellow plus a pop-up. Plug it back in → green.
3. Unplug the camera's network → yellow, no pop-up. Reconnect → green.
4. Break a setting, Restart → red plus a pop-up. Open settings, fix it, Restart → green.
5. `setx PTZ_PASSWORD` a wrong value, Restart → yellow, "rejected the login (401)". Set it back, Restart → green.
6. Pan, then sign out mid-pan → the camera stops.
7. Pan, then Quit → the camera stops.
8. Start `ptz_joystick.exe` while the tray runs → "already running".
9. Tick Start with Windows, sign out and back in → it starts by itself. Untick it, sign out and in → it doesn't.
10. `taskkill /f /im explorer.exe`, then `start explorer` → the icon comes back.

### Docs

- `README.md`: Run leads with `ptz_joystick_tray.exe`: icon colors, menu, Start with Windows, the Windows 11 note. The console exe is for troubleshooting. Controls table: Quit, logoff and shutdown stop the camera.
- `docs/troubleshooting.md`: icon colors, where errors show, "already running", `setx` then Restart.
- `docs/development.md`: the new files in the layout, `python -m ptz_joystick --tray`.
- `docs/releases.md`: two exes, both signed and smoke-tested.

## Out of scope

- Logoff/shutdown stop for the console exe. Microsoft's `SetConsoleCtrlHandler` docs say a program that loads user32.dll (`keyboard.py` does) doesn't get those events, so it may not work today. The new hidden window makes it a small follow-up.
- Skipping "move the stick" after autostart, by remembering the joystick ID.
- An installer or a Start menu shortcut.
- Editing settings or the password from the tray.
