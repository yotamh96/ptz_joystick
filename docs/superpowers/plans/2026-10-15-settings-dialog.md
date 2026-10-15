# Settings Dialog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tray menu → **Settings…** opens a window where the operator changes every setting and the camera password, with the same checks as startup, then optionally restarts.

**Architecture:** A tkinter dialog on its own thread (`windows/settings_dialog/`): `form.py` (pure: Settings ↔ field text, which field an error is about), `tabs.py` (widgets), `window.py` (Save / Cancel / Notepad), `__init__.py` (thread + handle). `config/` learns to write the file back (`render`, `save`) and to read it without the password (`read`). The tray swaps "Open settings" for "Settings…" and closes the dialog on Quit.

**Tech Stack:** Python 3.11+ stdlib only (`tkinter`/`ttk`, `ctypes`, `winreg`, `unittest`), ruff 0.16.10, mypy 2.4.0. Windows. PyInstaller in CI.

**Spec:** `docs/superpowers/specs/2026-10-15-settings-dialog-design.md`

## Plan decisions (where the plan is more exact than the spec)

- **Marking a bad field:** the field's label and the message under it turn red. The spec says "red border", but the ttk "vista" theme draws entry borders itself and ignores border colours.
- **"Open in Notepad"** is a button at the left of Save / Cancel, not a link.
- **Close signal from the tray:** a `threading.Event` the window checks every 100 ms (the spec says a `SimpleQueue`; one signal needs no queue).
- **Writing the file:** `config.save(path, s)` in `config/template.py` (temp file, then `os.replace`).
- **`form.to_fields(s)`** reads the password from `s.password`. The dialog passes Settings with the password filled in.

## Global Constraints

- Python 3.11+ (CI tests 3.11 and 3.14). No new packages.
- Tests: `unittest`, mirroring the package (`tests/<folder>/test_<module>.py`). Run all: `python -m unittest discover -s tests -t .`
- Every task ends green on all three: the unit tests, `ruff check .`, `mypy` (settings in `mypy.ini`; it checks `tests/` too).
- Match the surrounding code: lines up to about 120 characters, short comments that say why.
- `windows/` never imports `app/`. The tray (`app/tray.py`) passes camera types, controller types and `type_error` in.
- Every Tk call happens on the dialog's own thread. Other threads only touch the `Handle` (an Event, an HWND).
- Exact operator words: menu item `Settings…`; window title `ptz_joystick settings`; after Save `Settings saved. Restart now to use them?`; broken file `<Problem text>` + blank line + `Open it in Notepad?`; empty password `The camera password is not set`.
- `TEMPLATE`'s setting lines stay exactly as today (the installer edits the `host` and `controller` lines). Only its header comment changes.
- Message rules (`docs/extending.md`, "Writing a message"): `what` capital first letter, no period; `fix` an order, no period, never "restart"; technical text in `detail`; `text()` ≤ 120 characters. `tests/test_messages.py` checks every `Problem(...)` in the package.
- English only.
- Commits: stage only the files the task lists (never `.superpowers/`). Message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Tk objects freed on the wrong thread.** If the tray's thread garbage-collects a Tk variable or the interpreter, Tcl aborts the whole process (`Tcl_AsyncDelete`), which pops a crash box at Quit. The dialog thread must free everything itself. → Task 5, `test_opens_on_its_own_thread_and_closes_when_the_tray_asks` (closes, then `gc.collect()` on the main thread).
2. **An operator types `0,15` or ` 24 `.** The comma must give `deadzone must be a number, got '0,15'` on the Deadzone field, not a crash; spaces around a number are fine. → Task 3, `test_a_comma_decimal_is_named_in_the_usual_words`, `test_spaces_around_a_number_are_fine`.
3. **A folder the operator can't write** (a per-machine install without rights). The old file must stay whole, and the dialog must say why and stay open. → Task 1, `test_a_failed_save_leaves_the_old_file_whole`; Task 4, `test_a_failed_write_says_why_and_stays_open`.
4. **A password with `"`, `%`, spaces or Hebrew** must reach HKCU exactly as typed, not expanded. → Task 2, `test_set_then_read_back_as_typed`.
5. **A file that maps button 32 (index 31), or no buttons at all.** Rows must appear for it and come back unchanged on Save. → Task 1, `test_unusual_values_come_back_the_same`; Task 3, `test_twelve_button_rows_or_up_to_the_highest`.

---

### Task 1: Write the settings file back (`config`)

**Files:**
- Modify: `ptz_joystick/config/settings.py` (add `takes_number` after `BUTTON_COMMANDS`)
- Modify: `ptz_joystick/config/loading.py` (add `command_text`, `read`; `load` uses `read`)
- Modify: `ptz_joystick/config/template.py` (whole file below)
- Modify: `ptz_joystick/config/__init__.py`
- Test: `tests/config/test_template.py`, `tests/config/test_loading.py`

**Interfaces:**
- Produces: `config.takes_number(action: str) -> bool`; `config.command_text(cmd: Command) -> str`; `config.read(path: Path) -> Settings` (password `""`, `log_file` as written, raises `Problem` like `load`); `config.render(s: Settings) -> str`; `config.save(path: Path, s: Settings) -> None` (raises `Problem("Can't save <name>", fix="Check that you can write to its folder", detail=...)`); `config.TEMPLATE == config.render(Settings())`.

- [ ] **Step 1: Save today's template text, to compare after the change**

```powershell
python -c "import os; from ptz_joystick.config import TEMPLATE; open(os.path.join(os.environ['TEMP'], 'old_template.txt'), 'w', encoding='utf-8').write(TEMPLATE)"
```

- [ ] **Step 2: Write the failing tests**

In `tests/config/test_template.py`, add to the imports:

```python
from dataclasses import fields, replace

from ptz_joystick.config import template
from ptz_joystick.core.commands import Preset, Tracking
```

(`fields` is already imported; merge into one `from dataclasses import fields, replace` line.) Add these classes above `class DefaultPathTest`:

```python
class RenderTest(unittest.TestCase):
    def test_unusual_values_come_back_the_same(self):
        s = Settings(host='http://cam/"x"\\y', user="מפעיל\x7f", log_file="D:\\logs\\ptz.log", controller="keyboard",
                     invert_tilt=False, deadzone=0.05, timeout=2.0, pan_max=1,
                     buttons={0: Preset(7), 5: Tracking(True), 31: Preset(0)})
        for case in (s, replace(s, buttons={}, log_file="")):
            with self.subTest(case=case):
                self.assertEqual(config.from_dict(tomllib.loads(config.render(case)), ""), case)

    def test_never_writes_the_password(self):
        self.assertNotIn("secret", config.render(Settings(password="secret")))

    def test_the_installer_finds_its_two_lines(self):
        lines = config.TEMPLATE.splitlines()
        self.assertIn('host = "http://192.168.77.3"    # camera address', lines)
        self.assertIn('controller = "winmm"            # winmm (any controller joy.cpl shows) or keyboard', lines)

    def test_a_long_value_keeps_its_comment(self):
        text = config.render(Settings(host="http://" + "a" * 40))
        line = next(x for x in text.splitlines() if x.startswith("host = "))
        self.assertTrue(line.endswith('" # camera address'), line)


class SaveTest(unittest.TestCase):
    def test_a_saved_file_reads_back(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / config.FILE_NAME
            config.save(path, Settings(host="http://10.0.0.9"))
            self.assertEqual(config.read(path), Settings(host="http://10.0.0.9"))
            self.assertEqual([p.name for p in Path(d).iterdir()], [config.FILE_NAME])     # no .tmp left over

    def test_a_failed_save_leaves_the_old_file_whole(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / config.FILE_NAME
            path.write_text('host = "http://old"\n', encoding="utf-8")
            with mock.patch.object(template.os, "replace", side_effect=PermissionError("denied")), \
                    self.assertRaises(Problem) as cm:
                config.save(path, Settings())
            self.assertEqual(path.read_text(encoding="utf-8"), 'host = "http://old"\n')
        self.assertEqual(cm.exception.text(),
                         f"Can't save {config.FILE_NAME}. Check that you can write to its folder.")
        self.assertIn("denied", cm.exception.detail)
```

In `tests/config/test_loading.py`, add above `class EncodingTest`:

```python
class CommandTextTest(unittest.TestCase):
    def test_reverse_of_parse_command(self):
        for text in ("preset 0", "preset 12", "tracking"):
            with self.subTest(text):
                self.assertEqual(config.command_text(config.parse_command(text)), text)

    def test_which_actions_take_a_number(self):
        self.assertEqual({a: config.takes_number(a) for a in config.BUTTON_COMMANDS},
                         {"preset": True, "tracking": False})


class ReadTest(unittest.TestCase):
    def test_keeps_the_file_as_written_and_needs_no_password(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"PTZ_PASSWORD": ""}):
            path = Path(d) / config.FILE_NAME
            path.write_text("log_file = 'logs\\ptz.log'", encoding="utf-8")
            s = config.read(path)
        self.assertEqual((s.log_file, s.password), ("logs\\ptz.log", ""))

    def test_a_bad_file_is_a_bad_setting(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(Problem) as cm:
            path = Path(d) / config.FILE_NAME
            path.write_text('hots = "x"', encoding="utf-8")
            config.read(path)
        self.assertEqual(cm.exception.what, f"Bad setting in {config.FILE_NAME}: unknown setting 'hots'")
```

