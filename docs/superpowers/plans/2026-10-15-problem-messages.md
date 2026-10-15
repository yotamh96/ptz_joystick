# Problem Messages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every error and warning the operator can read is a `Problem` (what, fix, detail), shown with the same words in the log, the tray and the console, with the restart step that fits the mode.

**Architecture:** A `Problem` exception in `core/problem.py` is raised (or logged) where the facts are known. `app/main.py` (console, and the tray before its icon exists) and `app/session.py` + `app/status.py` (tray) show it, each adding its own restart step. Cameras report why they failed through a new `Camera.problem` attribute instead of log records.

**Tech Stack:** Python 3.11+ stdlib only (`unittest`, `ast`, `ctypes`), ruff 0.16.10, mypy 2.4.0. Windows.

**Spec:** `docs/superpowers/specs/2026-10-15-problem-messages-design.md`

## Before Task 1 (the human does this)

The working tree has an uncommitted keyboard/focus change that touches files this plan also edits (`app/session.py`, `tests/app/test_session.py`, `README.md`, `docs/troubleshooting.md`, `docs/development.md`). Commit it first, so each task below commits only its own changes. Check: `git status --short` shows nothing modified. This plan is written against the tree *with* that change (no `KEYBOARD_IN_TRAY` in `session.py`).

## Global Constraints

- Python 3.11+ (CI tests 3.11 and 3.14). No new packages.
- Tests: `unittest`, mirroring the package (`tests/<folder>/test_<module>.py`). Run all: `python -m unittest discover -s tests -t .`
- Every task ends green on all three: the unit tests, `ruff check .`, `mypy` (settings in `mypy.ini`; it checks `tests/` too, with `check_untyped_defs`).
- Match the surrounding code: lines up to about 120 characters, short comments that say why.
- Restart steps, exactly: console `run ptz_joystick again` (`RUN_AGAIN` in `app/main.py`), tray `click Restart` (`CLICK_RESTART` in `app/status.py`).
- Message rules (spec, "Writing a message"):
  1. `what` says what is wrong, not what the code did. One short sentence, capital first letter, no period.
  2. `fix` is an order the operator can follow. It names the setting, file or command. No period.
  3. Never put "restart" or "run again" in `fix`: the console or the tray adds its own step.
  4. HTTP codes, exception text and full paths go in `detail`. Only the log shows it.
  5. Keep `text()` within 120 characters.
- English only.
- Commits: stage only the files the task lists. Message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A camera that comes back** must set `problem` back to `None`, or the tray keeps showing an old reason. → Task 2, `test_recovery_clears_the_reason`.
2. **Run from a terminal or CI**, the console must never wait for Enter: a wrong wait hangs the CI job. → Task 3, `test_console_logs_the_problem_with_the_restart_step` (no `input()`), the shell-on-the-list test, and a step timeout on the CI smoke test.
3. **A double-clicked onefile exe** runs as two processes (bootloader plus child), both on the console list: it must still count as owning its window. → Task 3, `test_double_clicked_exe_owns_its_window`. Windows Terminal hosting is only provable by hand: manual check 1 in Task 7.
4. **Password changed with `setx` while an old terminal holds the old value**: the new value must win, in both modes. → Task 4, `test_the_newest_setx_wins_even_in_an_old_terminal`.
5. **A wrong setting with a long value**: the tooltip cuts at 128, but the pop-up must show the whole text, ending with the restart step. → Task 5, `test_a_long_message_stays_whole_for_the_pop_up`.

---

### Task 1: The `Problem` type

**Files:**
- Create: `ptz_joystick/core/problem.py`
- Test: `tests/core/test_problem.py`

**Interfaces:**
- Produces: `Problem(what: str, fix: str = "", detail: str = "")`, an `Exception` with attributes `what`, `fix`, `detail`; `str(p) == p.what`. `Problem.text(then: str = "") -> str`. `Problem.log_line(then: str = "") -> str`. `crashed(e: BaseException) -> Problem`.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_problem.py`:

```python
import unittest

from ptz_joystick.core.problem import Problem, crashed


class TextTest(unittest.TestCase):
    def test_what_and_fix(self):
        self.assertEqual(Problem("No controller found", fix="Plug it in").text(), "No controller found. Plug it in.")

    def test_then_joins_the_fix(self):
        self.assertEqual(Problem("A", fix="B").text(then="click Restart"), "A. B, then click Restart.")

    def test_then_alone_becomes_the_order(self):
        self.assertEqual(Problem("A").text(then="click Restart"), "A. Click Restart.")

    def test_what_alone(self):
        self.assertEqual(Problem("A").text(), "A.")

    def test_detail_only_in_the_log_line(self):
        p = Problem("A", fix="B", detail="HTTP 401")
        self.assertEqual(p.text(), "A. B.")
        self.assertEqual(p.log_line(), "A. B. (HTTP 401)")
        self.assertEqual(p.log_line(then="click Restart"), "A. B, then click Restart. (HTTP 401)")

    def test_no_detail_no_brackets(self):
        self.assertEqual(Problem("A", fix="B").log_line(), "A. B.")

    def test_str_is_what(self):
        self.assertEqual(str(Problem("A", fix="B", detail="x")), "A")


class CrashedTest(unittest.TestCase):
    def test_plain_sentence_for_the_operator_repr_for_the_log(self):
        p = crashed(RuntimeError("boom"))
        self.assertEqual(p.text(), "Unexpected error in ptz_joystick. See the log for details.")
        self.assertEqual(p.detail, "RuntimeError('boom')")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python -m unittest tests.core.test_problem -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'ptz_joystick.core.problem'`

- [ ] **Step 3: Write the implementation**

Create `ptz_joystick/core/problem.py`:

```python
"""Problem: something the operator must fix, in their words. Raised (or logged) where the facts are known; the
console (app/main.py) and the tray (app/status.py) show it, each adding its own restart step. How to word one:
docs/extending.md, "Writing a message"."""


class Problem(Exception):
    """what: what is wrong. fix: what to do about it. detail: the technical cause, for the log only."""

    def __init__(self, what: str, fix: str = "", detail: str = ""):
        super().__init__(what)
        self.what, self.fix, self.detail = what, fix, detail

    def text(self, then: str = "") -> str:
        """What the operator sees. then: the restart step ("click Restart"), only when the app stopped."""
        if self.fix:
            return f"{self.what}. {self.fix}, then {then}." if then else f"{self.what}. {self.fix}."
        return f"{self.what}. {then[:1].upper()}{then[1:]}." if then else f"{self.what}."

    def log_line(self, then: str = "") -> str:
        """text(then), plus the detail in brackets."""
        return f"{self.text(then)} ({self.detail})" if self.detail else self.text(then)


def crashed(e: BaseException) -> Problem:
    """An exception nobody expected: a plain sentence for the operator, its repr for the log."""
    return Problem("Unexpected error in ptz_joystick", fix="See the log for details", detail=repr(e))
```

- [ ] **Step 4: Run the tests, lint and types**

Run: `python -m unittest tests.core.test_problem -v` → 8 tests OK.
Run: `python -m unittest discover -s tests -t .` → OK.
Run: `ruff check .` and `mypy` → no errors.

- [ ] **Step 5: Commit**

```bash
git add ptz_joystick/core/problem.py tests/core/test_problem.py
git commit -m "Problem: what the operator must fix, in their words

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The camera says why it failed

**Files:**
- Modify: `ptz_joystick/cameras/__init__.py` (the `Camera` Protocol)
- Modify: `ptz_joystick/cameras/ptzoptics.py`
- Modify: `tests/contracts.py` (`CameraContract`)
- Modify: `tests/cameras/test_ptzoptics.py`
- Modify: `tests/fakes.py` (`RecordingCamera`)
- Modify: `tests/core/test_sender.py` (`FakeCamera`)

**Interfaces:**
- Consumes: `Problem` from Task 1.
- Produces: `Camera.problem: Problem | None`, why the last `send` failed; `None` after a success. Every fake camera passed where a `Camera` is expected now needs `problem: Problem | None = None`, or mypy fails.

- [ ] **Step 1: Write the failing tests**

In `tests/contracts.py`, add the import `from ptz_joystick.core.problem import Problem` (after the `ptz_joystick.core.commands` import) and this test to `CameraContract`, after `test_camera_down_returns_false_and_logs_once`:

```python
    def test_camera_down_says_why_and_up_says_nothing(self):
        down = self.make(up=False)
        with self.assertLogs(level="WARNING") as logs:
            down.send(PanTilt(0, 0))
        problem = down.problem
        assert isinstance(problem, Problem), problem
        self.assertIn(problem.what, logs.output[0])                 # the log line is the operator's sentence
        up = self.make(up=True)
        up.send(PanTilt(0, 0))
        self.assertIsNone(up.problem)
```

In `tests/cameras/test_ptzoptics.py`, replace `test_outage_logs_once_then_recovery` and `test_wrong_password_says_so` with:

```python
    def test_outage_logs_once_then_recovery(self):
        down = requests.ConnectTimeout("timed out")
        cam = camera_answering(down, down, down, 200)
        with self.assertLogs("ptz_joystick.cameras.ptzoptics", "INFO") as logs:
            results = [cam.send(PanTilt(0, 0)) for _ in range(4)]
        self.assertEqual(results, [False, False, False, True])
        self.assertEqual(len(logs.output), 2, logs.output)
        self.assertIn("Can't reach the camera at http://cam. Check host in ptz_joystick.toml and the network.",
                      logs.output[0])
        self.assertIn("The camera is answering again (was: unreachable)", logs.output[1])

    def test_recovery_clears_the_reason(self):
        cam = camera_answering(requests.ConnectTimeout("x"), 200)
        with self.assertLogs("ptz_joystick.cameras.ptzoptics", "INFO"):
            cam.send(PanTilt(0, 0))
            self.assertIsNotNone(cam.problem)
            cam.send(PanTilt(0, 0))
        self.assertIsNone(cam.problem)                  # or the tray would keep showing an old reason

    def test_wrong_password_says_so(self):
        cam = camera_answering(401)
        with self.assertLogs("ptz_joystick.cameras.ptzoptics", "WARNING") as logs:
            self.assertFalse(cam.send(PanTilt(0, 0)))
        problem = cam.problem
        assert problem is not None
        self.assertEqual(problem.text(),
                         "The camera refused the login. Check user in ptz_joystick.toml and PTZ_PASSWORD.")
        self.assertIn("(HTTP 401)", logs.output[0])
```

