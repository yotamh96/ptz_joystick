# Problem messages: design

2026-10-15 · Design approved in chat, section by section. This file is the reference for the implementation plan.

## Goal

Every error and warning the operator can read follows one shape and one wording, in every place it shows:

- **Same event, same words.** The log line, the tray status, the pop-up and the console say the same sentence.
- **Console errors stay visible.** A fatal error reaches the log file, and a double-clicked console exe waits for Enter instead of closing.
- **The fix fits the mode.** Console: "run ptz_joystick again". Tray: "click Restart".
- **One error mechanism in code.** One exception type carries the operator's sentence. No more `SystemExit` as a message carrier, and no reading the camera's reason out of log records.

## Decisions

| Topic | Decision |
|---|---|
| Mechanism | `Problem`, an exception in `core/problem.py`, raised where the facts are known. |
| Rejected | A central catalog of every sentence (`messages.py`): one file to review, but indirection, and every new adapter edits it. Rewording only and keeping `SystemExit`: misses "one mechanism", and camera reasons stay in log records. |
| Log vs operator | The log line is the operator's sentence plus the technical detail in brackets. |
| Language | English only. No translation support. |
| Restart step | Added by whoever shows the problem, only when the app stopped. Not part of the problem. |
| Password | Both modes read `PTZ_PASSWORD` from `HKCU\Environment` first, as the tray does today, so `setx` then "run again" works in an old terminal too. |

## The `Problem` type: `core/problem.py`

```python
class Problem(Exception):
    """Something the operator must fix, in their words."""

    def __init__(self, what: str, fix: str = "", detail: str = ""):
        super().__init__(what)
        self.what, self.fix, self.detail = what, fix, detail

    def text(self, then: str = "") -> str:
        """What the operator sees: "What. Fix, then <then>." Parts left empty are left out."""

    def log_line(self, then: str = "") -> str:
        """text(then), plus " (detail)" when there is a detail."""
```

| Field | Holds | Example |
|---|---|---|
| `what` | One short sentence: what is wrong. Capital first letter, no period. | `The camera refused the login` |
| `fix` | An order that names the setting, file or command. No period, no restart step. | `Check user in ptz_joystick.toml and PTZ_PASSWORD` |
| `detail` | The technical cause, for the log only: HTTP code, exception text, full path. | `HTTP 401` |
| `then` (argument) | The restart step, from whoever shows it, only when the app stopped. | Console `run ptz_joystick again`, tray `click Restart` |

`text()` joins as: `{what}.` then ` {fix}` then `, then {then}` then `.`

- `Problem("A", "B").text()` → `A. B.`
- `Problem("A", "B").text(then="click Restart")` → `A. B, then click Restart.`
- `Problem("A").text(then="click Restart")` → `A. Click Restart.` (no fix: the step becomes the order)
- `Problem("A", "B", "HTTP 401").log_line()` → `A. B. (HTTP 401)`

The restart steps are two constants: `RUN_AGAIN = "run ptz_joystick again"` in `app/main.py`, `CLICK_RESTART = "click Restart"` in `app/status.py`.

## Where problems are raised

Every user-facing `SystemExit` becomes a `Problem`. Untouched: argparse's own exits (`--help`, `--version`), and `TypeError` from a camera adapter (the sender's "this camera can't do that command" signal, never shown to the operator).

| Where | Today | New |
|---|---|---|
| `config/loading.py` `load()` | `SystemExit` for a missing password, a bad setting, an unreadable file | `Problem`. `from_dict`, `parse_*` and `Settings.__post_init__` keep raising `ValueError`; `load()` turns it into `bad_setting(path, e)`. |
| `config/loading.py` `read_text()` | `ValueError` for a wrong encoding | `Problem` directly (it has the path). |
| `config/loading.py` | none | New `bad_setting(path, message) -> Problem`: the one wording for any wrong setting. `checks.py` uses it too. |
| `config/template.py` | `SystemExit` for "can't create" | `Problem` |
| `app/checks.py` | `SystemExit` ×4 | `check_types` and `check_axes`: `bad_setting(...)`. `check_camera`: raises `camera.problem` (fallback: a generic camera `Problem` if the adapter left it `None`). |
| `controllers/winmm.py` `discover()` | `SystemExit("No controller found…")` | `Problem`. The tray still retries it every 5 s. |
| `app/main.py` | "already running" as `SystemExit` plus a message box | `Problem` |
| `app/main.py`, `app/session.py` | Crash: `Crashed: RuntimeError('boom'). See the log.` | Any other exception becomes `crashed(e) -> Problem` (in `core/problem.py`) with `repr(e)` in `detail`. The traceback still goes to the log at CRITICAL. |
| `app/startup.py` `prepare()` | none | Reads `PTZ_PASSWORD` from `HKCU\Environment` before `config.load` (moved from `session.py`). |