- [ ] **Step 3: Run them to see them fail**

Run: `python -m unittest tests.config.test_template tests.config.test_loading -v`
Expected: errors, `AttributeError: module 'ptz_joystick.config' has no attribute 'render'` (and `read`, `save`, `command_text`, `takes_number`).

- [ ] **Step 4: `takes_number` in `ptz_joystick/config/settings.py`**

Add `import inspect` as the first import line. Directly after the `BUTTON_COMMANDS` dict, add:

```python


def takes_number(action: str) -> bool:
    """Whether a BUTTON_COMMANDS action is written with a number ("preset 3") or alone ("tracking")."""
    return bool(inspect.signature(BUTTON_COMMANDS[action][0]).parameters)
```

- [ ] **Step 5: `command_text` and `read` in `ptz_joystick/config/loading.py`**

Change the settings import to `from .settings import BUTTON_COMMANDS, Settings, takes_number`. After `parse_command`, add:

```python
def command_text(cmd: Command) -> str:
    """Preset(3) -> "preset 3": the reverse of parse_command, for writing the settings file."""
    for name, (make, _) in BUTTON_COMMANDS.items():
        args = [getattr(cmd, f.name) for f in fields(cmd)] if takes_number(name) else []
        if make(*args) == cmd:
            return " ".join([name, *map(str, args)])
    raise ValueError(f"no button action makes {cmd!r}")
```

Replace `load()` with `read()` plus a shorter `load()`:

```python
def read(path: Path) -> Settings:
    """The settings in path as written: password "", log_file as typed. Raises Problem like load()."""
    try:
        return from_dict(tomllib.loads(read_text(path)), "")
    except (tomllib.TOMLDecodeError, ValueError) as e:
        raise bad_setting(path, e) from None
    except OSError as e:
        raise Problem(f"Can't read {path.name}", fix="Check that you can open it in Notepad", detail=str(e)) from None


def load(path: Path) -> Settings:
    password = os.environ.get("PTZ_PASSWORD")
    if not password:
        raise Problem("The camera password is not set", fix='Run setx PTZ_PASSWORD "..." in a terminal')
    s = replace(read(path), password=password)
    # A relative log file sits next to the settings file (and so the exe), whatever folder you run from.
    return replace(s, log_file=str(path.parent / s.log_file)) if s.log_file else s
```

- [ ] **Step 6: Replace `ptz_joystick/config/template.py` with**

```python
"""The settings file: its name, where it lives, the commented template a first run writes, and writing it back."""
import json
import os
import re
import sys
from pathlib import Path

from ..core.problem import Problem
from .loading import command_text
from .settings import Settings

FILE_NAME = "ptz_joystick.toml"

HEADER = """\
# ptz_joystick settings. Easiest: tray menu → Settings…, which rewrites this file (comments you add are lost).
# Or edit here, save, then restart ptz_joystick (tray: right-click → Restart).
# The camera password is not here: set it with  setx PTZ_PASSWORD "..."

"""
# Every setting but the buttons, in file order. render() puts in the values and keeps each comment where it is.
LAYOUT = """\
camera = "ptzoptics"            # camera type: ptzoptics
host = "http://192.168.77.3"    # camera address
user = "admin"                  # camera user
timeout = 1.0                   # seconds to wait for each camera request (max 2)

controller = "winmm"            # winmm (any controller joy.cpl shows) or keyboard
pan_axis = "X"                  # which controller axis does what: X Y Z R U V
tilt_axis = "Y"                 #   (debug = true shows which letter moves)
zoom_axis = "R"
invert_tilt = true              # flip if up/down feels backwards
invert_zoom = true
deadzone = 0.15                 # stick readings at or below this are ignored
full_speed_at = 0.7             # stick reading that gives top speed (max 1.0)

pan_max = 24                    # camera's top speeds (PTZOptics max 24 / 20 / 7)
tilt_max = 20
zoom_max = 7

save_hold_seconds = 2.0         # tap a preset button = go there; hold it this long = save the current
                                #   view there; 0 = saving off (and presets fire on press)
debug = false                   # true logs every stick reading and every command sent
log_file = "ptz_joystick.log"   # next to this file unless a full path; "" = terminal only
check_updates = true            # at startup, log a line if a newer release is on GitHub
"""
BUTTONS = '[buttons]                       # button index (0 = "button 1" in joy.cpl) = command\n'
SETTING_LINE = re.compile(r'^(\w+) = ("[^"]*"|\S+) *(#.*)?$', re.M)       # name = value   # comment
COMMENT_COLUMN = 32


def toml_value(v: object) -> str:
    """v as TOML writes it. json.dumps escapes backslash, quote and control characters as TOML does, except DEL."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False).replace("\x7f", "\\u007f")
    return repr(v)


def render(s: Settings) -> str:
    """The settings file for s: the template's lines and comments with s's values. Never the password."""
    def line(m: re.Match[str]) -> str:
        text = f"{m[1]} = {toml_value(getattr(s, m[1]))}"
        return f"{text:<{COMMENT_COLUMN - 1}} {m[3]}" if m[3] else text

    rows = "".join(f"{b} = {toml_value(command_text(c))}\n" for b, c in sorted(s.buttons.items()))
    return HEADER + SETTING_LINE.sub(line, LAYOUT) + "\n" + BUTTONS + rows


TEMPLATE = render(Settings())


def default_path() -> Path:
    """Next to the exe when frozen by PyInstaller, else in the repo folder (next to README.md)."""
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    return base / FILE_NAME


def write_template_if_missing(path: Path) -> bool:
    if path.exists():
        return False
    try:
        path.write_text(TEMPLATE, encoding="utf-8")
    except OSError as e:
        raise Problem(f"Can't create {path.name}", fix="Move the exe to a folder you can write to",
                      detail=str(e)) from None
    return True


def save(path: Path, s: Settings):
    """Write s to path as render() lays it out. Through a temp file, so a failed write never leaves half a file."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(render(s), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as e:
        raise Problem(f"Can't save {path.name}", fix="Check that you can write to its folder",
                      detail=str(e)) from None
```

- [ ] **Step 7: Export from `ptz_joystick/config/__init__.py`**

```python
"""Every setting in one place: settings.py (defaults, validation), template.py (the file, where it lives, writing
it), loading.py (reading it). Import from here: config.load, config.Settings, ..."""
from .loading import bad_setting, command_text, from_dict, load, parse_command, read
from .settings import AXES, BUTTON_COMMANDS, MAX_TIMEOUT, Settings, takes_number
from .template import FILE_NAME, TEMPLATE, default_path, render, save, write_template_if_missing

__all__ = ["AXES", "BUTTON_COMMANDS", "FILE_NAME", "MAX_TIMEOUT", "TEMPLATE", "Settings", "bad_setting",
           "command_text", "default_path", "from_dict", "load", "parse_command", "read", "render", "save",
           "takes_number", "write_template_if_missing"]
```

- [ ] **Step 8: Run the tests, and check the setting lines didn't move**

Run: `python -m unittest tests.config.test_template tests.config.test_loading -v`
Expected: all PASS.

Run:
```powershell
python -c "import os; from ptz_joystick.config import TEMPLATE; old = open(os.path.join(os.environ['TEMP'], 'old_template.txt'), encoding='utf-8').read().splitlines(); assert old[2:] == TEMPLATE.splitlines()[3:], 'setting lines changed'; print('setting lines unchanged')"
```
Expected: `setting lines unchanged`. (Old: 2 header lines; new: 3.)

- [ ] **Step 9: Full suite, lint, types**

Run: `python -m unittest discover -s tests -t .` then `ruff check .` then `mypy`
Expected: all green.

- [ ] **Step 10: Commit**