(`test_new_kind_of_failure_is_logged` stays: its `"500"` is now in the detail, `HTTP 500 to PanTilt(...)`.)

- [ ] **Step 2: Run them to make sure they fail**

Run: `python -m unittest tests.cameras.test_ptzoptics -v`
Expected: FAIL / ERROR in `test_camera_down_says_why_and_up_says_nothing` (`AttributeError: 'PtzOpticsCamera' object has no attribute 'problem'`), `test_outage_logs_once_then_recovery`, `test_recovery_clears_the_reason`, `test_wrong_password_says_so`.

- [ ] **Step 3: Implement**

`ptz_joystick/cameras/__init__.py`, whole file:

```python
"""Camera port: the one thing the core needs from a camera. The core never imports an adapter."""
from typing import Protocol

from ..core.commands import Command
from ..core.problem import Problem


class Camera(Protocol):
    problem: Problem | None
    """Why the last send() failed, in the operator's words; None after a success. The tray shows it."""

    def send(self, cmd: Command, /) -> bool:
        """Send one command from core/commands.py. True = the camera took it.

        Rules for an adapter:
        - PanTilt(0, 0) is "stop" and must always work: it is the startup check and the last thing sent.
        - Camera down, timeout, refused: set problem to why, as a Problem (core/problem.py; wording rules in
          docs/extending.md, "Writing a message"), return False, and log problem.log_line() once per outage,
          not per call (see ptzoptics.py). After a success, set problem back to None. The sender retries stick
          moves until taken and drops a button action after 3 refusals.
        - A command type this camera can't do at all (a camera without zoom, say): raise TypeError. The
          sender drops it.
        - Return within about a second (use a timeout): at shutdown the stops get 3 s in total.
        - Called from one thread at a time, so no locking needed.

        Each adapter module also has TOP_SPEEDS: the most pan_max / tilt_max / zoom_max may be for this camera,
        e.g. {"pan_max": 24, "tilt_max": 20, "zoom_max": 7}. Startup refuses settings above them.

        To add a camera: write the adapter, add a line to CAMERAS in app/registry.py, and subclass
        tests/contracts.py CameraContract in its tests. mypy (in CI) checks the adapter against this signature
        where CAMERAS lists it. The "/" means the parameter's name is free.
        """
```

`ptz_joystick/cameras/ptzoptics.py`: add `from ..core.problem import Problem` after the `..core.commands` import, then replace the whole `PtzOpticsCamera` class with:

```python
class PtzOpticsCamera:
    def __init__(self, host, user, password, timeout=1.0, session=None):
        self._host = host
        self._url = f"{host}/cgi-bin/"
        self._timeout = timeout
        self._session = session or requests.Session()     # tests pass a fake
        self._session.auth = HTTPDigestAuth(user, password)
        self._failing = None    # kind of the current failure, so an outage logs once, not every retry
        self.problem: Problem | None = None

    def send(self, cmd: Command) -> bool:
        try:
            r = self._session.get(self._url + to_query(cmd), timeout=self._timeout)
        except requests.RequestException as e:
            return self._failed("unreachable", Problem(f"Can't reach the camera at {self._host}",
                                                       fix="Check host in ptz_joystick.toml and the network",
                                                       detail=str(e)))
        if r.status_code == 200:
            if self._failing:
                log.info("The camera is answering again (was: %s)", self._failing)
                self._failing = None
            self.problem = None
            return True
        if r.status_code == 401:
            return self._failed(401, Problem("The camera refused the login",
                                             fix="Check user in ptz_joystick.toml and PTZ_PASSWORD",
                                             detail="HTTP 401"))
        return self._failed(r.status_code, Problem("The camera refused a command",
                                                   fix="Check that its web page opens in a browser",
                                                   detail=f"HTTP {r.status_code} to {cmd}"))

    def _failed(self, kind, problem: Problem) -> bool:
        self.problem = problem
        if kind != self._failing:
            log.warning(problem.log_line())
            self._failing = kind
        else:
            log.debug(problem.log_line())
        return False
```

`tests/fakes.py`: add `from ptz_joystick.core.problem import Problem` after the `ptz_joystick.controllers` import, and give `RecordingCamera` the attribute:

```python
class RecordingCamera:
    problem: Problem | None = None      # the Camera port's "why the last send failed"; this one never fails

    def __init__(self):
        self.calls = []
```

`tests/core/test_sender.py`: add `from ptz_joystick.core.problem import Problem` after the `ptz_joystick.core.commands` import, and give `FakeCamera` the same attribute, as its first line:

```python
class FakeCamera:
    """Answers like the real one: False = camera said 500 / timed out."""
    problem: Problem | None = None      # the Camera port's attribute; the sender never reads it

    def __init__(self, fail_first=0, delay=0.0):
```

- [ ] **Step 4: Run the tests, lint and types**

Run: `python -m unittest tests.cameras.test_ptzoptics -v` → all OK.
Run: `python -m unittest discover -s tests -t .` → OK.
Run: `ruff check .` and `mypy` → no errors. If mypy names another fake camera without `problem`, give it the same `problem: Problem | None = None` line.

- [ ] **Step 5: Commit**

```bash
git add ptz_joystick/cameras/__init__.py ptz_joystick/cameras/ptzoptics.py tests/contracts.py tests/cameras/test_ptzoptics.py tests/fakes.py tests/core/test_sender.py
git commit -m "Camera: say why a send failed, as a Problem

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The console shows problems and crashes, and waits when double-clicked

**Files:**
- Modify: `ptz_joystick/app/main.py`
- Modify: `ptz_joystick/__main__.py`
- Modify: `ptz_joystick/windows/console.py`
- Modify: `ptz_joystick/app/startup.py` (`bootstrap_log` moves here)
- Modify: `ptz_joystick/app/tray.py` (no longer sets up logging; imports `bootstrap_log`)
- Modify: `.github/workflows/ci.yml` (step timeout)
- Test: `tests/app/test_main.py` (rewrite), `tests/test_entry_point.py`, `tests/windows/test_console.py`, `tests/app/test_tray.py`

**Interfaces:**
- Consumes: `Problem`, `crashed` (Task 1).
- Produces: `app.main.RUN_AGAIN = "run ptz_joystick again"`. `app.startup.bootstrap_log(path: Path) -> Path`. `windows.console.owns_console() -> bool` and `windows.console._console_pids() -> list[int]`. `main()` catches `Problem` and any `Exception`. `SystemExit` and `KeyboardInterrupt` still pass through untouched, so the old `SystemExit` raisers keep working until Task 4.

- [ ] **Step 1: Write the failing tests**

Replace `tests/app/test_main.py` with:

```python
import unittest
from pathlib import Path
from unittest import mock

import ptz_joystick.app.main as app_main
from ptz_joystick.core.problem import Problem


class MainTest(unittest.TestCase):
    """Shared setUp: no real log file, no real mutex, no message box, no waiting on the keyboard."""

    def setUp(self):
        self.setup_logging = self.enterContext(mock.patch.object(app_main, "setup_logging"))
        self.claim = self.enterContext(mock.patch.object(app_main.single_instance, "claim", return_value=True))
        self.box = self.enterContext(mock.patch.object(app_main, "message_box"))
        self.owns = self.enterContext(mock.patch.object(app_main, "owns_console", return_value=False))
        self.input = self.enterContext(mock.patch("builtins.input"))

    def fails(self, argv, error=None) -> list[str]:
        """main(argv) with the console (or, with --tray, the tray) raising error; None = main raises its own.
        Checks it exits 1. -> the log lines."""
        target = "run_tray" if "--tray" in argv else "_console"
        with mock.patch.object(app_main, target, side_effect=error), \
                self.assertLogs("ptz_joystick", "ERROR") as logs, self.assertRaises(SystemExit) as stopped:
            app_main.main(argv)
        self.assertEqual(stopped.exception.code, 1)
        return logs.output


class AlreadyRunningTest(MainTest):
    def setUp(self):
        super().setUp()
        self.claim.return_value = False

    def test_console_logs_it_with_the_fix(self):
        lines = self.fails([])
        self.assertIn("Another ptz_joystick is already running. Quit it first", lines[0])
        self.box.assert_not_called()                    # the console shows the log line itself

    def test_tray_also_shows_a_message_box(self):
        self.fails(["--tray"])
        self.box.assert_called_once_with("Another ptz_joystick is already running. Quit it first: its tray icon or "
                                         "console window, then run ptz_joystick again.")