### Contract changes

- `cameras/__init__.py` `Camera`: new attribute `problem: Problem | None`. Why the last `send` failed, in operator words; `None` after a success. The adapter still logs once per outage, now as `log.warning(problem.log_line())`.
- `controllers/__init__.py`: a controller factory with no device raises `Problem("<what>", fix="<what to check>")` instead of `SystemExit`.
- `docs/extending.md`: both rules, plus "Writing a message" (below).

### Warnings that are only logged

Operator-readable WARNING and ERROR lines log `Problem(...).log_line()`, so they have the same shape. Developer-only lines (`log.exception` for adapter bugs, DEBUG lines) keep their wording.

## How each mode shows a problem

### Console and before the tray exists: `app/main.py`

1. Parse arguments, then set up logging to the default log file next to the settings file, in both modes. Today only `run_tray` does this; `bootstrap_log` moves from `tray.py` to `startup.py`.
2. `single_instance.claim()`, then the console run or `run_tray`, inside one `try`.
3. `except Problem as p`, or `except Exception as e` → `p = crashed(e)` with the traceback logged at CRITICAL:
   - log `p.log_line(then=RUN_AGAIN)` at ERROR
   - tray mode: `message_box(p.text(then=RUN_AGAIN))` (already running, or the tray failed to start)
   - console mode: if `console.owns_console()`, print `Press Enter to close.` and wait (`EOFError` = no stdin, don't wait)
   - `raise SystemExit(1)`

`__main__.py` keeps only `except KeyboardInterrupt: pass`.

`windows/console.py` `owns_console() -> bool`: `GetConsoleProcessList` is not empty, and every process on it is this one or its parent. The parent counts because a PyInstaller onefile exe runs as two processes (bootloader plus child). Double-clicked: owned. Run from a terminal, from VS Code, or from CI's PowerShell: the shell is on the list, so not owned and no wait.

### Tray: `app/session.py`, `app/status.py`, `app/tray.py`

- `session.py` catches `Problem` (and crashes, as `crashed(e)`), logs `p.log_line(then=CLICK_RESTART)`, and calls `report.stopped(p)`.
- `LastWarning` (the log-record handler) is deleted. The session reads `camera.problem`.
- `Report` passes problems, not strings:

| Method | Today | New |
|---|---|---|
| `waiting_for_camera` | `(host, why: str)` | `(host, problem: Problem \| None)` |
| `no_controller` | `(message: str)` | `(problem: Problem)` |
| `camera` | `(ok, why: str)` | `(ok, problem: Problem \| None)` |
| `stopped` | `(message: str)` | `(problem: Problem)` |

- `status.py` builds the words:
  - red: `p.text(then=CLICK_RESTART)`, as status text and pop-up
  - yellow: `p.text()`, or the plain fallback from the table below when there is no problem yet

### Events the app reports itself

`CONTROLLER_UNPLUGGED = Problem("The controller is unplugged and the camera stopped", fix="Plug it back in")`, in `app/loop.py`. The loop logs `CONTROLLER_UNPLUGGED.log_line()`; `status.py` shows `CONTROLLER_UNPLUGGED.text()` as the status text and the pop-up.

Info lines stay plain strings, but the log and the tray use the same words (table below). The console log may add ` Ctrl+C to quit.`

### Length

The tooltip shows 128 characters (including `ptz_joystick: `), the pop-up 256, the log everything. Literal text keeps `text(then=RUN_AGAIN)` within 120 characters. Messages with values in them (a bad setting) may run longer: the tooltip cuts them, and the pop-up and the log show them whole.

## Every message, old → new

Text shown as `text()`; `then` is added as described above.

### Problems

| Event | Today | `what` | `fix` | `detail` |
|---|---|---|---|---|
| No password | `Set the camera password first:  setx PTZ_PASSWORD "..."  then open a new terminal.` | `The camera password is not set` | `Run setx PTZ_PASSWORD "..." in a terminal` | |
| Password in the settings file | `<path>: password must not be in the settings file, use:  setx PTZ_PASSWORD "..."` | via `bad_setting`, message `remove password, set it with setx PTZ_PASSWORD "..." instead` | | |
| Any wrong setting (`bad_setting`) | `<path>: <error>` | `Bad setting in ptz_joystick.toml: <error>` | `Fix it and save` | full path |
| Unknown camera / controller type | `<path>: camera must be one of ptzoptics, got 'x'` | via `bad_setting`, same message | | |
| Speed above the camera's top | `<path>: pan_max can be at most 24 for camera 'ptzoptics', got 30` | via `bad_setting`, same message | | |
| Axis the controller lacks | `Controller has no axis ['Q'] (has [...]). Fix the axes in <path>.` | via `bad_setting`, message `the controller has no axis Q (it has X, Y, Z, R)` | | |
| Wrong file encoding | `<path>: can't read it as text. Save it as UTF-8 (Notepad: File > Save as > Encoding)` | `Wrong text encoding in ptz_joystick.toml` | `In Notepad: File > Save as > Encoding: UTF-8` | full path |
| Can't read the settings file | `Can't read settings file <path>: <error>` | `Can't read ptz_joystick.toml` | `Check that you can open it in Notepad` | the `OSError` |
| Can't create the settings file | `Can't create settings file <path>: <error>` | `Can't create ptz_joystick.toml` | `Move the exe to a folder you can write to` | the `OSError` |
| Camera unreachable | `camera unreachable: <error>` | `Can't reach the camera at <host>` | `Check host in ptz_joystick.toml and the network` | the request error |
| Camera login refused | `camera rejected the login (401): check user in ptz_joystick.toml and PTZ_PASSWORD` | `The camera refused the login` | `Check user in ptz_joystick.toml and PTZ_PASSWORD` | `HTTP 401` |
| Camera answered an error | `camera answered <code> to <cmd>` | `The camera refused a command` | `Check that its web page opens in a browser` | `HTTP <code> to <cmd>` |
| Startup camera check, adapter gave no reason | `Camera at <host> did not accept a stop command (reason logged above). Check host in <path>, the network, and PTZ_PASSWORD.` | `The camera at <host> didn't answer` | `Check host in ptz_joystick.toml, the network, and PTZ_PASSWORD` | |
| No controller | `No controller found. Check that it shows in joy.cpl.` | `No controller found` | `Plug it in and check that it shows in joy.cpl` | |
| Already running | `ptz_joystick is already running. Quit it first: tray icon or its console window.` | `Another ptz_joystick is already running` | `Quit it first: its tray icon or console window` | |
| Crash | `Crashed: RuntimeError('boom'). See the log.` | `Unexpected error in ptz_joystick` | `See the log for details` | `repr(e)` |
| Controller unplugged (log, status, pop-up) | `Controller lost, camera stopped. Waiting for it...` / `Controller unplugged: plug it back in` / `Controller unplugged. Camera stopped. Plug it back in.` | `The controller is unplugged and the camera stopped` | `Plug it back in` | |

### Log-only warnings

| Event | Today | `what` | `fix` | `detail` |
|---|---|---|---|---|
| Sender gave up on a button command | `gave up on <cmd> after 3 tries` | `The camera didn't take a button command` | `Press the button again` | `gave up on <cmd> after 3 tries` |
| Camera didn't confirm the final stop | `Camera did not confirm stop.` | `The camera didn't confirm the stop` | `Check that it stopped moving` | |
| Can't write the log file | `Can't write log file <file> (<error>): terminal only.` | `Can't write the log file` | `Close any program that has it open, or change log_file` | `<file>: <error>` |
| Can't watch the console closing | `Can't watch for the console closing (<error>): close with Ctrl+C to stop the camera.` | `Can't watch for the console window closing` | `Quit with Ctrl+C so the camera stops` | the `WinError` |

### Info lines (plain strings, same words in the log and the tray)

| Event | Today | New |
|---|---|---|
| Driving | log `Driving camera <host>. Ctrl+C to quit.` / tray `Driving <host>` | `Driving the camera at <host>` (console log adds `. Ctrl+C to quit.`) |
| Waiting for a stick move | log `Move the left stick now...` / tray `Move the left stick to start` | `Move the left stick to start` |
| Waiting for the camera, no reason yet | tray `Waiting for camera at <host>` | `Waiting for the camera at <host>` |
| Camera not answering while driving, no reason | tray `Camera not answering` | `The camera is not answering` |
| Controller back | log `Controller back.` | `The controller is back` |
| Camera back | log `camera back (was: <kind>)` | `The camera is answering again (was: <kind>)` |

Unchanged: `Starting…`, the update notice, the startup lines (`ptz_joystick <version>`, `Settings: …`, `Wrote default settings …`), the keyboard help line.

## Writing a message (goes into `docs/extending.md`)

1. `what` says what is wrong, not what the code did. One short sentence, capital first letter, no period.
2. `fix` is an order the operator can follow. It names the setting, file or command. No period.
3. Never put "restart" or "run again" in `fix`: the console or the tray adds its own step.
4. HTTP codes, exception text and full paths go in `detail`. Only the log shows it.
5. Keep `text()` within 120 characters.

## Tests

They mirror the package and use unittest, as today.

| Test file | Covers |
|---|---|
| `tests/core/test_problem.py` (new) | `text()` with and without `fix`, with `then`, with neither. `log_line()` adds the detail; `text()` never does. `crashed(e)` puts `repr(e)` in `detail`. |
| `tests/test_messages.py` (new) | Style check: `ast` over every `.py` under `ptz_joystick/`. For each `Problem(...)` call with literal text: `what` starts with a capital and has no final period, `fix` has no final period and no "restart", and `text(then=RUN_AGAIN)` is within 120 characters. |
| `tests/contracts.py` `CameraContract` | Down: `send` returns False and `problem` is a `Problem`. Up: `problem` is `None`. Still logs once per outage. |
| `tests/config/test_loading.py`, `test_template.py` | `Problem` with the `what` / `fix` from the table, instead of `SystemExit` text. Encoding → its own `Problem`. |
| `tests/app/test_checks.py`, `test_startup.py` | `bad_setting` problems. `check_camera` raises the camera's `problem`. `prepare` reads `PTZ_PASSWORD` from a patched `user_env`. |
| `tests/controllers/test_winmm.py` | No device → `Problem`. |
| `tests/app/test_main.py` | Console: a `Problem` is logged to the default log file; waits for Enter only when `owns_console()` is True; exit code 1. Tray: "already running" → `message_box` with the text. Crash → CRITICAL with traceback, then the crash `Problem`. |
| `tests/windows/test_console.py` | `owns_console()` with a patched process list: only us and our parent → True; a shell too → False; empty → False. |
| `tests/app/test_session.py`, `test_status.py`, `test_tray.py` | `Report` gets `Problem` objects. Red adds `click Restart`, yellow doesn't. Controller unplugged: same text in the log, the status and the pop-up. |
| `tests/core/test_sender.py`, `tests/app/test_loop.py`, `tests/app/test_logs.py` | The log-only warnings use the new wording. |

### CI: `.github/workflows/ci.yml`

Both smoke tests match `Set the camera password first`. They switch to `The camera password is not set`. The console smoke test also proves the exe doesn't wait for Enter when run from a shell: it would hang the job.

### Manual check

About 5 minutes on a PC with the exes:

1. Double-click `ptz_joystick.exe` with no `PTZ_PASSWORD` → the message, then `Press Enter to close.`, and the line is in `ptz_joystick.log`.
2. Run it from a terminal → the same message, and the prompt returns at once.
3. `setx PTZ_PASSWORD` a wrong value, run the console exe again from the same terminal → `The camera refused the login. …` (the new value was read without a new terminal).
4. Tray, break a setting, Restart → red, pop-up ends `then click Restart.`
5. Tray, unplug the pad while driving → yellow, the pop-up and the hover text read the same, and so does the log line.

## Docs

- `docs/troubleshooting.md`: the symptom table uses the new `what` texts. "Open a new terminal" goes away.
- `docs/extending.md`: the camera `problem` rule, the controller `Problem` rule, "Writing a message".
- `README.md`: the tray table, where its texts change.
- `docs/development.md`: `core/problem.py` in the layout.

## Out of scope

- When pop-ups show, and the dot colors: unchanged.
- In the tray, a `Can't write the log file` warning has nowhere to go (no log file, no terminal). Same as today.
- Translation.
- Developer-only log lines.