```powershell
git add ptz_joystick/config/settings.py ptz_joystick/config/loading.py ptz_joystick/config/template.py ptz_joystick/config/__init__.py tests/config/test_template.py tests/config/test_loading.py
git commit -m "Config: write the settings file back (render, save), read it without the password" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Helpers the dialog needs (`type_error`, `set_user_env`, `ask`)

**Files:**
- Modify: `ptz_joystick/app/checks.py` (`check_types`)
- Modify: `ptz_joystick/windows/user_env.py`
- Modify: `ptz_joystick/windows/message_box.py`
- Test: `tests/app/test_checks.py`, `tests/windows/test_user_env.py`

**Interfaces:**
- Produces: `app.checks.type_error(s: Settings) -> str | None` (same messages as `check_types`, no file name); `windows.user_env.set_user_env(name: str, value: str, key: str = KEY) -> None` (raises `OSError`); `windows.message_box.ask(text: str, title: str = "ptz_joystick") -> bool`.

- [ ] **Step 1: Write the failing tests**

In `tests/app/test_checks.py`, change the import to `from ptz_joystick.app.checks import check_axes, check_camera, check_types, type_error` and add above `class CheckAxesTest`:

```python
class TypeErrorTest(unittest.TestCase):
    def test_says_what_is_wrong_without_a_file_name(self):
        self.assertIsNone(type_error(Settings()))
        self.assertEqual(type_error(Settings(camera="sony")), "camera must be one of ptzoptics, got 'sony'")
        self.assertEqual(type_error(Settings(tilt_max=21)), "tilt_max can be at most 20 for camera 'ptzoptics', got 21")
```

In `tests/windows/test_user_env.py`, change the imports to:

```python
import os
import unittest
import winreg
from unittest import mock

import ptz_joystick.windows.user_env as env_module
from ptz_joystick.windows.user_env import set_user_env, user_env
from tests.windows.scratch_key import scratch_key
```

and add to `UserEnvTest`:

```python
    def test_set_then_read_back_as_typed(self):
        password = 'p%a"ss wörd מ'                     # % is not expanded, quotes and Hebrew survive
        with mock.patch.object(env_module.user32, "SendMessageTimeoutW") as broadcast:
            set_user_env("PTZ_PASSWORD", password, self.key)
        self.assertEqual(user_env("PTZ_PASSWORD", self.key), password)
        broadcast.assert_called_once()                  # Explorer hears of it, as after setx
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m unittest tests.app.test_checks tests.windows.test_user_env -v`
Expected: `ImportError: cannot import name 'type_error'` and `cannot import name 'set_user_env'`.

- [ ] **Step 3: `type_error` in `ptz_joystick/app/checks.py`**

Replace `check_types` with:

```python
def type_error(s: Settings) -> str | None:
    """What's wrong with camera, controller or the speeds for that camera, or None. No file name: the settings
    dialog shows it under the field; check_types adds the file."""
    for name, table in (("camera", CAMERAS), ("controller", CONTROLLERS)):
        if getattr(s, name) not in table:
            return f"{name} must be one of {', '.join(table)}, got {getattr(s, name)!r}"
    for name, top in CAMERAS[s.camera].top_speeds.items():
        if getattr(s, name) > top:
            return f"{name} can be at most {top} for camera {s.camera!r}, got {getattr(s, name)}"
    return None


def check_types(s: Settings, settings_path: Path):
    """camera and controller name known types, and the speeds fit that camera. Before anything connects."""
    if message := type_error(s):
        raise bad_setting(settings_path, message)
```

- [ ] **Step 4: `set_user_env` in `ptz_joystick/windows/user_env.py`**

Replace the module docstring, imports and constants with:

```python
"""A user environment variable as setx left it, for a program that started before setx ran, and setting one as setx
does. Windows only.

A running program keeps the environment it started with. setx writes HKCU\\Environment, so reading there finds a
password set after the tray app started."""
import ctypes
import winreg
from ctypes import wintypes

KEY = "Environment"
HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x001A, 0x0002
BROADCAST_MS = 1000             # a program that doesn't answer within this is skipped

user32 = ctypes.WinDLL("user32", use_last_error=True)       # own copy: we set prototypes below
user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPCWSTR,
                                       wintypes.UINT, wintypes.UINT, ctypes.c_void_p]
```

and add after `user_env()`:

```python
def set_user_env(name: str, value: str, key: str = KEY):
    """Save the variable in HKCU\\<key> as plain text (REG_SZ: % is not expanded), as setx does, and tell Explorer,
    so programs started from now on get it. Raises OSError if the registry refuses."""
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
    user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, KEY, SMTO_ABORTIFHUNG, BROADCAST_MS, None)
```

- [ ] **Step 5: `ask` in `ptz_joystick/windows/message_box.py`**

Replace the file with:

```python
"""A plain message box, and a Yes/No question, for when there is no console and no window to own one. Windows only."""
import ctypes
from ctypes import wintypes

MB_YESNO, MB_ICONQUESTION, MB_ICONWARNING, IDYES = 0x04, 0x20, 0x30, 6

user32 = ctypes.WinDLL("user32")            # own copy: we set prototypes below
user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]


def message_box(text: str, title: str = "ptz_joystick"):
    """Show text and wait for OK."""
    user32.MessageBoxW(None, text, title, MB_ICONWARNING)


def ask(text: str, title: str = "ptz_joystick") -> bool:
    """Show text with Yes and No, and wait. -> True for Yes."""
    return user32.MessageBoxW(None, text, title, MB_YESNO | MB_ICONQUESTION) == IDYES
```

- [ ] **Step 6: Run the tests**

Run: `python -m unittest tests.app.test_checks tests.windows.test_user_env -v`
Expected: all PASS (the existing `check_types` tests too: same messages).

- [ ] **Step 7: Full suite, lint, types**

Run: `python -m unittest discover -s tests -t .` then `ruff check .` then `mypy`
Expected: all green.

- [ ] **Step 8: Commit**

```powershell
git add ptz_joystick/app/checks.py ptz_joystick/windows/user_env.py ptz_joystick/windows/message_box.py tests/app/test_checks.py tests/windows/test_user_env.py
git commit -m "type_error, set_user_env and a Yes/No box, for the settings dialog" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The dialog's fields, without Tk (`form.py`)

**Files:**
- Create: `ptz_joystick/windows/settings_dialog/__init__.py` (docstring only for now; Task 5 fills it)
- Create: `ptz_joystick/windows/settings_dialog/form.py`
- Create: `tests/windows/settings_dialog/__init__.py` (empty)
- Test: `tests/windows/settings_dialog/test_form.py`

**Interfaces:**
- Consumes: `config.command_text`, `config.parse_command`, `config.from_dict`, `config.takes_number`, `config.BUTTON_COMMANDS`, `config.MAX_TIMEOUT` (Task 1).
- Produces: `form.TABS: tuple[str, ...]` = `("Camera", "Controller", "Buttons", "Other")`; `form.Field(setting, tab, label, hint="")`; `form.FIELDS: list[Field]`; `form.NOTHING = "nothing"`; `form.ACTIONS: list[str]`; `form.FieldError(setting: str, message: str, row: int | None = None)` with attributes `setting`, `message`, `row`; `form.numbered(action: str) -> bool`; `form.to_fields(s: Settings) -> dict[str, Any]` (text for entries and dropdowns, `bool` for checkboxes, `"password"` from `s.password`, `"buttons"` a `list[tuple[str, str]]` of `(action, number text)`); `form.from_fields(values: dict[str, Any], type_error: Callable[[Settings], str | None]) -> Settings` (password included; raises `FieldError`).

- [ ] **Step 1: Create the package files**

`ptz_joystick/windows/settings_dialog/__init__.py`:

```python
"""The settings dialog (tray menu → Settings…): every setting and the camera password in one window."""
```

`tests/windows/settings_dialog/__init__.py`: an empty file.

- [ ] **Step 2: Write the failing tests**

`tests/windows/settings_dialog/test_form.py`:

```python
import unittest
from dataclasses import fields, replace

from ptz_joystick.app.checks import type_error
from ptz_joystick.config import Settings
from ptz_joystick.core.commands import Preset, Tracking
from ptz_joystick.windows.settings_dialog import form

PW = replace(Settings(), password="pw")


def save(**changes):
    """from_fields on the default fields, with some changed as the operator would type them."""
    return form.from_fields({**form.to_fields(PW), **changes}, type_error)


class FieldsTest(unittest.TestCase):
    def test_every_setting_has_a_field_on_a_tab(self):
        self.assertEqual({f.setting for f in form.FIELDS}, {f.name for f in fields(Settings)})
        self.assertLessEqual({f.tab for f in form.FIELDS}, set(form.TABS))

    def test_fields_give_the_same_settings_back(self):
        s = replace(Settings(), host="http://10.0.0.9", password='p"w', controller="keyboard", invert_zoom=False,
                    deadzone=0.1, timeout=2.0, log_file="", buttons={0: Preset(1), 5: Tracking(True), 20: Preset(30)})
        self.assertEqual(form.from_fields(form.to_fields(s), type_error), s)

    def test_twelve_button_rows_or_up_to_the_highest(self):
        self.assertEqual(len(form.to_fields(PW)["buttons"]), 12)
        rows = form.to_fields(replace(PW, buttons={31: Preset(2)}))["buttons"]
        self.assertEqual((len(rows), rows[31], rows[0]), (32, ("preset", "2"), ("nothing", "")))
        self.assertEqual(save(buttons=rows).buttons, {31: Preset(2)})

    def test_a_tracking_row_ignores_its_number_box(self):
        rows = form.to_fields(PW)["buttons"]
        rows[4] = ("tracking", "7")
        self.assertEqual(save(buttons=rows).buttons[4], Tracking(True))

    def test_spaces_around_a_number_are_fine(self):
        self.assertEqual(save(pan_max=" 12 ", deadzone="0.2 ").pan_max, 12)

    def test_only_preset_takes_a_number(self):
        self.assertEqual([a for a in form.ACTIONS if form.numbered(a)], ["preset"])


class ErrorTest(unittest.TestCase):
    CASES = [               # (field, what the operator typed, the field that gets marked)
        ("host", "192.168.77.3", "host"),
        ("timeout", "3", "timeout"),
        ("timeout", "abc", "timeout"),
        ("pan_axis", "Q", "pan_axis"),
        ("deadzone", "0.8", "deadzone"),
        ("deadzone", "0,15", "deadzone"),
        ("full_speed_at", "1.5", "deadzone"),       # the rule names both: the first is marked (spec)
        ("pan_max", "0", "pan_max"),
        ("pan_max", "2.5", "pan_max"),
        ("tilt_max", "21", "tilt_max"),             # over the camera's ceiling: type_error
        ("save_hold_seconds", "11", "save_hold_seconds"),
        ("camera", "sony", "camera"),
        ("controller", "xbox", "controller"),
    ]

    def test_every_rule_marks_its_field(self):
        for setting, text, marked in self.CASES:
            with self.subTest(setting=setting, text=text):
                with self.assertRaises(form.FieldError) as cm:
                    save(**{setting: text})
                self.assertEqual(cm.exception.setting, marked, cm.exception.message)

    def test_a_comma_decimal_is_named_in_the_usual_words(self):
        with self.assertRaises(form.FieldError) as cm:
            save(deadzone="0,15")
        self.assertEqual(cm.exception.message, "deadzone must be a number, got '0,15'")

    def test_a_bad_preset_row_names_its_row(self):
        rows = form.to_fields(PW)["buttons"]
        rows[2] = ("preset", "x")
        with self.assertRaises(form.FieldError) as cm:
            save(buttons=rows)
        self.assertEqual((cm.exception.setting, cm.exception.row), ("buttons", 2))
        self.assertTrue(cm.exception.message.startswith("button 3: bad command 'preset x'"), cm.exception.message)

    def test_an_empty_password_is_refused(self):
        with self.assertRaises(form.FieldError) as cm:
            save(password="")
        self.assertEqual((cm.exception.setting, cm.exception.message), ("password", "The camera password is not set"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run them to see them fail**

Run: `python -m unittest tests.windows.settings_dialog.test_form -v`
Expected: `ImportError: cannot import name 'form'`.

- [ ] **Step 4: Write `ptz_joystick/windows/settings_dialog/form.py`**

```python
"""The settings dialog's fields, without Tk: each setting's tab and label, Settings ↔ the text in the fields, and
which field an error is about. tabs.py builds the widgets from FIELDS."""
import re
from collections.abc import Callable
from dataclasses import dataclass, fields
from typing import Any, cast

from ... import config
from ...config import BUTTON_COMMANDS, MAX_TIMEOUT, Settings, takes_number

TABS = ("Camera", "Controller", "Buttons", "Other")
NOTHING = "nothing"                 # a button row that fires nothing: left out of [buttons]
ACTIONS = [NOTHING, *BUTTON_COMMANDS]
MIN_ROWS = 12                       # button rows shown even when the file maps fewer


@dataclass(frozen=True)
class Field:
    setting: str                    # a Settings field
    tab: str
    label: str
    hint: str = ""                  # grey text at the right


FIELDS = [                          # every Settings field, in the order the tabs show them
    Field("camera", "Camera", "Camera type"),
    Field("host", "Camera", "Address"),
    Field("user", "Camera", "User"),
    Field("password", "Camera", "Password", "saved for this Windows user"),
    Field("timeout", "Camera", "Timeout (seconds)", f"max {MAX_TIMEOUT:g}"),
    Field("pan_max", "Camera", "Top speed: pan"),           # hint: the camera's ceiling, added by tabs.py
    Field("tilt_max", "Camera", "Top speed: tilt"),
    Field("zoom_max", "Camera", "Top speed: zoom"),
    Field("controller", "Controller", "Controller", "winmm = any controller joy.cpl shows"),
    Field("pan_axis", "Controller", "Pan axis", "joystick only"),
    Field("tilt_axis", "Controller", "Tilt axis"),
    Field("zoom_axis", "Controller", "Zoom axis"),
    Field("invert_tilt", "Controller", "Invert tilt"),
    Field("invert_zoom", "Controller", "Invert zoom"),
    Field("deadzone", "Controller", "Deadzone", "readings at or below are ignored"),
    Field("full_speed_at", "Controller", "Full speed at", "reading that gives top speed"),
    Field("buttons", "Buttons", "Buttons"),
    Field("save_hold_seconds", "Buttons", "Hold to save (s)", "0 = saving off"),
    Field("log_file", "Other", "Log file", "empty = no log"),
    Field("check_updates", "Other", "Check for updates"),
    Field("debug", "Other", "Debug log", "every reading and command"),
]
TYPES = {f.name: cast(type, f.type) for f in fields(Settings)}
NAMED = re.compile(r"\b(" + "|".join(f.setting for f in FIELDS) + r")\b")


class FieldError(Exception):
    """A value Save can't take. setting: the field to mark; row: the button row, for a button."""

    def __init__(self, setting: str, message: str, row: int | None = None):
        super().__init__(message)
        self.setting, self.message, self.row = setting, message, row


def numbered(action: str) -> bool:
    """Whether a button action takes a preset number ("preset 3"), so its number box is on."""
    return action != NOTHING and takes_number(action)


def to_fields(s: Settings) -> dict[str, Any]:
    """What each field shows: text for entries and dropdowns, True/False for checkboxes, the password from
    s.password, and the button rows as (action, number) pairs, numbered from 0."""
    values: dict[str, Any] = {f.setting: getattr(s, f.setting) if TYPES[f.setting] is bool
                              else str(getattr(s, f.setting)) for f in FIELDS if f.setting != "buttons"}
    count = max(MIN_ROWS, max(s.buttons, default=-1) + 1)
    values["buttons"] = [_row(s.buttons.get(i)) for i in range(count)]
    return values


def from_fields(values: dict[str, Any], type_error: Callable[[Settings], str | None]) -> Settings:
    """The fields as Settings, password included, checked as startup checks them. Raises FieldError for the first
    value that's wrong."""
    if not values["password"]:
        raise FieldError("password", "The camera password is not set")
    table: dict[str, Any] = {f.setting: _typed(f.setting, values[f.setting]) for f in FIELDS
                             if f.setting not in ("password", "buttons")}
    table["buttons"] = _buttons(values["buttons"])
    try:
        s = config.from_dict(table, values["password"])
    except ValueError as e:
        raise FieldError(_named_in(str(e)), str(e)) from None
    if message := type_error(s):
        raise FieldError(_named_in(message), message)
    return s


def _row(cmd) -> tuple[str, str]:
    if cmd is None:
        return NOTHING, ""
    action, _, number = config.command_text(cmd).partition(" ")
    return action, number


def _typed(setting: str, value: Any) -> Any:
    """An entry's text as its setting's number type. Text that isn't one stays text, so from_dict says so in its own
    words ("deadzone must be a number, got '0,15'")."""
    want = TYPES[setting]
    if want in (int, float) and isinstance(value, str):
        try:
            return want(value.strip())
        except ValueError:
            pass
    return value


def _buttons(rows: list[tuple[str, str]]) -> dict[str, str]:
    """The button rows as the file's [buttons] table, {"0": "preset 1", ...}, each checked here so an error names
    its row."""
    table = {}
    for i, (action, number) in enumerate(rows):
        if action == NOTHING:
            continue
        text = f"{action} {number.strip()}" if numbered(action) else action
        try:
            config.parse_command(text)
        except ValueError as e:
            raise FieldError("buttons", f"button {i + 1}: {e}", row=i) from None
        table[str(i)] = text
    return table


def _named_in(message: str) -> str:
    """The field an error is about: the first setting its message names. "need 0 <= deadzone < full_speed_at"
    names two: the first is marked."""
    m = NAMED.search(message)
    return m[1] if m else FIELDS[0].setting
```

- [ ] **Step 5: Run the tests**

Run: `python -m unittest tests.windows.settings_dialog.test_form -v`
Expected: all PASS.

- [ ] **Step 6: Full suite, lint, types**

Run: `python -m unittest discover -s tests -t .` then `ruff check .` then `mypy`
Expected: all green.

- [ ] **Step 7: Commit**

```powershell
git add ptz_joystick/windows/settings_dialog/__init__.py ptz_joystick/windows/settings_dialog/form.py tests/windows/settings_dialog/__init__.py tests/windows/settings_dialog/test_form.py
git commit -m "Settings dialog: the fields, and which field an error is about" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The window (`tabs.py`, `window.py`)