class ProblemTest(MainTest):
    PASSWORD = Problem("The camera password is not set", fix='Run setx PTZ_PASSWORD "..." in a terminal')

    def test_console_logs_the_problem_with_the_restart_step(self):
        lines = self.fails([], self.PASSWORD)
        self.assertIn('The camera password is not set. Run setx PTZ_PASSWORD "..." in a terminal, then run '
                      'ptz_joystick again.', lines[0])
        self.input.assert_not_called()                  # run from a terminal: the prompt comes back at once
        self.box.assert_not_called()

    def test_double_clicked_console_waits_for_enter(self):
        self.owns.return_value = True
        self.fails([], self.PASSWORD)
        self.input.assert_called_once_with("Press Enter to close.")

    def test_no_keyboard_to_wait_for_still_exits(self):
        self.owns.return_value = True
        self.input.side_effect = EOFError
        self.fails([], self.PASSWORD)

    def test_tray_shows_the_problem_in_a_message_box(self):
        self.fails(["--tray"], Problem("A", fix="B"))
        self.box.assert_called_once_with("A. B, then run ptz_joystick again.")
        self.input.assert_not_called()

    def test_crash_logs_the_traceback_and_shows_a_plain_sentence(self):
        lines = self.fails(["--tray"], RuntimeError("boom"))
        self.assertTrue(lines[0].startswith("CRITICAL"), lines[0])
        self.assertIn("(RuntimeError('boom'))", lines[0])
        self.assertIn("Traceback", lines[0])
        self.box.assert_called_once_with("Unexpected error in ptz_joystick. See the log for details, then run "
                                         "ptz_joystick again.")

    def test_ctrl_c_is_not_a_crash(self):
        with mock.patch.object(app_main, "_console", side_effect=KeyboardInterrupt), \
                self.assertNoLogs("ptz_joystick", "ERROR"), self.assertRaises(KeyboardInterrupt):
            app_main.main([])


class TrayFlagTest(MainTest):
    def test_tray_flag_hands_over_to_the_tray(self):
        with mock.patch.object(app_main, "run_tray") as run_tray:
            app_main.main(["--tray", "--keyboard", "--config", "x.toml"])
        run_tray.assert_called_once_with(Path("x.toml"), True)

    def test_logging_starts_before_the_settings_are_read(self):
        with mock.patch.object(app_main, "run_tray"):
            app_main.main(["--tray", "--config", r"C:\tools\ptz_joystick.toml"])
        [settings] = self.setup_logging.call_args.args
        self.assertEqual(settings.log_file, r"C:\tools\ptz_joystick.log")


if __name__ == "__main__":
    unittest.main()
```

Replace `tests/test_entry_point.py` with (crash handling moved into `main()`, tested above):

```python
import runpy
import unittest
from unittest import mock


class EntryPointTest(unittest.TestCase):
    def test_ctrl_c_and_clean_exit_stay_quiet(self):
        for exc in (KeyboardInterrupt(), SystemExit(1)):
            with self.subTest(exc=exc), mock.patch("ptz_joystick.app.main.main", side_effect=exc), \
                    self.assertNoLogs("ptz_joystick", "CRITICAL"):
                try:
                    runpy.run_module("ptz_joystick", run_name="__main__")
                except SystemExit as e:
                    self.assertEqual(e.code, 1)


if __name__ == "__main__":
    unittest.main()
```

In `tests/windows/test_console.py`, add `import os`, `from unittest import mock` and `from ptz_joystick.windows import console` to the imports, and this class before `if __name__ == "__main__":`:

```python
class OwnsConsoleTest(unittest.TestCase):
    def owns(self, pids):
        with mock.patch.object(console, "_console_pids", return_value=pids):
            return console.owns_console()

    def test_double_clicked_exe_owns_its_window(self):
        self.assertTrue(self.owns([os.getpid()]))
        self.assertTrue(self.owns([os.getppid(), os.getpid()]))     # onefile exe: the bootloader is our parent

    def test_a_shell_on_the_console_means_a_terminal(self):
        shell = max(os.getpid(), os.getppid()) + 1
        self.assertFalse(self.owns([shell, os.getppid(), os.getpid()]))

    def test_no_console_is_not_ours(self):
        self.assertFalse(self.owns([]))

    def test_the_real_list_reads(self):
        self.assertIsInstance(console._console_pids(), list)
```

In `tests/app/test_tray.py`, `test_ctrl_c_in_a_terminal_still_stops_the_camera`: delete `mock.patch.object(tray, "setup_logging"), ` from its `with` line (run_tray no longer sets up logging). The line becomes:

```python
        with mock.patch.object(tray, "HiddenWindow", Interrupted), mock.patch.object(tray, "TrayIcon", Recorded), \
                mock.patch.object(tray, "on_console_close"), self.assertRaises(KeyboardInterrupt):
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `python -m unittest tests.app.test_main tests.windows.test_console tests.app.test_tray -v`
Expected: ERRORs: `module 'ptz_joystick.app.main' has no attribute 'owns_console'` (every `MainTest`), `no attribute '_console_pids'`; `test_ctrl_c_in_a_terminal_still_stops_the_camera` may pass already.

- [ ] **Step 3: Implement**

`ptz_joystick/windows/console.py`: add `import os` to the imports and these two functions at the end of the file:

```python
def _console_pids() -> list[int]:
    """The processes attached to this console; empty without one."""
    pids = (wintypes.DWORD * 64)()
    n = ctypes.windll.kernel32.GetConsoleProcessList(pids, len(pids))
    return list(pids[:min(n, len(pids))])


def owns_console() -> bool:
    """True when this console window was opened for us (the exe was double-clicked), so it closes the moment we
    exit. A terminal's shell on the list means it wasn't. Our parent counts as us: a PyInstaller onefile exe runs
    as two processes."""
    pids = _console_pids()
    return bool(pids) and set(pids) <= {os.getpid(), os.getppid()}
```

`ptz_joystick/app/startup.py`: add after the `log = ...` line:

```python
def bootstrap_log(path: Path) -> Path:
    """The log file until the settings are read: the default one, next to the settings file."""
    return path.parent / Settings().log_file
```

`ptz_joystick/app/tray.py`:
- Delete the `bootstrap_log` function, and the imports `from ..config import Settings` and `from .logs import setup_logging`.
- Add `from .startup import bootstrap_log` (after `from .session import run_session`).
- `run_tray` becomes:

```python
def run_tray(path: Path, keyboard: bool):
    """Until Quit. main() already logs to the default log file, so even a missing password gets logged."""
    log.info("ptz_joystick %s (tray)", VERSION)
    app = TrayApp(path, keyboard)
    if sys.stderr:                  # started from a terminal (--tray while developing): closing it is a Quit
        on_console_close(app.shutdown)
    app.start_session()
    try:
        app.run()
    finally:                        # also on Ctrl+C in that terminal: never leave the camera moving
        app.shutdown()
```

`ptz_joystick/app/main.py`, whole file:

```python
"""Composition root: the only place that builds hardware objects, picked from the tables in registry.py.
Reads the settings, runs the startup checks, then hands over to the loop. --tray hands over to tray.py instead.
A Problem or a crash ends here, in both modes: logged, shown where the operator looks, exit 1."""
import argparse
import logging
from pathlib import Path

from .. import config
from ..core.problem import Problem, crashed
from ..core.sender import CommandSender
from ..windows import single_instance
from ..windows.console import on_console_close, owns_console
from ..windows.message_box import message_box
from . import updates
from .checks import check_axes, check_camera
from .logs import setup_logging
from .loop import run, stop_camera
from .registry import CAMERAS, CONTROLLERS
from .startup import bootstrap_log, prepare
from .tray import run_tray
from .version import VERSION

log = logging.getLogger(__name__)
RUN_AGAIN = "run ptz_joystick again"    # the restart step, after a problem that stopped ptz_joystick


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ptz_joystick", description="Drive a PTZOptics camera with a game controller.")
    parser.add_argument("--config", type=Path, default=config.default_path(),
                        help=f"settings file (default: {config.default_path()})")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--keyboard", action="store_true", help="same as controller = \"keyboard\" in the settings file")
    parser.add_argument("--tray", action="store_true", help="run as an icon in the notification area, not in a console")
    args = parser.parse_args(argv)
    setup_logging(config.Settings(log_file=str(bootstrap_log(args.config))))     # until the settings are read
    try:
        if not single_instance.claim():
            raise Problem("Another ptz_joystick is already running", fix="Quit it first: its tray icon or console window")
        if args.tray:
            run_tray(args.config, args.keyboard)
        else:
            _console(args.config, args.keyboard)
    except Problem as p:
        log.error(p.log_line(then=RUN_AGAIN))
        _show(p, args.tray)
    except Exception as e:
        p = crashed(e)
        log.critical(p.log_line(then=RUN_AGAIN), exc_info=True)
        _show(p, args.tray)


def _show(p: Problem, tray: bool):
    """Where the operator reads p, after its log line. Then exit 1."""
    if tray:                                # no console: a message box
        message_box(p.text(then=RUN_AGAIN))
    elif owns_console():                    # double-clicked: the window would close before anyone reads it
        try:
            input("Press Enter to close.")
        except EOFError:                    # no keyboard to wait for
            pass
    raise SystemExit(1)


def _console(path: Path, keyboard: bool):
    s = prepare(path, keyboard)
    if s.check_updates:
        updates.check_in_background(VERSION)
    camera = CAMERAS[s.camera].connect(s)
    check_camera(camera, s.host, path)
    controller = CONTROLLERS[s.controller](s)
    check_axes(controller, s, path)
    sender = CommandSender(camera)

    def console_closing():
        log.info("Console closing.")
        stop_camera(sender)

    on_console_close(console_closing)
    log.info("Driving camera %s. Ctrl+C to quit.", s.host)
    run(s, controller, sender)
```

`ptz_joystick/__main__.py`, whole file:

```python
from .app.main import main

try:
    main()                      # problems and crashes are logged and shown there
except KeyboardInterrupt:
    pass
```

`.github/workflows/ci.yml`: give the console smoke test a timeout, so a wrong "Press Enter to close." fails fast instead of hanging the job:

```yaml
      - name: Smoke test
        timeout-minutes: 5               # a wrong "Press Enter to close." wait would hang the job
        run: |
```

- [ ] **Step 4: Run the tests, lint and types**

Run: `python -m unittest tests.app.test_main tests.windows.test_console tests.app.test_tray tests.test_entry_point -v` → all OK.
Run: `python -m unittest discover -s tests -t .` → OK. Check `git status --short` shows no new `ptz_joystick.log` in the repo folder (the tests patch `setup_logging`).
Run: `ruff check .` and `mypy` → no errors.

- [ ] **Step 5: Commit**