**Files:**
- Create: `ptz_joystick/windows/settings_dialog/tabs.py`
- Create: `ptz_joystick/windows/settings_dialog/window.py`
- Test: `tests/windows/settings_dialog/test_window.py`

**Interfaces:**
- Consumes: `form.*` (Task 3); `config.save`, `config.read` (Task 1); `set_user_env` (Task 2).
- Produces: `tabs.Tabs(parent, values, path, cameras, controllers)` with `notebook`, `pages: dict[str, ttk.Frame]`, `vars: dict[str, tk.Variable]`, `error: ttk.Label | None`, `values() -> dict[str, Any]`, `show_error(e: FieldError)`, `clear_error()`. `window.write(path: Path, s: Settings, old_password: str) -> None` (raises `Problem`). `window.SettingsWindow(root, path, settings, cameras, controllers, type_error, write, on_restart, on_notepad)` with `tabs`, `closed: bool`, `save()`, `notepad()`, `close()`, `watch(closing: threading.Event)`. Types: `cameras: dict[str, dict[str, int]]` (camera type → its top speeds), `controllers: list[str]`, `write: Callable[[Settings], None]`, `on_restart` / `on_notepad: Callable[[], None]`.

- [ ] **Step 1: Write the failing tests**

`tests/windows/settings_dialog/test_window.py`:

```python
import tempfile
import threading
import tkinter as tk
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from ptz_joystick import config
from ptz_joystick.app.checks import type_error
from ptz_joystick.app.registry import CAMERAS, CONTROLLERS
from ptz_joystick.config import Settings
from ptz_joystick.core.problem import Problem
from ptz_joystick.windows.settings_dialog import window
from ptz_joystick.windows.settings_dialog.window import SettingsWindow

PATH = Path(r"C:\Users\op\OneDrive - Draco\ptz_joystick.toml")
OLD = replace(Settings(), password="pw")


class WindowTest(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.written: list[Settings] = []
        self.restarts: list[bool] = []
        self.notepads: list[bool] = []
        self.window = SettingsWindow(self.root, PATH, OLD, {n: t.top_speeds for n, t in CAMERAS.items()},
                                     list(CONTROLLERS), type_error, self.written.append,
                                     lambda: self.restarts.append(True), lambda: self.notepads.append(True))
        self.addCleanup(self.window.close)
        self.ask = self.enterContext(mock.patch.object(window.messagebox, "askyesno", return_value=True))
        self.show = self.enterContext(mock.patch.object(window.messagebox, "showerror"))
        self.root.update()

    def type(self, setting, text):
        self.window.tabs.vars[setting].set(text)

    def test_save_writes_the_change_then_asks_to_restart(self):
        self.type("host", "http://10.0.0.9")
        self.window.save()
        self.assertEqual(self.written, [replace(OLD, host="http://10.0.0.9")])
        self.assertEqual(self.ask.call_args.args[1], "Settings saved. Restart now to use them?")
        self.assertEqual((self.restarts, self.window.closed), ([True], True))

    def test_no_means_saved_but_not_restarted(self):
        self.ask.return_value = False
        self.type("user", "operator")
        self.window.save()
        self.assertEqual((len(self.written), self.restarts, self.window.closed), (1, [], True))

    def test_a_bad_value_opens_its_tab_and_keeps_the_dialog_open(self):
        self.type("deadzone", "0.8")
        self.window.save()
        tabs = self.window.tabs
        self.assertEqual(tabs.notebook.select(), str(tabs.pages["Controller"]))
        assert tabs.error is not None
        self.assertIn("deadzone", tabs.error.cget("text"))
        self.assertEqual((self.written, self.window.closed), ([], False))
        self.type("deadzone", "0.1")                # fixed: the next Save goes through
        self.window.save()
        self.assertEqual(len(self.written), 1)

    def test_nothing_changed_just_closes(self):
        self.window.save()
        self.assertEqual(self.written, [])
        self.ask.assert_not_called()
        self.assertTrue(self.window.closed)

    def test_a_failed_write_says_why_and_stays_open(self):
        def refuse(s):
            raise Problem("Can't save ptz_joystick.toml", fix="Check that you can write to its folder", detail="denied")

        self.window._write = refuse
        self.type("user", "operator")
        self.window.save()
        self.assertIn("denied", self.show.call_args.args[1])
        self.assertFalse(self.window.closed)

    def test_open_in_notepad_closes_without_saving(self):
        self.type("user", "operator")
        self.window.notepad()
        self.assertEqual((self.written, self.notepads, self.window.closed), ([], [True], True))

    def test_the_tray_can_close_it(self):
        closing = threading.Event()
        self.window.watch(closing)
        self.assertFalse(self.window.closed)
        closing.set()
        self.window.watch(closing)
        self.assertTrue(self.window.closed)


class WriteTest(unittest.TestCase):
    def test_the_password_is_saved_only_when_it_changed(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(window, "set_user_env") as set_env:
            path = Path(d) / config.FILE_NAME
            window.write(path, OLD, "pw")
            set_env.assert_not_called()
            window.write(path, replace(OLD, password="new"), "pw")
            set_env.assert_called_once_with("PTZ_PASSWORD", "new")
            self.assertEqual(config.read(path), Settings())         # the file never holds the password


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m unittest tests.windows.settings_dialog.test_window -v`
Expected: `ImportError: cannot import name 'window'`.

- [ ] **Step 3: Write `ptz_joystick/windows/settings_dialog/tabs.py`**

```python
"""The settings dialog's four tabs, built from form.FIELDS: a row per setting (label, input, hint), plus the button
rows. Every call on the dialog's thread."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any

from ...config import AXES
from .form import ACTIONS, FIELDS, TABS, FieldError, numbered

PER_COLUMN = 6                  # button rows per column on the Buttons tab, two columns
AXIS_SETTINGS = ("pan_axis", "tilt_axis", "zoom_axis")


class Tabs:
    """The notebook, a variable per field, and marking the field an error is about."""

    def __init__(self, parent: tk.Misc, values: dict[str, Any], path: Path, cameras: dict[str, dict[str, int]],
                 controllers: list[str]):
        style = ttk.Style(parent)
        style.configure("Hint.TLabel", foreground="#666666")
        style.configure("Bad.TLabel", foreground="#c42b1c")
        self.notebook = ttk.Notebook(parent)
        self.pages = {tab: ttk.Frame(self.notebook, padding=10) for tab in TABS}
        for tab, page in self.pages.items():
            self.notebook.add(page, text=tab)
        choices = {"camera": list(cameras), "controller": controllers, **dict.fromkeys(AXIS_SETTINGS, list(AXES))}
        tops = cameras.get(values["camera"], {})
        self.vars: dict[str, tk.Variable] = {}
        self.inputs: dict[str, tk.Widget] = {}
        self.labels: dict[str, ttk.Label] = {}
        self.places: dict[str, tuple[ttk.Frame, int]] = {}       # setting -> (its page, its grid row)
        self.rows: list[tuple[ttk.Label, tk.StringVar, tk.StringVar, ttk.Entry]] = []     # the button rows
        self.error: ttk.Label | None = None                      # the message under a bad field
        self._marked: ttk.Label | None = None                    # that field's label, now red
        next_row = dict.fromkeys(TABS, 0)
        for f in FIELDS:
            page, row = self.pages[f.tab], next_row[f.tab]
            next_row[f.tab] += 2                                  # the row below is for an error message
            self.places[f.setting] = page, row
            if f.setting == "buttons":
                self._button_rows(page, row, values["buttons"])
                continue
            value = values[f.setting]
            widget: tk.Widget
            if isinstance(value, bool):
                var: tk.Variable = tk.BooleanVar(page, value)
                widget = ttk.Checkbutton(page, text=f.label, variable=var)
            else:
                var = tk.StringVar(page, value)
                label = ttk.Label(page, text=f.label)
                label.grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)
                self.labels[f.setting] = label
                if f.setting in choices:
                    widget = ttk.Combobox(page, textvariable=var, values=choices[f.setting], state="readonly",
                                          width=21)
                else:
                    widget = ttk.Entry(page, textvariable=var, width=24, show="●" if f.setting == "password" else "")
            widget.grid(row=row, column=1, sticky="we", pady=2)
            hint = f"max {tops[f.setting]} for {values['camera']}" if f.setting in tops else f.hint
            ttk.Label(page, text=hint, style="Hint.TLabel").grid(row=row, column=2, sticky="w", padx=(10, 0))
            self.vars[f.setting], self.inputs[f.setting] = var, widget
        other, row = self.pages["Other"], next_row["Other"]
        ttk.Label(other, text="Settings file", style="Hint.TLabel").grid(row=row, column=0, sticky="w", pady=(12, 0))
        ttk.Label(other, text=str(path), wraplength=420).grid(row=row + 1, column=0, columnspan=3, sticky="w")

    def values(self) -> dict[str, Any]:
        """What the fields hold now, in form.to_fields' shape."""
        values: dict[str, Any] = {setting: var.get() for setting, var in self.vars.items()}
        values["buttons"] = [(action.get(), number.get()) for _, action, number, _ in self.rows]
        return values

    def show_error(self, e: FieldError):
        """Open the field's tab, turn its label red, show the message under it, and put the cursor there."""
        page, row = self.places[e.setting]
        self.notebook.select(page)
        widget: tk.Widget | None
        if e.row is not None:
            self._marked, _, _, widget = self.rows[e.row]
        else:
            self._marked, widget = self.labels.get(e.setting), self.inputs.get(e.setting)
        if self._marked:
            self._marked.configure(style="Bad.TLabel")
        self.error = ttk.Label(page, text=e.message, style="Bad.TLabel", wraplength=420)
        self.error.grid(row=row + 1, column=0, columnspan=3, sticky="w")
        if widget:
            widget.focus_set()

    def clear_error(self):
        if self.error:
            self.error.destroy()
        if self._marked:
            self._marked.configure(style="TLabel")
        self.error = self._marked = None

    def _button_rows(self, page: ttk.Frame, row: int, rows: list[tuple[str, str]]):
        """Button / Action / Preset, in two columns. Numbered as joy.cpl shows them: index + 1."""
        table = ttk.Frame(page)
        table.grid(row=row, column=0, columnspan=3, sticky="w")
        per_column = max(PER_COLUMN, (len(rows) + 1) // 2)
        for i, (action, number) in enumerate(rows):
            col, r = 3 * (i // per_column), 1 + i % per_column
            if r == 1:
                for c, title in enumerate(("Button", "Action", "Preset")):
                    ttk.Label(table, text=title, style="Hint.TLabel").grid(row=0, column=col + c, sticky="w")
            label = ttk.Label(table, text=str(i + 1))
            label.grid(row=r, column=col, sticky="w", padx=(20 if col else 0, 6))
            action_var, number_var = tk.StringVar(table, action), tk.StringVar(table, number)
            ttk.Combobox(table, textvariable=action_var, values=ACTIONS, state="readonly", width=10).grid(
                row=r, column=col + 1, pady=2)
            entry = ttk.Entry(table, textvariable=number_var, width=5)
            entry.grid(row=r, column=col + 2, padx=(6, 0))
            _number_box_follows(action_var, entry)
            self.rows.append((label, action_var, number_var, entry))


def _number_box_follows(action: tk.StringVar, entry: ttk.Entry):
    """Grey the number box while the action takes no number (nothing, tracking)."""
    def sync(*_):
        entry.state(["!disabled"] if numbered(action.get()) else ["disabled"])

    action.trace_add("write", sync)
    sync()
```

- [ ] **Step 4: Write `ptz_joystick/windows/settings_dialog/window.py`**

```python
"""The settings dialog's window: the tabs, Save / Cancel / Open in Notepad, and what Save does. Every call on the
dialog's thread (__init__.py)."""
import logging
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk

from ... import config
from ...config import Settings
from ...core.problem import Problem
from ..user_env import set_user_env
from . import form
from .tabs import Tabs

log = logging.getLogger(__name__)

TITLE = "ptz_joystick settings"
RESTART_QUESTION = "Settings saved. Restart now to use them?"
WATCH_MS = 100                  # how often the window checks whether the tray asked it to close


def write(path: Path, s: Settings, old_password: str):
    """Save the settings file, then the password if it changed. Raises Problem."""
    config.save(path, s)
    if s.password != old_password:
        try:
            set_user_env("PTZ_PASSWORD", s.password)
        except OSError as e:
            raise Problem("Can't save the camera password", fix='Run setx PTZ_PASSWORD "..." in a terminal',
                          detail=str(e)) from None


class SettingsWindow:
    """Fills root. settings: as the file has them, with the current password. write(s) saves; on_restart and
    on_notepad go back to the tray."""

    def __init__(self, root: tk.Tk, path: Path, settings: Settings, cameras: dict[str, dict[str, int]],
                 controllers: list[str], type_error: Callable[[Settings], str | None],
                 write: Callable[[Settings], None], on_restart: Callable[[], None], on_notepad: Callable[[], None]):
        self.root, self._path, self._old = root, path, settings
        self._type_error, self._write, self._on_restart, self._on_notepad = type_error, write, on_restart, on_notepad
        self.closed = False
        root.title(TITLE)
        root.resizable(False, False)
        setattr(root, "report_callback_exception", self._failed)     # the windowed exe has no stderr to print to
        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)
        self.tabs = Tabs(frame, form.to_fields(settings), path, cameras, controllers)
        self.tabs.notebook.pack(fill="both", expand=True)
        bar = ttk.Frame(frame, padding=(0, 10, 0, 0))
        bar.pack(fill="x")
        ttk.Button(bar, text="Open in Notepad", command=self.notepad).pack(side="left")
        ttk.Button(bar, text="Cancel", command=self.close).pack(side="right")
        ttk.Button(bar, text="Save", command=self.save, default="active").pack(side="right", padx=(0, 8))
        root.bind("<Return>", lambda _: self.save())
        root.bind("<Escape>", lambda _: self.close())
        root.protocol("WM_DELETE_WINDOW", self.close)

    def save(self):
        """Check every field; the first bad one is marked and the dialog stays. Then write, ask, close."""
        self.tabs.clear_error()
        try:
            s = form.from_fields(self.tabs.values(), self._type_error)
        except form.FieldError as e:
            self.tabs.show_error(e)
            return
        if s == self._old:
            self.close()
            return
        try:
            self._write(s)
        except Problem as p:
            messagebox.showerror(TITLE, p.log_line(), parent=self.root)
            return
        log.info("Settings saved to %s", self._path)
        restart = messagebox.askyesno(TITLE, RESTART_QUESTION, parent=self.root)
        self.close()
        if restart:
            self._on_restart()

    def notepad(self):
        """Close without saving, then open the file: one editor at a time, so neither overwrites the other."""
        self.close()
        self._on_notepad()

    def close(self):
        if not self.closed:
            self.closed = True
            self.root.destroy()

    def watch(self, closing: threading.Event):
        """Close when the tray asks (Quit, logoff). Checked every WATCH_MS: only this thread may touch Tk."""
        if closing.is_set():
            self.close()
        elif not self.closed:
            self.root.after(WATCH_MS, self.watch, closing)

    def _failed(self, kind, value, tb):
        log.error("Settings dialog: unexpected error", exc_info=(kind, value, tb))
```

- [ ] **Step 5: Run the tests**

Run: `python -m unittest tests.windows.settings_dialog.test_window -v`
Expected: all PASS. (The tests build a real, hidden Tk window: they need a desktop session, which the Windows CI runner has.)

- [ ] **Step 6: Look at it once**

```powershell
python -c "import tkinter as tk; from dataclasses import replace; from pathlib import Path; from ptz_joystick.app.checks import type_error; from ptz_joystick.app.registry import CAMERAS, CONTROLLERS; from ptz_joystick.config import Settings; from ptz_joystick.windows.settings_dialog.window import SettingsWindow; r = tk.Tk(); SettingsWindow(r, Path('x.toml'), replace(Settings(), password='pw'), {n: t.top_speeds for n, t in CAMERAS.items()}, list(CONTROLLERS), type_error, print, lambda: None, lambda: None); r.mainloop()"
```
Expected: the window with four tabs as in the spec. Click through each tab, type `0.8` as Deadzone, click Save: the Controller tab shows the red label and message. Esc closes.

- [ ] **Step 7: Full suite, lint, types**

Run: `python -m unittest discover -s tests -t .` then `ruff check .` then `mypy`
Expected: all green.

- [ ] **Step 8: Commit**

```powershell
git add ptz_joystick/windows/settings_dialog/tabs.py ptz_joystick/windows/settings_dialog/window.py tests/windows/settings_dialog/test_window.py
git commit -m "Settings dialog: the window (tabs, Save, Cancel, Open in Notepad)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The dialog's thread (`open_dialog`, `Handle`)

**Files:**
- Modify: `ptz_joystick/windows/settings_dialog/__init__.py` (whole file below)
- Test: `tests/windows/settings_dialog/test_open_dialog.py`

**Interfaces:**
- Consumes: `SettingsWindow`, `write` (Task 4); `config.read`, `config.write_template_if_missing` (Task 1); `ask` (Task 2); `user_env`.
- Produces: `settings_dialog.open_dialog(path: Path, cameras: dict[str, dict[str, int]], controllers: list[str], type_error: Callable[[Settings], str | None], on_restart: Callable[[], None], on_notepad: Callable[[], None]) -> Handle`. `Handle` has `alive: bool` (property), `hwnd: int`, `thread: threading.Thread | None`, `focus()`, `close()`. The callbacks run on the dialog's thread.

- [ ] **Step 1: Write the failing tests**

`tests/windows/settings_dialog/test_open_dialog.py`:

```python
import gc
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from ptz_joystick import config
from ptz_joystick.app.checks import type_error
from ptz_joystick.app.registry import CAMERAS, CONTROLLERS
from ptz_joystick.windows import settings_dialog


class OpenDialogTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(tempfile.TemporaryDirectory())) / config.FILE_NAME
        self.notepads: list[bool] = []

    def open(self):
        handle = settings_dialog.open_dialog(self.path, {n: t.top_speeds for n, t in CAMERAS.items()},
                                             list(CONTROLLERS), type_error, lambda: None,
                                             lambda: self.notepads.append(True))
        assert handle.thread is not None
        return handle, handle.thread

    def test_a_broken_file_offers_notepad_instead(self):
        self.path.write_text('hots = "x"', encoding="utf-8")
        with mock.patch.object(settings_dialog, "ask", return_value=True) as ask:
            _, thread = self.open()
            thread.join(5)
        text = ask.call_args.args[0]
        self.assertTrue(text.startswith(f"Bad setting in {config.FILE_NAME}: unknown setting 'hots'"), text)
        self.assertTrue(text.endswith("\n\nOpen it in Notepad?"), text)
        self.assertEqual(self.notepads, [True])

    def test_no_to_the_offer_opens_nothing(self):
        self.path.write_text('hots = "x"', encoding="utf-8")
        with mock.patch.object(settings_dialog, "ask", return_value=False):
            _, thread = self.open()
            thread.join(5)
        self.assertEqual(self.notepads, [])

    def test_opens_on_its_own_thread_and_closes_when_the_tray_asks(self):
        handle, _ = self.open()                 # no file yet: the template is written first
        deadline = time.monotonic() + 5
        while not handle.hwnd and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(handle.hwnd and handle.alive)
        self.assertTrue(self.path.exists())
        handle.close()
        self.assertFalse(handle.alive)
        gc.collect()                            # nothing of Tk left for this thread to free: Tcl would abort


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m unittest tests.windows.settings_dialog.test_open_dialog -v`
Expected: `AttributeError: module 'ptz_joystick.windows.settings_dialog' has no attribute 'open_dialog'`.

- [ ] **Step 3: Replace `ptz_joystick/windows/settings_dialog/__init__.py` with**

```python
"""The settings dialog (tray menu → Settings…): every setting and the camera password in one window. It runs on its
own thread: Tk must stay on the thread that made it, and the tray's thread runs the icon's message loop.
open_dialog() is all the tray uses. Windows only."""
import ctypes
import gc
import logging
import os
import threading
import tkinter as tk
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import replace
from pathlib import Path

from ... import config
from ...config import Settings
from ...core.problem import Problem
from ..message_box import ask
from ..user_env import user_env
from .window import SettingsWindow, write

log = logging.getLogger(__name__)

CLOSE_SECONDS = 1.0             # Quit waits this long for the dialog; it checks every 100 ms
SW_RESTORE = 9
DPI_AWARENESS_CONTEXT_SYSTEM_AWARE = -2     # Tk 8.6 scales by the system DPI only

user32 = ctypes.WinDLL("user32", use_last_error=True)       # own copy: we set prototypes below
user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]


class Handle:
    """The tray's hold on an open dialog. focus() and close() are safe from the tray's thread."""

    def __init__(self):
        self.closing = threading.Event()
        self.hwnd = 0                   # the window, once the dialog's thread has made it
        self.thread: threading.Thread | None = None

    @property
    def alive(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def focus(self):
        """Bring the window to the front. Allowed: the tray's menu has just given this process the foreground."""
        if self.hwnd:
            user32.ShowWindow(self.hwnd, SW_RESTORE)
            user32.SetForegroundWindow(self.hwnd)

    def close(self):
        """Close the window (unsaved changes are dropped) and wait for it."""
        self.closing.set()
        if self.thread:
            self.thread.join(CLOSE_SECONDS)


def open_dialog(path: Path, cameras: dict[str, dict[str, int]], controllers: list[str],
                type_error: Callable[[Settings], str | None], on_restart: Callable[[], None],
                on_notepad: Callable[[], None]) -> Handle:
    """Start the dialog on its own thread. cameras: each camera type's top speeds. The callbacks run on the dialog's
    thread, so on_restart must hand over to the tray's thread (HiddenWindow.post)."""
    handle = Handle()
    handle.thread = threading.Thread(target=_run, name="settings-dialog", daemon=True,
                                     args=(handle, path, cameras, controllers, type_error, on_restart, on_notepad))
    handle.thread.start()
    return handle


def _run(handle: Handle, path: Path, cameras, controllers, type_error, on_restart, on_notepad):
    try:
        try:
            config.write_template_if_missing(path)        # deleted since the tray started
            settings = config.read(path)
        except Problem as p:                                # the same words as the red dot
            if ask(f"{p.text()}\n\nOpen it in Notepad?"):
                on_notepad()
            return
        password = user_env("PTZ_PASSWORD") or os.environ.get("PTZ_PASSWORD", "")
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(DPI_AWARENESS_CONTEXT_SYSTEM_AWARE))   # crisp at 150 %
        root = tk.Tk()
        window = SettingsWindow(root, path, replace(settings, password=password), cameras, controllers, type_error,
                                lambda s: write(path, s, password), on_restart, on_notepad)
        window.watch(handle.closing)
        root.update_idletasks()
        handle.hwnd = int(root.wm_frame(), 16)
        root.focus_force()
        root.mainloop()
        del window, root
        gc.collect()            # free every Tk object on this thread: freed on another, Tcl aborts the process
    except Exception:
        log.exception("Settings dialog failed")
```

- [ ] **Step 4: Run the tests**

Run: `python -m unittest tests.windows.settings_dialog.test_open_dialog -v`
Expected: all PASS. The last test shows the real window for a moment.

- [ ] **Step 5: Full suite, lint, types**

Run: `python -m unittest discover -s tests -t .` then `ruff check .` then `mypy`
Expected: all green.

- [ ] **Step 6: Commit**

```powershell
git add ptz_joystick/windows/settings_dialog/__init__.py tests/windows/settings_dialog/test_open_dialog.py
git commit -m "Settings dialog: its own thread, focus and close from the tray" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Tray menu → Settings…

**Files:**
- Modify: `ptz_joystick/app/tray.py`
- Test: `tests/app/test_tray.py`

**Interfaces:**
- Consumes: `settings_dialog.open_dialog`, `Handle` (Task 5); `type_error` (Task 2); `CAMERAS`, `CONTROLLERS`.
- Produces: `tray.load_settings_dialog()` → the `settings_dialog` module, or `None` when tkinter is missing. Menu item `Settings…`.

- [ ] **Step 1: Write the failing tests**

In `tests/app/test_tray.py`, change `test_menu_in_a_source_run`'s expected list to:

```python
                         ["Starting…", "---", "Settings…", "Open log", "Restart", "---", "Quit"])
```

Replace `test_open_settings_keeps_a_path_with_spaces_whole` with these, in `TrayAppTest`:

```python
    def dialog(self):
        """Stand in for the settings dialog module. -> (that module, the handle its open_dialog returns)."""
        module = mock.Mock()
        handle = module.open_dialog.return_value
        handle.alive = True
        self.enterContext(mock.patch.object(tray, "load_settings_dialog", return_value=module))
        return module, handle

    def test_settings_opens_the_dialog_then_brings_it_to_front(self):
        module, handle = self.dialog()
        self.pick("Settings…")
        self.pick("Settings…")
        module.open_dialog.assert_called_once()
        self.assertEqual(module.open_dialog.call_args.args[0], SETTINGS)
        handle.focus.assert_called_once_with()

    def test_a_closed_dialog_opens_again(self):
        module, handle = self.dialog()
        self.pick("Settings…")
        handle.alive = False
        self.pick("Settings…")
        self.assertEqual(module.open_dialog.call_count, 2)

    def test_restart_from_the_dialog_runs_on_the_tray_thread(self):
        module, _ = self.dialog()
        self.app.start_session()
        self.session(1)
        self.pick("Settings…")
        module.open_dialog.call_args.kwargs["on_restart"]()      # called on the dialog's thread
        self.assertEqual(len(self.sessions.started), 1)          # queued, not run there
        self.window.pump()
        self.session(2)

    def test_quit_closes_the_dialog(self):
        _, handle = self.dialog()
        self.pick("Settings…")
        self.app.quit()
        handle.close.assert_called_once_with()

    def test_without_tkinter_settings_opens_notepad_with_the_whole_path(self):
        with mock.patch.object(tray, "load_settings_dialog", return_value=None), \
                mock.patch.object(tray.subprocess, "Popen") as popen:
            self.pick("Settings…")
        popen.assert_called_once_with(["notepad.exe", str(SETTINGS)])

    def test_the_dialog_module_loads(self):
        self.assertIsNotNone(tray.load_settings_dialog())
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m unittest tests.app.test_tray -v`
Expected: FAIL on the menu list (`'Open settings' != 'Settings…'`) and `AttributeError: ... has no attribute 'load_settings_dialog'`.