```bash
git add ptz_joystick/app/main.py ptz_joystick/__main__.py ptz_joystick/windows/console.py ptz_joystick/app/startup.py ptz_joystick/app/tray.py .github/workflows/ci.yml tests/app/test_main.py tests/test_entry_point.py tests/windows/test_console.py tests/app/test_tray.py
git commit -m "Console: log every problem and crash, wait for Enter when double-clicked

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Raise `Problem` instead of `SystemExit`

**Files:**
- Modify: `ptz_joystick/config/loading.py`, `ptz_joystick/config/__init__.py`, `ptz_joystick/config/template.py`
- Modify: `ptz_joystick/app/checks.py`
- Modify: `ptz_joystick/controllers/winmm.py`, `ptz_joystick/controllers/__init__.py` (docstring)
- Modify: `ptz_joystick/app/startup.py` (reads the registry password)
- Modify: `ptz_joystick/app/session.py` (catches `Problem`), `ptz_joystick/app/status.py` (`CLICK_RESTART`)
- Modify: `.github/workflows/ci.yml` (smoke test text)
- Test: `tests/config/test_loading.py`, `tests/config/test_template.py`, `tests/app/test_checks.py`, `tests/controllers/test_winmm.py`, `tests/app/test_startup.py`, `tests/app/test_session.py`

**Interfaces:**
- Consumes: `Problem` (Task 1), `Camera.problem` (Task 2), `main()` handling `Problem` (Task 3).
- Produces: `config.bad_setting(path: Path, message: object) -> Problem`. `app.status.CLICK_RESTART = "click Restart"`. `prepare()` reads `PTZ_PASSWORD` from `HKCU\Environment` first (patch `app.startup.user_env` in tests). The tray's `Report` still takes strings in this task; Task 5 changes it to `Problem` objects.

- [ ] **Step 1: Write the failing tests**

`tests/config/test_loading.py`: add `from ptz_joystick.core.problem import Problem`, then replace these four tests:

```python
    def test_bad_file_names_file_and_key(self):
        for text, word in [
            ('hots = "x"', "unknown setting 'hots'"),
            ('password = "x"', "PTZ_PASSWORD"),
            ('pan_max = "24"', "pan_max must be a whole number"),
            ("buttons = 3", r"buttons must be a \[table\]"),
            ("pan_max = true", "pan_max"),
            ('debug = "yes"', "debug must be true or false"),
            ("deadzone = 0.9", "deadzone"),                  # Settings validation still runs
            ('[buttons]\n0 = "home"', "bad command 'home'"),
            ('[buttons]\n0 = "preset"', "bad command"),
            ('[buttons]\n0 = "preset -1"', "bad command 'preset -1'"),
            ('[buttons]\n5 = "tracking 1"', "bad command 'tracking 1'"),     # tracking takes no number
            ("timeout = inf", "timeout"),                    # TOML allows inf
            ('[buttons]\n0 = 3', "bad command"),
            ('[buttons]\nx = "preset 1"', "index must be a number"),
            ("[buttons]\n40 = \"preset 1\"", "buttons"),
            ("host = ", "Invalid value"),                    # TOML syntax error
        ]:
            with self.subTest(text=text):
                with self.assertRaises(Problem) as cm:
                    self.load(text)
                self.assertRegex(cm.exception.what, f"^Bad setting in {config.FILE_NAME}: .*{word}")
                self.assertEqual(cm.exception.fix, "Fix it and save")

    def test_password_checked_before_file(self):
        with mock.patch.dict(os.environ, {"PTZ_PASSWORD": ""}), self.assertRaises(Problem) as cm:
            config.load(Path("does-not-exist.toml"))
        self.assertEqual(cm.exception.text(),
                         'The camera password is not set. Run setx PTZ_PASSWORD "..." in a terminal.')

    def test_unreadable_file_names_it(self):
        with mock.patch.dict(os.environ, {"PTZ_PASSWORD": "pw"}), self.assertRaises(Problem) as cm:
            config.load(Path("does-not-exist.toml"))
        self.assertEqual(cm.exception.what, "Can't read does-not-exist.toml")
        self.assertIn("does-not-exist.toml", cm.exception.detail)
```

and in `EncodingTest`:

```python
    def test_other_encoding_says_save_as_utf8(self):
        raw = '# הגדרות\nhost = "http://10.0.0.1"\n'.encode("cp1255")      # Hebrew comment saved as ANSI
        with self.assertRaises(Problem) as cm:
            self.load_bytes(raw)
        self.assertEqual(cm.exception.text(),
                         f"Wrong text encoding in {config.FILE_NAME}. In Notepad: File > Save as > Encoding: UTF-8.")