- [ ] **Step 3: Change `ptz_joystick/app/tray.py`**

Imports: add `from typing import TYPE_CHECKING` after `from pathlib import Path`; add after `from .version import VERSION`:

```python
from .checks import type_error
from .registry import CAMERAS, CONTROLLERS

if TYPE_CHECKING:
    from ..windows.settings_dialog import Handle
```

(Keep the `from .` imports in alphabetical order: `.checks`, `.registry`, `.session`, `.startup`, `.status`, `.version`; put the `TYPE_CHECKING` block after them.)

After `open_in_notepad`, add:

```python
def load_settings_dialog():
    """The settings dialog's module, or None without tkinter: some Python installs, and the console exe (CI leaves
    Tcl/Tk out of it)."""
    try:
        from ..windows import settings_dialog
    except ImportError:
        return None
    return settings_dialog
```

In `TrayApp.__init__`, after `self._thread: threading.Thread | None = None`, add:

```python
        self._dialog: Handle | None = None  # the settings dialog, while it's open
```

Replace `shutdown`:

```python
    def shutdown(self):
        """Stop the camera, close the settings dialog, remove the icon: Quit, logoff, shutdown, a closed terminal."""
        self._stop_session()
        if self._dialog:
            self._dialog.close()
        self._icon.remove()
```

In `_entries`, replace the `Open settings` item with:

```python
            menu.Item("Settings…", self._open_settings),
```

Add after `_entries`:

```python
    def _open_settings(self):
        if self._dialog and self._dialog.alive:
            self._dialog.focus()
            return
        dialog = load_settings_dialog()
        if dialog is None:
            open_in_notepad(str(self._path))
            return
        self._dialog = dialog.open_dialog(
            self._path, {name: t.top_speeds for name, t in CAMERAS.items()}, list(CONTROLLERS), type_error,
            on_restart=lambda: self._window.post(self.restart), on_notepad=lambda: open_in_notepad(str(self._path)))
```

- [ ] **Step 4: Run the tests**

Run: `python -m unittest tests.app.test_tray -v`
Expected: all PASS.

- [ ] **Step 5: Try it from source**

Run: `python -m ptz_joystick --tray`
Expected: click the dot → **Settings…** → the dialog. Click Settings… again → the same window comes to the front. Change User, Save, answer Yes → the dot goes yellow then back (Restart). Quit from the menu with the dialog open → both close, no error in the terminal.

- [ ] **Step 6: Full suite, lint, types**

Run: `python -m unittest discover -s tests -t .` then `ruff check .` then `mypy`
Expected: all green.

- [ ] **Step 7: Commit**

```powershell
git add ptz_joystick/app/tray.py tests/app/test_tray.py
git commit -m "Tray: Settings… opens the settings dialog; Quit closes it" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: CI and docs

**Files:**
- Modify: `.github/workflows/ci.yml` (the console exe's `pyinstaller` line)
- Modify: `README.md`, `docs/settings.md`, `docs/troubleshooting.md`, `docs/extending.md`, `docs/development.md`

**Interfaces:** none (no code).

- [ ] **Step 1: CI keeps Tcl/Tk out of the console exe**

In `.github/workflows/ci.yml`, replace:

```yaml
          pyinstaller --onefile --name ptz_joystick launch.py
```

with:

```yaml
          pyinstaller --onefile --exclude-module tkinter --name ptz_joystick launch.py   # no dialog: ~3 MB less
```

- [ ] **Step 2: `README.md`**

Replace the menu lines

```markdown
- **Open settings**, **Open log**: in Notepad.
- **Restart**: after editing the settings or running `setx PTZ_PASSWORD`.
```

with

```markdown
- **Settings…**: every setting and the camera password in one window. Save checks them, then asks whether to restart. **Open in Notepad** there edits the file itself.
- **Open log**: in Notepad.
- **Restart**: after editing the settings in Notepad or running `setx PTZ_PASSWORD`.
```

In line 18, replace `Edit it to change settings ([every setting](docs/settings.md)); no rebuild needed.` with `Change settings from the tray (**Settings…**) or by editing it ([every setting](docs/settings.md)); no rebuild needed.`

- [ ] **Step 3: `docs/settings.md`**

Replace the first paragraph (line 5) with:

```markdown
Change them in the tray: click the dot → **Settings…**. Save checks every value the way startup does, marks the one that's wrong, then asks whether to restart. It also sets the camera password (`PTZ_PASSWORD`, as `setx` does). Saving rewrites the file in the template's layout, so comments you added by hand are lost.

Or edit the file itself. Settings live in `ptz_joystick.toml`: next to `ptz_joystick.exe`, or in the repo folder (next to README.md) when run with Python. If it's missing, the first run writes it with every setting, its default and a comment. Edit it, save, then restart (tray: right-click the dot → Restart).
```

In the paragraph about bad settings, replace `The password only comes from `PTZ_PASSWORD`.` with `The password only comes from `PTZ_PASSWORD` (Settings… or `setx`).`

- [ ] **Step 4: `docs/troubleshooting.md`**

Replace the row

```markdown
| Changed a setting, nothing happened | Check the `Settings:` line at startup: it shows which file was read. Restart after saving (tray: right-click → Restart) |
```

with

```markdown
| Changed a setting, nothing happened | Answer **Yes** to "Restart now?" after Save in Settings…, or click **Restart**. After editing in Notepad: check the `Settings:` line at startup, it shows which file was read |
```

In the `The camera password is not set` row, replace `Run `setx PTZ_PASSWORD "..."` in a terminal, then` with `Type it in **Settings…** (tray), or run `setx PTZ_PASSWORD "..."` in a terminal, then`.

- [ ] **Step 5: `docs/extending.md`**

Camera step 5: replace `Add `<name>` to the `camera` comment in `TEMPLATE` (`config/template.py`) and to the `camera` row in [settings.md](settings.md). A camera that needs new settings (a COM port, say) adds them to `Settings` (`config/settings.py`) and `TEMPLATE` too.` with:

```markdown
5. Add `<name>` to the `camera` comment in `LAYOUT` (`config/template.py`) and to the `camera` row in [settings.md](settings.md). It shows in the settings dialog's Camera type list by itself. A camera that needs new settings (a COM port, say) adds them to `Settings` (`config/settings.py`), `LAYOUT`, and `FIELDS` in `windows/settings_dialog/form.py` (its tab and label; a test fails until it has one).
```

Controller step 5: replace `TEMPLATE` with `LAYOUT` and add ` It shows in the settings dialog's Controller list by itself.` at the end.

New button action, step 3: add at the end ` It shows in the settings dialog's Action list by itself.`

- [ ] **Step 6: `docs/development.md`**

In the layout block, replace the `template.py` line with:

```
    template.py        the settings file's name, where it lives, the template a first run writes, writing it back
```

After the `message_box.py` line, add:

```
    settings_dialog/   tray menu → Settings…, on its own thread (__init__.py): form.py (fields, no Tk),
                       tabs.py (widgets), window.py (Save / Cancel / Open in Notepad)
```

- [ ] **Step 7: Full suite, lint, types**

Run: `python -m unittest discover -s tests -t .` then `ruff check .` then `mypy`
Expected: all green.

- [ ] **Step 8: Commit**

```powershell
git add .github/workflows/ci.yml README.md docs/settings.md docs/troubleshooting.md docs/extending.md docs/development.md
git commit -m "Docs and CI: the settings dialog; Tcl/Tk only in the tray exe" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 9: Manual check list for the PR (on a Draco PC, with the CI-built tray exe)**

Copy into the PR description, tick each by hand:

1. Settings… → change the address → Save → Yes → green, with the new camera.
2. Deadzone `0.8` → Save → the Controller tab opens, the Deadzone label and the message under it are red.
3. Change the password → Save → Yes → the camera answers. A new terminal: `echo %PTZ_PASSWORD%` shows the new value.
4. At 150 % display scaling the text is crisp. The elevated tray (Zao) opens the dialog and saves.
5. Settings… twice → one window, brought to the front. Open and close the dialog 5 times, then Quit with it open → no crash box.
6. Break the file in Notepad → Settings… → "Open it in Notepad?".
7. Tray exe size before and after (expect about +3 MB); the console exe the same as before.