```

(Delete the old `test_bad_file_is_clean_exit_naming_file_and_key` and `test_unreadable_file_is_clean_exit`.)

`tests/config/test_template.py`: add `from ptz_joystick.core.problem import Problem` and to `TemplateTest`:

```python
    def test_unwritable_folder_says_where_to_move(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(Problem) as cm:
            config.write_template_if_missing(Path(d) / "missing" / config.FILE_NAME)
        self.assertEqual(cm.exception.text(),
                         f"Can't create {config.FILE_NAME}. Move the exe to a folder you can write to.")
```

`tests/app/test_checks.py`: add `from ptz_joystick.core.problem import Problem`; replace `CheckCameraTest.test_camera_that_refuses_stops_startup` with:

```python
    def test_camera_that_refuses_stops_startup_with_its_reason(self):
        class Refusing(RecordingCamera):
            def send(self, cmd):
                super().send(cmd)
                self.problem = Problem("The camera refused the login", fix="Check user and PTZ_PASSWORD")
                return False

        cam = Refusing()
        with self.assertRaises(Problem) as cm:
            check_camera(cam, "http://cam", Path("ptz_joystick.toml"))
        self.assertIs(cm.exception, cam.problem)
        self.assertEqual(cam.calls, [PanTilt(0, 0)])     # probe is a harmless stop

    def test_a_camera_that_gives_no_reason_still_names_the_checks(self):
        class Silent(RecordingCamera):
            def send(self, cmd):
                return False

        with self.assertRaises(Problem) as cm:
            check_camera(Silent(), "http://cam", Path("ptz_joystick.toml"))
        self.assertEqual(cm.exception.text(), "The camera at http://cam didn't answer. Check host in "
                                              "ptz_joystick.toml, the network, and PTZ_PASSWORD.")
```

In the same file change every `self.assertRaisesRegex(SystemExit, ...)` to `self.assertRaisesRegex(Problem, ...)` (3 places), and the axes one's pattern to:

```python
        with self.assertRaisesRegex(Problem, r"no axis R \(it has X, Y\)"):
```

`tests/controllers/test_winmm.py`: add `from ptz_joystick.core.problem import Problem` and before `if __name__ == "__main__":`:

```python
class DiscoverTest(unittest.TestCase):
    def test_no_device_says_what_to_check(self):
        with mock.patch.object(winmm, "_pos", return_value=None), self.assertRaises(Problem) as cm:
            winmm.discover()
        self.assertEqual(cm.exception.text(), "No controller found. Plug it in and check that it shows in joy.cpl.")
```

`tests/app/test_startup.py`: add `from ptz_joystick.app import startup` and `from ptz_joystick.core.problem import Problem`. In `setUp` add as its last line:

```python
        self.enterContext(mock.patch.object(startup, "user_env", return_value=None))   # never the real registry
```

Change both `assertRaisesRegex(SystemExit, ...)` to `assertRaisesRegex(Problem, ...)`; the password one's text becomes `"The camera password is not set"`. Add:

```python
    def test_a_password_set_only_with_setx_is_found(self):
        del os.environ["PTZ_PASSWORD"]
        with mock.patch.object(startup, "user_env", return_value="from-setx"), \
                self.assertLogs("ptz_joystick.app.startup", "INFO"):
            self.assertEqual(prepare(self.path, keyboard=False).password, "from-setx")

    def test_the_newest_setx_wins_even_in_an_old_terminal(self):
        os.environ["PTZ_PASSWORD"] = "old"              # what this terminal started with
        with mock.patch.object(startup, "user_env", return_value="new"), \
                self.assertLogs("ptz_joystick.app.startup", "INFO"):
            self.assertEqual(prepare(self.path, keyboard=False).password, "new")
```

`tests/app/test_session.py`:
- Imports: `from ptz_joystick.app import session, startup` and add `from ptz_joystick.core.problem import Problem`.
- `NO_PAD = Problem("No controller found", fix="Plug it in and check that it shows in joy.cpl")`
- In `setUp`, the `user_env` patch becomes `mock.patch.object(startup, "user_env", return_value=None)`.
- Delete `test_a_password_set_with_setx_after_start_is_used` (now in `test_startup.py`).
- Replace three tests:

```python
    def test_missing_password_is_red_with_the_fix(self):
        del os.environ["PTZ_PASSWORD"]
        logs = self.run_session()
        self.assertEqual(self.report.calls, [("stopped", 'The camera password is not set. Run setx PTZ_PASSWORD '
                                                         '"..." in a terminal, then click Restart.')])
        self.assertTrue(any(line.startswith("ERROR") and "then click Restart" in line for line in logs.output))

    def test_no_controller_waits_and_tries_again(self):
        self.controllers.insert(0, NO_PAD)
        self.run_session()
        self.assertEqual(self.names(), ["log_to", "waiting_for_stick", "no_controller", "waiting_for_stick", "driving"])
        self.assertIn(("no_controller", NO_PAD.text()), self.report.calls)
```

and in `test_a_crash_while_driving_stops_the_camera_and_goes_red` the first assertion becomes:

```python
        self.assertEqual(self.report.calls[-1],
                         ("stopped", "Unexpected error in ptz_joystick. See the log for details, then click Restart."))
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `python -m unittest tests.config.test_loading tests.config.test_template tests.app.test_checks tests.controllers.test_winmm tests.app.test_startup tests.app.test_session -v`
Expected: FAILs and ERRORs: `SystemExit` raised where `Problem` is expected, `module 'ptz_joystick.app.startup' has no attribute 'user_env'`.

- [ ] **Step 3: Implement**

`ptz_joystick/config/loading.py`:
- Add `from ..core.problem import Problem` after the `..core.commands` import.
- In `from_dict`, the password line becomes:

```python
            raise ValueError('remove password, set it with setx PTZ_PASSWORD "..." instead')
```

- Replace `read_text` and `load`, and add `bad_setting` before them:

```python
def bad_setting(path: Path, message: object) -> Problem:
    """The one wording for any wrong setting. message: what's wrong with it, e.g. "unknown setting 'hots'"."""
    return Problem(f"Bad setting in {path.name}: {message}", fix="Fix it and save", detail=str(path))


def read_text(path: Path) -> str:
    """The settings file as text, in any encoding Notepad saves: UTF-8 (with or without BOM) or "Unicode"."""
    raw = path.read_bytes()
    encoding = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    try:
        return raw.decode(encoding)
    except UnicodeDecodeError:
        raise Problem(f"Wrong text encoding in {path.name}", fix="In Notepad: File > Save as > Encoding: UTF-8",
                      detail=str(path)) from None


def load(path: Path) -> Settings:
    password = os.environ.get("PTZ_PASSWORD")
    if not password:
        raise Problem("The camera password is not set", fix='Run setx PTZ_PASSWORD "..." in a terminal')
    try:
        s = from_dict(tomllib.loads(read_text(path)), password)
        # A relative log file sits next to the settings file (and so the exe), whatever folder you run from.
        return replace(s, log_file=str(path.parent / s.log_file)) if s.log_file else s
    except (tomllib.TOMLDecodeError, ValueError) as e:
        raise bad_setting(path, e) from None
    except OSError as e:
        raise Problem(f"Can't read {path.name}", fix="Check that you can open it in Notepad", detail=str(e)) from None
```

`ptz_joystick/config/__init__.py`: export it:

```python
from .loading import bad_setting, from_dict, load, parse_command
```

and add `"bad_setting",` to `__all__` right after `"Settings",`.

`ptz_joystick/config/template.py`: add `from ..core.problem import Problem` after `from pathlib import Path`, and the `except` in `write_template_if_missing` becomes:

```python
    except OSError as e:
        raise Problem(f"Can't create {path.name}", fix="Move the exe to a folder you can write to",
                      detail=str(e)) from None
```

`ptz_joystick/app/checks.py`, whole file:

```python
"""Startup checks: catch a wrong setting or a missing device now, with a message naming the fix, instead of
mid-session."""
from pathlib import Path

from ..cameras import Camera
from ..config import Settings, bad_setting
from ..controllers import Controller
from ..core.commands import PanTilt
from ..core.problem import Problem
from .registry import CAMERAS, CONTROLLERS


def check_types(s: Settings, settings_path: Path):
    """camera and controller name known types, and the speeds fit that camera. Before anything connects."""
    for name, table in (("camera", CAMERAS), ("controller", CONTROLLERS)):
        if getattr(s, name) not in table:
            raise bad_setting(settings_path, f"{name} must be one of {', '.join(table)}, got {getattr(s, name)!r}")
    for name, top in CAMERAS[s.camera].top_speeds.items():
        if getattr(s, name) > top:
            raise bad_setting(settings_path, f"{name} can be at most {top} for camera {s.camera!r}, "
                                             f"got {getattr(s, name)}")


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
```

`ptz_joystick/controllers/winmm.py`: add `from ..core.problem import Problem` to the imports; in `discover()`:

```python
    if not start:
        raise Problem("No controller found", fix="Plug it in and check that it shows in joy.cpl")
```

`ptz_joystick/controllers/__init__.py`: in the `Controller.read` docstring, the sentence `With no device, it raises SystemExit("<what to check>").` becomes:

```
        may wait for the user. With no device, it raises Problem (core/problem.py): what's missing and what to
        check. The tray retries it every 5 s. Annotate its return
```

(keep the rest of that paragraph as is; re-wrap the lines to about 120 characters.)

`ptz_joystick/app/startup.py`: add `import os` and `from ..windows.user_env import user_env`; update the module docstring's first line to `"""Startup steps the console and the tray share: the password, the settings file, the settings and their checks,` and `prepare` becomes:

```python
def prepare(path: Path, keyboard: bool) -> Settings:
    """The settings from path (written from the template on a first run), checked, with logging set up from them.
    keyboard: the --keyboard flag. Raises Problem naming the fix when PTZ_PASSWORD or a setting is wrong."""
    if password := user_env("PTZ_PASSWORD"):        # the newest setx, even in a terminal opened before it
        os.environ["PTZ_PASSWORD"] = password
    created = config.write_template_if_missing(path)
    s = config.load(path)
    if keyboard:
        s = replace(s, controller="keyboard")
    check_types(s, path)
    setup_logging(s)
    log.info("ptz_joystick %s", VERSION)
    if created:
        log.info("Wrote default settings to %s. Edit it and restart to change them.", path)
    log.info("Settings: %s (camera %s, controller %s)", path, s.camera, s.controller)
    return s
```

`ptz_joystick/app/status.py`: after the `GREEN, YELLOW, RED = ...` line add:

```python
CLICK_RESTART = "click Restart"     # the tray's restart step, after a problem that stopped the session
```

`ptz_joystick/app/session.py`:
- Delete `import os`, `from ..windows.user_env import user_env`, and the two `user_env` lines at the top of `_session` (moved to `prepare`).
- Add `from ..core.problem import Problem, crashed` and `from .status import CLICK_RESTART`.
- `run_session`'s `except` clauses become:

```python
    except Problem as p:                            # the startup checks' problems name the fix
        log.error(p.log_line(then=CLICK_RESTART))
        report.stopped(p.text(then=CLICK_RESTART))
    except Exception as e:
        p = crashed(e)
        log.critical(p.log_line(then=CLICK_RESTART), exc_info=True)
        report.stopped(p.text(then=CLICK_RESTART))
```

- In `_wait_for_controller`:

```python
        except Problem as p:                                # the Controller contract's "no device"
            report.no_controller(p.text())
```

`.github/workflows/ci.yml`: replace all three `"Set the camera password first"` with `"The camera password is not set"` (one in "Smoke test", two in "Smoke test (tray)").

- [ ] **Step 4: Run the tests, lint and types**

Run: `python -m unittest discover -s tests -t .` → OK.
Run: `ruff check .` and `mypy` → no errors.
Run: `git grep -n "SystemExit" -- ptz_joystick` → only `main.py`'s `raise SystemExit(1)` remains.

- [ ] **Step 5: Commit**

```bash
git add ptz_joystick/config/loading.py ptz_joystick/config/__init__.py ptz_joystick/config/template.py ptz_joystick/app/checks.py ptz_joystick/controllers/winmm.py ptz_joystick/controllers/__init__.py ptz_joystick/app/startup.py ptz_joystick/app/session.py ptz_joystick/app/status.py .github/workflows/ci.yml tests/config/test_loading.py tests/config/test_template.py tests/app/test_checks.py tests/controllers/test_winmm.py tests/app/test_startup.py tests/app/test_session.py
git commit -m "Raise Problem instead of SystemExit; both modes read the newest setx

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The tray shows problems; same words everywhere

**Files:**
- Modify: `ptz_joystick/app/session.py` (`Report` takes `Problem`s; `LastWarning` deleted)
- Modify: `ptz_joystick/app/status.py`
- Modify: `ptz_joystick/app/tray.py` (`_Report`)
- Modify: `ptz_joystick/app/loop.py` (`CONTROLLER_UNPLUGGED`)
- Modify: `ptz_joystick/app/main.py` (one log line), `ptz_joystick/controllers/winmm.py` (one log line)
- Test: `tests/app/test_status.py`, `tests/app/test_tray.py`, `tests/app/test_session.py`, `tests/app/test_loop.py`

**Interfaces:**
- Consumes: `Problem`, `crashed` (Task 1); `Camera.problem` (Task 2); `CLICK_RESTART` (Task 4); `config.bad_setting` (Task 4).
- Produces: `Report.waiting_for_camera(host: str, problem: Problem | None)`, `Report.no_controller(problem: Problem)`, `Report.camera(ok: bool, problem: Problem | None)`, `Report.stopped(problem: Problem)`; the same signatures on `Status` and `tray._Report`. `app.loop.CONTROLLER_UNPLUGGED: Problem`.

- [ ] **Step 1: Write the failing tests**

Replace `tests/app/test_status.py` with:

```python
import unittest
from pathlib import Path

from ptz_joystick.app.status import GREEN, RED, YELLOW, Popup, Status
from ptz_joystick.config import bad_setting
from ptz_joystick.core.problem import Problem, crashed

HOST = "http://192.168.77.3"
UNPLUGGED_TEXT = "The controller is unplugged and the camera stopped. Plug it back in."
UNPLUGGED = Popup(UNPLUGGED_TEXT, "warning")
LOGIN = Problem("The camera refused the login", fix="Check user in ptz_joystick.toml and PTZ_PASSWORD",
                detail="HTTP 401")
UNREACHABLE = Problem(f"Can't reach the camera at {HOST}", fix="Check host in ptz_joystick.toml and the network",
                      detail="timed out")


def driving():
    s = Status("ptz_joystick.log")
    s.driving(HOST)
    return s


class BeforeDrivingTest(unittest.TestCase):
    def test_starts_yellow_with_the_app_name_in_the_hover_text(self):
        s = Status("ptz_joystick.log")
        self.assertEqual((s.color, s.text), (YELLOW, "Starting…"))
        self.assertEqual(s.tooltip, "ptz_joystick: Starting…")

    def test_waiting_for_camera_says_why_without_the_detail(self):
        s = Status("ptz_joystick.log")
        s.waiting_for_camera(HOST, LOGIN)
        self.assertEqual((s.color, s.text),
                         (YELLOW, "The camera refused the login. Check user in ptz_joystick.toml and PTZ_PASSWORD."))

    def test_waiting_for_camera_before_it_says_why(self):
        s = Status("ptz_joystick.log")
        s.waiting_for_camera(HOST, None)
        self.assertEqual(s.text, f"Waiting for the camera at {HOST}")

    def test_stick_prompt_once_per_session_and_only_while_waiting(self):
        s = Status("ptz_joystick.log")
        self.assertIsNone(s.stick_prompt())                 # not waiting yet
        s.waiting_for_stick()
        self.assertEqual((s.color, s.text), (YELLOW, "Move the left stick to start"))
        self.assertEqual(s.stick_prompt(), Popup("Move the left stick to start", "info"))
        self.assertIsNone(s.stick_prompt())
        s.starting()                                        # Restart: a new session may prompt again
        s.waiting_for_stick()
        self.assertIsNotNone(s.stick_prompt())

    def test_a_late_stick_prompt_after_the_stick_moved_is_dropped(self):
        s = Status("ptz_joystick.log")
        s.waiting_for_stick()
        s.driving(HOST)
        self.assertIsNone(s.stick_prompt())

    def test_no_controller_shows_the_problem(self):
        s = Status("ptz_joystick.log")
        s.no_controller(Problem("No controller found", fix="Plug it in and check that it shows in joy.cpl"))
        self.assertEqual((s.color, s.text),
                         (YELLOW, "No controller found. Plug it in and check that it shows in joy.cpl."))

    def test_controller_and_camera_news_before_driving_is_ignored(self):
        s = Status("ptz_joystick.log")
        s.waiting_for_stick()
        self.assertIsNone(s.controller(False))
        s.camera(False, UNREACHABLE)
        self.assertEqual(s.text, "Move the left stick to start")


class DrivingTest(unittest.TestCase):
    def test_driving_is_green(self):
        s = driving()
        self.assertEqual((s.color, s.text), (GREEN, f"Driving the camera at {HOST}"))

    def test_unplugged_controller_pops_up_once_per_unplug(self):
        s = driving()
        self.assertEqual(s.controller(False), UNPLUGGED)
        self.assertEqual((s.color, s.text), (YELLOW, UNPLUGGED_TEXT))      # the status and the pop-up agree
        self.assertIsNone(s.controller(False))
        self.assertIsNone(s.controller(True))
        self.assertEqual(s.color, GREEN)
        self.assertEqual(s.controller(False), UNPLUGGED)    # unplugged again: pops up again

    def test_camera_drop_changes_the_icon_only(self):
        s = driving()
        s.camera(False, UNREACHABLE)
        self.assertEqual((s.color, s.text), (YELLOW, UNREACHABLE.text()))
        s.camera(True, None)
        self.assertEqual((s.color, s.text), (GREEN, f"Driving the camera at {HOST}"))

    def test_camera_drop_without_a_reason(self):
        s = driving()
        s.camera(False, None)
        self.assertEqual(s.text, "The camera is not answering")

    def test_unplugged_controller_wins_over_a_silent_camera(self):
        s = driving()
        s.camera(False, UNREACHABLE)
        s.controller(False)
        self.assertEqual(s.text, UNPLUGGED_TEXT)
        s.controller(True)
        self.assertEqual(s.text, UNREACHABLE.text())


class StoppedTest(unittest.TestCase):
    def test_red_adds_the_restart_step_and_pops_up_every_time(self):
        s = driving()
        text = "Unexpected error in ptz_joystick. See the log for details, then click Restart."
        self.assertEqual(s.stopped(crashed(RuntimeError("boom"))), Popup(text, "error"))
        self.assertEqual((s.color, s.text), (RED, text))
        self.assertEqual(s.stopped(Problem("A", fix="B")), Popup("A. B, then click Restart.", "error"))
        self.assertIsNone(s.controller(False))              # a stopped session drives nothing

    def test_a_long_message_stays_whole_for_the_pop_up(self):
        problem = bad_setting(Path("ptz_joystick.toml"),
                              "bad command 'presset 1', use one of: " + ", ".join(["preset <n>"] * 8))
        popup = driving().stopped(problem)
        self.assertGreater(len(popup.text), 128)            # longer than the hover text holds
        self.assertTrue(popup.text.endswith(", then click Restart."), popup.text)

    def test_update_pops_up_without_changing_the_icon(self):
        s = driving()
        self.assertEqual(s.update("v0.4.0"), Popup("Update available: v0.4.0", "info"))
        self.assertEqual(s.color, GREEN)

    def test_log_file_follows_the_settings(self):
        s = Status(r"C:\tools\ptz_joystick.log")
        s.log_to("")
        self.assertEqual(s.log_file, "")


if __name__ == "__main__":
    unittest.main()
```

`tests/app/test_tray.py`: add `from ptz_joystick.core.problem import Problem, crashed`; then:
- In `test_starts_yellow_then_green_once_the_session_drives`, the last assertion becomes `(GREEN, "ptz_joystick: Driving the camera at http://cam")`.
- `test_red_pops_up_as_an_error` becomes:

```python
    def test_red_pops_up_as_an_error(self):
        self.app.start_session()
        _, report, _ = self.session(1)
        report.stopped(Problem("The camera password is not set", fix='Run setx PTZ_PASSWORD "..." in a terminal'))
        self.window.pump()
        self.assertEqual(self.icon.shown[-1][0], RED)
        self.assertEqual(self.icon.popups, [('The camera password is not set. Run setx PTZ_PASSWORD "..." in a '
                                             'terminal, then click Restart.', tray.NIIF_ERROR)])
```

- In `test_a_stopped_sessions_late_news_is_dropped`: `old.stopped(crashed(RuntimeError("late")))`.

`tests/app/test_session.py`:
- Replace `FlakyCamera` with:

```python
class FlakyCamera(RecordingCamera):
    """Answers from a script (True = took it), then `then`. Says why it refused, like a real adapter."""
    WHY = Problem("Can't reach the camera", detail="timed out")

    def __init__(self, *answers, then=True):
        super().__init__()
        self.answers, self.then = list(answers), then

    def send(self, cmd):
        super().send(cmd)
        ok = self.answers.pop(0) if self.answers else self.then
        self.problem = None if ok else self.WHY
        return ok
```

- Delete `import logging` (no longer used). `RecordingReport`'s docstring: `"""A session's report, as tuples: ("driving", host), ("camera", ok, problem), ..."""`.
- In `test_drives_once_the_camera_answers`: `self.assertIn(("waiting_for_camera", HOST, FlakyCamera.WHY), self.report.calls)`.
- `test_missing_password_is_red_with_the_fix` becomes:

```python
    def test_missing_password_is_red_with_the_fix(self):
        del os.environ["PTZ_PASSWORD"]
        logs = self.run_session()
        [(name, problem)] = self.report.calls
        self.assertEqual((name, problem.what), ("stopped", "The camera password is not set"))
        self.assertTrue(any(line.startswith("ERROR") and "then click Restart" in line for line in logs.output))
```

- In `test_no_controller_waits_and_tries_again`: `self.assertIn(("no_controller", NO_PAD), self.report.calls)`.
- In `test_a_crash_while_driving_stops_the_camera_and_goes_red`, the first assertion becomes:

```python
        name, problem = self.report.calls[-1]
        self.assertEqual((name, problem.what, problem.detail),
                         ("stopped", "Unexpected error in ptz_joystick", "RuntimeError('boom')"))
```

- In `test_camera_drops_while_driving_come_with_the_reason`: `self.assertIn(("camera", False, FlakyCamera.WHY), self.report.calls)`.

`tests/app/test_loop.py`: add `from ptz_joystick.app.loop import CONTROLLER_UNPLUGGED` (with the `run` import: `from ptz_joystick.app.loop import CONTROLLER_UNPLUGGED, run`). In `test_unplug_mid_pan_stops_camera_and_warns`:

```python
        self.assertIn(CONTROLLER_UNPLUGGED.text(), logs.output[0])       # the same words as the tray's
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `python -m unittest tests.app.test_status tests.app.test_tray tests.app.test_session tests.app.test_loop -v`
Expected: ERROR `cannot import name 'CONTROLLER_UNPLUGGED'`, plus FAILs on the old status texts.

- [ ] **Step 3: Implement**

`ptz_joystick/app/loop.py`: add `from ..core.problem import Problem`; after `log = ...`:

```python
# The same words in the log, the tray's status text and its pop-up (app/status.py).
CONTROLLER_UNPLUGGED = Problem("The controller is unplugged and the camera stopped", fix="Plug it back in")
```

and in `run`:

```python
                if lost:
                    log.warning(CONTROLLER_UNPLUGGED.log_line())
                else:
                    log.info("The controller is back")
```

`ptz_joystick/app/status.py`, whole file:

```python
"""What the tray shows: the dot's color, the status text, and which events pop up a message. Plain rules with no
Windows calls; app/tray.py feeds them events and draws the result."""
from dataclasses import dataclass

from ..core.problem import Problem
from .loop import CONTROLLER_UNPLUGGED

GREEN, YELLOW, RED = (0x22, 0xA0, 0x45), (0xF0, 0xB0, 0x00), (0xD0, 0x30, 0x30)
CLICK_RESTART = "click Restart"     # the tray's restart step, after a problem that stopped the session


@dataclass(frozen=True)
class Popup:
    text: str
    kind: str           # "info", "warning" or "error": the pop-up's icon


class Status:
    """One per tray app, used on the window's thread. Event methods return the pop-up to show, if any."""

    def __init__(self, log_file: str):
        self.color, self.text = YELLOW, "Starting…"
        self.log_file = log_file                # what Open log opens; "" = there is no log file
        self._host: str | None = None           # set while driving
        self._waiting_for_stick = self._prompted = False
        self._controller_ok = self._camera_ok = True
        self._camera_problem: Problem | None = None

    @property
    def tooltip(self) -> str:
        return f"ptz_joystick: {self.text}"

    def starting(self) -> None:
        """A new session: its "move the stick" pop-up may show again."""
        self._phase(YELLOW, "Starting…")
        self._prompted = False

    def log_to(self, log_file: str) -> None:
        self.log_file = log_file

    def waiting_for_camera(self, host: str, problem: Problem | None) -> None:
        self._phase(YELLOW, problem.text() if problem else f"Waiting for the camera at {host}")

    def waiting_for_stick(self) -> None:
        self._phase(YELLOW, "Move the left stick to start")
        self._waiting_for_stick = True

    def stick_prompt(self) -> Popup | None:
        """The session has waited a second for a stick move: pop up, once per session."""
        if not self._waiting_for_stick or self._prompted:
            return None
        self._prompted = True
        return Popup("Move the left stick to start", "info")

    def no_controller(self, problem: Problem) -> None:
        self._phase(YELLOW, problem.text())

    def driving(self, host: str) -> None:
        self._phase(GREEN, f"Driving the camera at {host}")
        self._host = host
        self._controller_ok = self._camera_ok = True

    def controller(self, ok: bool) -> Popup | None:
        if self._host is None:                  # only while driving
            return None
        unplugged = self._controller_ok and not ok
        self._controller_ok = ok
        self._show_driving()
        return Popup(CONTROLLER_UNPLUGGED.text(), "warning") if unplugged else None

    def camera(self, ok: bool, problem: Problem | None) -> None:
        """Icon only: the camera drops every minute or two on this network, a pop-up each time would be noise."""
        if self._host is None:
            return
        self._camera_ok, self._camera_problem = ok, problem
        self._show_driving()

    def stopped(self, problem: Problem) -> Popup:
        text = problem.text(then=CLICK_RESTART)
        self._phase(RED, text)
        return Popup(text, "error")

    def update(self, tag: str) -> Popup:
        return Popup(f"Update available: {tag}", "info")

    def _phase(self, color: tuple[int, int, int], text: str):
        self.color, self.text = color, text
        self._host, self._waiting_for_stick = None, False

    def _show_driving(self):
        if not self._controller_ok:             # an unplugged controller explains more than a silent camera
            self.color, self.text = YELLOW, CONTROLLER_UNPLUGGED.text()
        elif not self._camera_ok:
            self.color = YELLOW
            self.text = self._camera_problem.text() if self._camera_problem else "The camera is not answering"
        else:
            self.color, self.text = GREEN, f"Driving the camera at {self._host}"
```

`ptz_joystick/app/tray.py`: add `from ..core.problem import Problem`; in `_Report` these four methods become:

```python
    def waiting_for_camera(self, host: str, problem: Problem | None) -> None:
        self._send(lambda s: s.waiting_for_camera(host, problem))

    def no_controller(self, problem: Problem) -> None:
        self._send(lambda s: s.no_controller(problem))

    def camera(self, ok: bool, problem: Problem | None) -> None:
        self._send(lambda s: s.camera(ok, problem))

    def stopped(self, problem: Problem) -> None:
        self._send(lambda s: s.stopped(problem))
```

`ptz_joystick/app/session.py`:
- Delete the `LastWarning` class.
- `Report`'s four methods become:

```python
    def waiting_for_camera(self, host: str, problem: Problem | None) -> None:
        """The camera didn't take the startup stop; problem = why (None if the camera didn't say)."""

    def no_controller(self, problem: Problem) -> None:
        """The factory found no device; problem says what to check. Trying again soon."""

    def camera(self, ok: bool, problem: Problem | None) -> None:
        """While driving: the camera stopped (False, problem = why) or started (True) taking commands."""

    def stopped(self, problem: Problem) -> None:
        """The session ended; problem names the fix. The tray adds its restart step."""
```

- `run_session` and `_session` become:

```python
def run_session(path: Path, keyboard: bool, stop: threading.Event, report: Report, check_updates: bool = False,
                retry_every: float = 5.0):
    """Startup steps, then drive the camera until stop is set. check_updates: ask GitHub (the first session)."""
    try:
        _session(path, keyboard, stop, report, check_updates, retry_every)
    except Problem as p:                            # the startup checks' problems name the fix
        log.error(p.log_line(then=CLICK_RESTART))
        report.stopped(p)
    except Exception as e:
        p = crashed(e)
        log.critical(p.log_line(then=CLICK_RESTART), exc_info=True)
        report.stopped(p)


def _session(path: Path, keyboard: bool, stop: threading.Event, report: Report, check_updates: bool,
             retry_every: float):
    s = prepare(path, keyboard)
    report.log_to(s.log_file)
    if check_updates and s.check_updates:
        updates.check_in_background(VERSION, on_found=report.update)
    camera = CAMERAS[s.camera].connect(s)
    while not camera.send(PanTilt(0, 0)):           # the startup check, retried: the camera may boot after the PC
        report.waiting_for_camera(s.host, camera.problem)
        if stop.wait(retry_every):
            return
    controller = _wait_for_controller(s, stop, report, retry_every)
    if controller is None:
        return
    check_axes(controller, s, path)
    sender = CommandSender(camera, on_camera=lambda ok: report.camera(ok, camera.problem))
    report.driving(s.host)
    log.info("Driving the camera at %s", s.host)
    run(s, controller, sender, stop=stop, on_controller=report.controller)
```

- In `_wait_for_controller`: `report.no_controller(p)`.

`ptz_joystick/app/main.py`, in `_console`: `log.info("Driving the camera at %s. Ctrl+C to quit.", s.host)`.

`ptz_joystick/controllers/winmm.py`, in `discover()`: `log.info("Move the left stick to start")` (was `"Move the left stick now..."`).

- [ ] **Step 4: Run the tests, lint and types**

Run: `python -m unittest discover -s tests -t .` → OK.
Run: `ruff check .` and `mypy` → no errors.
Run: `git grep -n "LastWarning\|camera_warning" -- ptz_joystick tests` → nothing.

- [ ] **Step 5: Commit**

```bash
git add ptz_joystick/app/session.py ptz_joystick/app/status.py ptz_joystick/app/tray.py ptz_joystick/app/loop.py ptz_joystick/app/main.py ptz_joystick/controllers/winmm.py tests/app/test_status.py tests/app/test_tray.py tests/app/test_session.py tests/app/test_loop.py
git commit -m "Tray: show Problems, with the same words as the log

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Log-only warnings as Problems, and the style check

**Files:**
- Modify: `ptz_joystick/core/sender.py`, `ptz_joystick/app/logs.py`, `ptz_joystick/windows/console.py`, `ptz_joystick/app/loop.py` (`stop_camera`)
- Create: `tests/test_messages.py`
- Test: `tests/core/test_sender.py`, `tests/app/test_logs.py`

**Interfaces:**
- Consumes: `Problem` (Task 1), `RUN_AGAIN` (Task 3).
- Produces: nothing new; every operator-readable WARNING/ERROR line is a `Problem.log_line()`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_messages.py`:

```python
"""Every Problem(...) in the package follows docs/extending.md, "Writing a message". It reads the source, so a new
message is checked the day it's written. Only plain-text parts are checked: an f-string's values aren't known."""
import ast
import unittest
from pathlib import Path

import ptz_joystick
from ptz_joystick.app.main import RUN_AGAIN
from ptz_joystick.core.problem import Problem

PACKAGE = Path(ptz_joystick.__file__).parent


def literal(node):
    """A plain string literal's text; None for anything else (an f-string, a name)."""
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def problems():
    """(where, what, fix) for every Problem(...) call. None = not plain text; fix "" = not given."""
    for path in sorted(PACKAGE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Problem":
                args = dict(zip(("what", "fix", "detail"), node.args))
                for k in node.keywords:
                    if k.arg:
                        args[k.arg] = k.value
                fix = literal(args["fix"]) if "fix" in args else ""
                yield f"{path.relative_to(PACKAGE)}:{node.lineno}", literal(args.get("what")), fix


class MessageStyleTest(unittest.TestCase):
    def test_the_scan_finds_the_problems(self):
        self.assertGreaterEqual(len(list(problems())), 15, "renamed Problem, or imported it under another name?")

    def test_every_problem_follows_the_rules(self):
        for where, what, fix in problems():
            with self.subTest(where):
                if what is not None:
                    self.assertTrue(what[:1].isupper(), f"rule 1, capital first letter: {what!r}")
                    self.assertFalse(what.endswith("."), f"rule 1, no period: {what!r}")
                if fix:
                    self.assertFalse(fix.endswith("."), f"rule 2, no period: {fix!r}")
                    self.assertNotRegex(fix.lower(), r"restart|run .*again", "rule 3: the console or tray adds it")
                if what is not None and fix is not None:
                    text = Problem(what, fix).text(then=RUN_AGAIN)
                    self.assertLessEqual(len(text), 120, f"rule 5: {text}")


if __name__ == "__main__":
    unittest.main()
```

`tests/core/test_sender.py`, `test_refused_preset_dropped_after_3_tries`: add as its last line:

```python
        self.assertIn("The camera didn't take a button command. Press the button again.", logs.output[-1])
```

`tests/app/test_logs.py`, `test_unwritable_log_file_falls_back_to_terminal`: the last line becomes:

```python
        self.assertIn("Can't write the log file. Close any program that has it open, or change log_file.",
                      logs.output[0])
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `python -m unittest tests.test_messages tests.core.test_sender tests.app.test_logs -v`
Expected: `test_the_scan_finds_the_problems` FAILs (13 found; this task adds 4), the sender and logs assertions FAIL. `test_every_problem_follows_the_rules` should already PASS. If it fails, fix the named message to follow the rules.

- [ ] **Step 3: Implement**

`ptz_joystick/core/sender.py`: add `from .problem import Problem` after `from .commands import MOVES, Command`; the give-up line becomes:

```python
                    log.warning(Problem("The camera didn't take a button command", fix="Press the button again",
                                        detail=f"gave up on {cmd} after {tries} tries").log_line())
```

`ptz_joystick/app/logs.py`: add `from ..core.problem import Problem`; the last two lines become:

```python
    if file_error:
        log.warning(Problem("Can't write the log file", fix="Close any program that has it open, or change log_file",
                            detail=f"{s.log_file}: {file_error}").log_line())
```

`ptz_joystick/windows/console.py`: add `from ..core.problem import Problem`; the `else:` branch of `on_console_close` becomes:

```python
    else:
        log.warning(Problem("Can't watch for the console window closing", fix="Quit with Ctrl+C so the camera stops",
                            detail=str(ctypes.WinError())).log_line())
```

`ptz_joystick/app/loop.py`, `stop_camera`'s `else:`:

```python
    else:
        log.error(Problem("The camera didn't confirm the stop", fix="Check that it stopped moving").log_line())
```

- [ ] **Step 4: Run the tests, lint and types**

Run: `python -m unittest discover -s tests -t .` → OK.
Run: `ruff check .` and `mypy` → no errors.

- [ ] **Step 5: Commit**

```bash
git add ptz_joystick/core/sender.py ptz_joystick/app/logs.py ptz_joystick/windows/console.py ptz_joystick/app/loop.py tests/test_messages.py tests/core/test_sender.py tests/app/test_logs.py
git commit -m "Log-only warnings as Problems; a test keeps every message in style

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Docs, and the manual check

**Files:**
- Modify: `docs/troubleshooting.md`, `docs/extending.md`, `README.md`, `docs/development.md`

**Interfaces:**
- Consumes: the final wording from Tasks 2–6. Copy message text from the code, not from memory.

- [ ] **Step 1: `docs/troubleshooting.md`**

Replace the log sample and the paragraph after it (up to `To see what happened...`) with:

````markdown
```
14:02:10 INFO    ptz_joystick v0.3.0
14:02:11 INFO    Using joystick ID 0
14:02:11 INFO    Driving the camera at http://192.168.77.3. Ctrl+C to quit.
14:05:40 WARNING The controller is unplugged and the camera stopped. Plug it back in.
14:05:43 INFO    The controller is back
14:07:02 WARNING Can't reach the camera at http://192.168.77.3. Check host in ptz_joystick.toml and the network. (...)
14:07:30 INFO    The camera is answering again (was: unreachable)
```

A WARNING or ERROR line is the sentence the tray shows, plus the technical cause in brackets. A camera outage logs one warning when it starts and one line when the camera is back, not one line per retry.
While the camera is down, stick moves keep retrying. A button action (like a preset recall) the camera refuses 3 times is dropped, so it can't fire minutes later.
````

Then replace the whole Troubleshooting table (from `| Symptom | Fix |` to its last row) with:

```markdown
| Symptom | Fix |
|---|---|
| No tray dot | Windows 11 hides it behind **^** on the taskbar. Settings → Personalization → Taskbar → Other system tray icons → turn on ptz_joystick_tray |
| Tray dot red | Hover over it, or **Open log**: the message names the fix (see the rows below). Fix it, then **Restart** |
| Tray dot yellow, `Waiting for the camera at ...` | The camera hasn't answered yet. Once it says why, the hover text shows that instead: see `The camera refused the login` and `Can't reach the camera` below. It tries again every 5 s |
| `Move the left stick to start` (tray dot yellow, or the console stuck there) | Move the stick fully. The tool picks the first controller whose stick moves more than 0.3 |
| Console window shows `Press Enter to close.` | The console exe stopped on one of the messages below; it waits so you can read it. Fix it, press Enter, run it again |
| `Another ptz_joystick is already running` | Another copy runs: a tray dot (look behind **^**) or a console window. Quit it first |
| Keyboard controller: keys do nothing | Keys only count while Zao Virtual Cabin is in front. Click its window first |
| `The camera password is not set` | Run `setx PTZ_PASSWORD "..."` in a terminal, then run ptz_joystick again (console, any terminal) or click **Restart** (tray) |
| `No controller found` | Open `joy.cpl` (Win+R). If the controller isn't listed or its crosshair doesn't move there, it's a cable, receiver or driver problem, not this tool |
| `Bad setting in ptz_joystick.toml: the controller has no axis ...` | Set `debug = true`, run, move each stick, and see which letter changes. Put those letters in `pan_axis` / `tilt_axis` / `zoom_axis` |
| Camera never reaches full speed | Set `debug = true` and push the stick to its edge. Set `full_speed_at` a little below the highest value you see |
| Full speed comes too early in the push | Raise `full_speed_at` (max `1.0`) |
| Up/down is backwards | Toggle `invert_tilt` or `invert_zoom` |
| `The camera at ... didn't answer` | The startup check failed and the camera gave no reason. Check `host`, the network, and `PTZ_PASSWORD` |
| `The camera refused the login` | Wrong `user` or `PTZ_PASSWORD` |
| `Can't reach the camera at ...` | Check `host`, the network, and that the camera's web page opens in a browser |
| `The camera refused a command` | The camera answered with an HTTP error; the log line has the code. Check that its web page opens in a browser |
| `The camera didn't take a button command` | The camera was down when the button was pressed, so the action was dropped after 3 tries. Press it again |
| `Bad setting in ptz_joystick.toml: ...` | A setting is misspelled or has an invalid value. The message names it and the allowed range |
| Changed a setting, nothing happened | Check the `Settings:` line at startup: it shows which file was read. Restart after saving (tray: right-click → Restart) |
| `Can't write the log file` | Another program has the log open, or the folder is read-only. The tool keeps running and logs to the terminal only (the tray version then has no log) |
| `Wrong text encoding in ptz_joystick.toml` | The file was saved in an old encoding (for example ANSI with Hebrew text). In Notepad: File → Save as → Encoding: UTF-8 |
| `Unexpected error in ptz_joystick` | Something failed that the tool doesn't expect. The log has the details (a traceback). Restart; if it comes back, send the log to whoever maintains the tool |
```

If the current table has a row this one lacks (added after this plan was written), keep that row.

- [ ] **Step 2: `docs/extending.md`**

- "Adding a camera", step 2, first bullet becomes: ``- a class that has `send(cmd) -> bool` and a `problem` attribute: why the last send failed, as a `Problem` (`core/problem.py`), `None` after a success. Word it as in [Writing a message](#writing-a-message)``
- Step 4's last paragraph sentence becomes: ``The contract checks that stops always work, every command is sent or refused with `TypeError`, a camera that's down returns `False`, logs once and says why in `problem`, and `TOP_SPEEDS` is complete.``
- "Adding a controller", step 2 becomes: ``2. Add `controllers/<name>.py` with a class that has `read()`, and a function that takes `Settings` and returns a ready controller (like `keyboard.start`). With no device, the function raises a `Problem` (`core/problem.py`) saying what to check, like `winmm.discover()`. The tray retries it every 5 s.``
- Add this section before "## New button action (home, focus, …)":

```markdown
## Writing a message

Anything the operator should read is a `Problem` (`core/problem.py`): `Problem(what, fix, detail)`. Raise it to stop, or log `problem.log_line()` for a warning. The console and the tray add their own restart step ("run ptz_joystick again", "click Restart").

1. `what` says what is wrong, not what the code did. One short sentence, capital first letter, no period.
2. `fix` is an order the operator can follow. It names the setting, file or command. No period.
3. Never put "restart" or "run again" in `fix`: the console or the tray adds its own step.
4. HTTP codes, exception text and full paths go in `detail`. Only the log shows it.
5. Keep `text()` within 120 characters.

`tests/test_messages.py` checks rules 1, 2, 3 and 5 for every `Problem(...)` with plain text in it.
```

- [ ] **Step 3: `README.md` and `docs/development.md`**

`README.md`, Setup: the line ``` `setx` only applies to new terminals, so open a new one after running it.``` becomes:

```markdown
ptz_joystick reads the new value even in a terminal that was open before `setx`.
```

`docs/development.md`, the layout block:
- After the `sender.py` line add: `    problem.py         Problem: what the operator must fix, in their words; console and tray add the restart step`
- The `test_entry_point.py` line becomes: `  test_entry_point.py  __main__.py: Ctrl+C stays quiet`
- After it add: `  test_messages.py     every Problem(...) follows docs/extending.md "Writing a message"`
- The `Camera.send` bullet below the block becomes: ``- `Camera.send(cmd: Command) -> bool` in `cameras/__init__.py` (True = camera took it), and `Camera.problem`: why it didn't``

- [ ] **Step 4: Check the docs against the code**

Run: `git grep -n -E "password first|new terminal|camera unreachable|rejected the login|Controller lost|left stick now|Crashed:|did not accept a stop" -- README.md docs/*.md ptz_joystick tests .github`
Expected: no hits outside `docs/superpowers/` (old specs and plans keep their history).
Run: `python -m unittest discover -s tests -t .`, `ruff check .`, `mypy` → all clean.

- [ ] **Step 5: Commit**

```bash
git add docs/troubleshooting.md docs/extending.md README.md docs/development.md
git commit -m "Docs: the new messages, and how to write one

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Manual check (the human, about 5 minutes, after CI builds the exes)**

1. Double-click `ptz_joystick.exe` with no `PTZ_PASSWORD` → the message, then `Press Enter to close.`, and the line is in `ptz_joystick.log`. Do this on Windows 11 with Windows Terminal as the default terminal too, if that's what operators have.
2. Run it from a terminal → the same message, and the prompt returns at once.
3. `setx PTZ_PASSWORD` a wrong value, run the console exe again from the same terminal → `The camera refused the login. …`.
4. Tray: break a setting, Restart → red, pop-up ends `then click Restart.`
5. Tray: unplug the pad while driving → yellow; the pop-up, the hover text and the log line read the same.
