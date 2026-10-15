# Settings dialog: design

2026-10-15 · Design approved in chat, section by section, with mockups. This file is the reference for the implementation plan. It replaces the tray spec's out-of-scope line "Editing settings or the password from the tray".

## Goal

An operator changes any setting, and the camera password, from the tray without seeing `ptz_joystick.toml` or a terminal.

- Tray menu → **Settings…** opens a window with every setting from [settings.md](../../settings.md), plus the password.
- Save checks every value first, with the same rules and words as startup, and marks the field that's wrong.
- Notepad stays as the fallback: an "Open in Notepad" link in the dialog.

## Decisions

| Topic | Decision |
|---|---|
| Scope | Every setting, plus `PTZ_PASSWORD`. Notepad becomes the fallback. |
| Toolkit | tkinter + ttk ("vista" theme), stdlib. The window runs on its own thread. |
| Rejected | Raw Win32 controls via ctypes: fully native and no size growth, but 3–4× the code, with hand-placed layout, DPI handling and control IDs. A local web page: it would send the password over localhost and add a server. |
| Layout | Tabs: Camera · Controller · Buttons · Other. Save, Cancel, "Open in Notepad" below them. |
| Password | A masked field, filled with the current value. Save writes `HKCU\Environment\PTZ_PASSWORD`, as `setx` does. |
| On Save | Check, write the file, then ask "Settings saved. Restart now to use them?" Yes / No. |
| File format | Save rewrites the whole file in the template's layout, with the template's comments. Comments the operator added in Notepad are lost, and the header says so. |
| Errors | The same words as the log (setting names included). The field is marked red and its tab opens. |
| Size | Tray exe about +3 MB (Tcl/Tk compressed; 11 MB unpacked at each start). The console exe doesn't change. |

## What the operator sees

### Menu

`Open settings` becomes **`Settings…`**. If the dialog is already open, picking it again brings that window to the front. Everything else in the menu stays.

### The window

Title `ptz_joystick settings`. Every field starts with the value from the file.

| Tab | Fields (hint at the right) |
|---|---|
| Camera | Camera type (dropdown of `CAMERAS`) · Address · User · Password (masked; "saved for this Windows user") · Timeout (seconds; "max 2") · **Top speeds**: Pan / Tilt / Zoom (the hint shows the selected camera type's ceiling, e.g. "max 24 for ptzoptics") |
| Controller | Controller (dropdown of `CONTROLLERS`; "winmm = any controller joy.cpl shows") · **Axes** ("joystick only"): Pan / Tilt / Zoom (dropdowns `X Y Z R U V`) · Invert tilt · Invert zoom · Deadzone · Full speed at |
| Buttons | Rows numbered as `joy.cpl` shows them (index + 1). Rows go up to 12, or to the highest button the file uses (at most 32). Each row has an Action dropdown (`nothing` plus every `BUTTON_COMMANDS` name) and a Preset number box. The number box is greyed when the action takes no number, meaning its factory in `BUTTON_COMMANDS` has no parameter. Below the rows: Hold to save (s) ("0 = saving off"). |
| Other | Log file ("empty = no log") · Check for updates · Debug log ("every reading and command") · the settings file's full path (read-only text) |

Keys: Tab moves between fields, Enter = Save, Esc = Cancel.

### Save

1. A bad value: its tab opens, the field gets a red border, the message appears under it, and the cursor goes there. The dialog stays open. One error at a time: the first one found.
2. Nothing changed: the dialog closes. No write, no question.
3. Otherwise the file is written, the password is saved if it changed, then *"Settings saved. Restart now to use them?"* Yes queues Restart on the tray. Either answer closes the dialog.

### Leaving without saving

- Cancel, Esc and ✕ close without writing.
- **Open in Notepad** closes the dialog without saving, then opens the file in Notepad. Only one editor is open at a time, so neither overwrites the other.

### A broken file

If the file can't be read (bad TOML, unknown setting, wrong type, bad value), the dialog doesn't open. A Yes/No box shows the same Problem text as the red dot, then *"Open it in Notepad?"* If the file only breaks the camera-type rules (an unknown `camera`, a speed over the ceiling), the dialog opens, and Save marks that field.

## How it's built

### Threads

- **Tray thread** (main): the menu click calls `settings_dialog.open_dialog(...)` and keeps the handle. A second click calls `handle.focus()`, which is `SetForegroundWindow` on the dialog's HWND (a plain Win32 call, safe from any thread). The tray has foreground rights right after its menu.
- **Dialog thread** (`settings-dialog`, daemon): calls `SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_SYSTEM_AWARE)`, then reads the file, then creates `Tk()` and runs `mainloop()`. All Tk calls happen on this thread. Every 100 ms (`after`), it checks a `queue.SimpleQueue` for `"close"`.
- **Restart** goes back through `HiddenWindow.post(app.restart)`, the same route session news takes.
- **Quit, logoff, shutdown, closed terminal:** `TrayApp.shutdown()` calls `handle.close()`, which queues `"close"` and joins up to 1 s. This prevents a Tk window dying with its daemon thread at exit, which can raise `Tcl_AsyncDelete` and a crash box in the windowed exe.

### Opening

1. `config.write_template_if_missing(path)`, in case the file was deleted after start.
2. `config.read(path)` → `Settings`, or a `Problem`, which leads to the broken-file box (`message_box.ask`) and, on Yes, `open_in_notepad`.
3. Password: `user_env("PTZ_PASSWORD")`, else `os.environ`, else empty.
4. Build the window from `form.to_fields(settings, password)`.

### Saving: `form.py`

1. `form.from_fields(fields)` builds the values for `from_dict`:
   - A number field whose text doesn't parse as that number goes through as text, so `from_dict` reports it in its usual words: `deadzone must be a number, got 'abc'`.
   - Each button row becomes `"preset N"`, `"tracking"` or is left out (`nothing`), and goes through `parse_command` row by row, so an error names its row.
   - An empty password gives `The camera password is not set` on the Password field.
2. `config.from_dict(values, password)`, which also runs `Settings.__post_init__`.
3. `type_error(s)`: the camera-type rules (known camera and controller, speeds within the ceiling).
4. The first `ValueError` or `type_error` message marks a field: the first setting name in the message, as a whole word, decides which. A message naming two settings (`need 0 <= deadzone < full_speed_at <= 1`) marks the first.
5. `s == old and password == old_password`: just close.
6. Write: `render(s)` to `<file>.tmp` in the same folder, then `os.replace`. An `OSError` gives `Problem(f"Can't save {path.name}", fix="Check that you can write to its folder", detail=str(e))`, shown in a box with its detail. The dialog stays open.
7. Password changed: `set_user_env("PTZ_PASSWORD", password)`.
8. `tkinter.messagebox.askyesno(...)`, then `on_restart()` on Yes, then destroy the window.

### What the tray hands in

`windows/` never imports `app/`, so `app/tray.py` passes the choices as arguments:

```python
open_dialog(path, cameras={name: t.top_speeds for name, t in CAMERAS.items()}, controllers=list(CONTROLLERS),
            type_error=type_error, on_restart=lambda: self._window.post(self.restart))
```

### New files

| File | Purpose |
|---|---|
| `windows/settings_dialog/__init__.py` | `open_dialog(...) -> Handle` (`focus()`, `close()`, `alive`). Starts the thread. |
| `windows/settings_dialog/form.py` | Pure logic, no Tk. The field table (setting, tab, label, hint), `to_fields`, `from_fields`, mapping an error to a field, "nothing changed". |
| `windows/settings_dialog/tabs.py` | The four tabs' widgets, built from the field table, plus the button rows. |
| `windows/settings_dialog/window.py` | The Tk root, the tabs, Save / Cancel / Open in Notepad, error marking, the close queue, DPI awareness. |

### Changes to existing files

| File | Change |
|---|---|
| `config/template.py` | `render(s: Settings) -> str`: the template's lines with `s`'s values. Strings are written as TOML basic strings, with `\`, `"` and every control character escaped. `json.dumps(v, ensure_ascii=False)` does all of that except DEL (U+007F), which TOML also forbids raw, so `render` escapes it as `\u007f`. Bools as `true` / `false`, numbers with `repr`, and the `[buttons]` rows from `s.buttons`. `TEMPLATE = render(Settings())`. Only the header comment changes from today's text. The installer's `host = ` and `controller = ` lines stay exactly as they are. |
| `config/template.py` header | `# ptz_joystick settings. Easiest: tray menu → Settings…, which rewrites this file (comments you add are lost).` and `# Or edit here, save, then restart ptz_joystick (tray: right-click → Restart).` The password line stays. |
| `config/loading.py` | `read(path) -> Settings`: `read_text`, `tomllib`, then `from_dict` with password `""`, raising the same Problems as today. `load()` = the password check, then `read()`, then the full log path. New `command_text(cmd) -> str`, the reverse of `parse_command`. |
| `config/__init__.py` | Export `read`, `render`, `command_text`. |
| `app/checks.py` | `type_error(s) -> str | None` holds the camera/controller/speed rules. `check_types(s, path)` raises `bad_setting(path, msg)` when it returns a message. Same messages as today. |
| `windows/user_env.py` | `set_user_env(name, value, key=KEY)`: REG_SZ in `HKCU\<key>`, then `SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 1000, None)`, so programs started later see it, as after `setx`. |
| `windows/message_box.py` | `ask(text) -> bool`: `MB_YESNO \| MB_ICONQUESTION`. |
| `app/tray.py` | The `Settings…` item, `self._dialog` (a handle, or None), and `close()` in `shutdown()`. If `import tkinter` fails (a source run without Tk), it falls back to `open_in_notepad`. |

## Build, CI, tests, docs

### CI: `.github/workflows/ci.yml`

- Add `--exclude-module tkinter` to the console exe's `pyinstaller` line. Both exes come from the same entry point, so without it the console exe grows too.
- The tray exe's smoke test stays as it is. It must still start and log the password check.

### Tests

| Test file | Test |
|---|---|
| `tests/config/test_template.py` | `render` round-trips a non-default `Settings`: quotes and backslashes in strings, Hebrew, a `tracking` button, button 31, `log_file = ""`. The existing tests keep `TEMPLATE` equal to the defaults and listing every setting. One added test: the `host = "` and `controller = "` lines start a line, for the installer. |
| `tests/config/test_loading.py` | `command_text(parse_command(t)) == t` for each `BUTTON_COMMANDS` kind. `read()` keeps `log_file` as written. |
| `tests/app/test_checks.py` | `type_error` returns the message, or None. The existing `check_types` tests are unchanged. |
| `tests/windows/settings_dialog/test_form.py` | `from_fields(to_fields(s, pw))` gives `s, pw` back. **Every rule marks the right field**: a table of (field, bad value) covering `from_dict` types, every `Settings.__post_init__` check, top speeds, a bad preset row and an empty password, each giving the expected field and tab. Unchanged fields mean "nothing changed". |
| `tests/windows/settings_dialog/test_window.py` | Builds the window hidden (`withdraw`), pumps it with `update()`, sets a field, calls Save with a fake writer. The right `Settings` reach the writer. A bad deadzone switches to the Controller tab and marks the field. |
| `tests/windows/test_user_env.py` | `set_user_env` then `user_env` reads the same value (with `scratch_key`). |
| `tests/app/test_tray.py` | The menu reads `Settings…`. Picking it opens the dialog (mocked). Picking it again focuses the dialog. Quit closes it. A missing tkinter falls back to Notepad. |
| `tests/test_messages.py` | Unchanged. It checks the new `Can't save` Problem automatically. |

### Manual check (PR checklist, on a Draco PC)

1. Settings… → change the address → Save → Yes → green, with the new camera.
2. Deadzone 0.8 → Save → the Controller tab opens, with that field red and the message under it.
3. Change the password → Save → Yes → the camera answers. In a new terminal, `echo %PTZ_PASSWORD%` shows the new value.
4. At 150 % display scaling, the text is crisp. The elevated tray (Zao) opens the dialog and saves.
5. Settings… twice → one window, brought to the front. Quit with the dialog open → no crash box.
6. Break the file in Notepad → Settings… → the "Open it in Notepad?" box.
7. Tray exe size before and after, in the PR.

### Docs

- `README.md`: in the menu list, **Settings…** (every setting in one window; Notepad from there), and Restart via the question after Save.
- `docs/settings.md`: the intro leads with tray → Settings…; editing the file stays as the second way. The note that Save drops hand-added comments.
- `docs/troubleshooting.md`: "Changed a setting, nothing happened" → answer Yes to "Restart now?", or Restart from the menu.
- `docs/extending.md`: a camera that needs new settings also adds rows to the field table in `windows/settings_dialog/form.py`. A new button action shows up in the Action dropdown by itself.
- `docs/development.md`: the new files in the layout.

## Accepted limits (upgrade when they bite)

- **Notepad opened from Explorer while the dialog is open:** the last save wins. Upgrade: compare the file's modified time at Save.
- **`--keyboard`:** still overrides the controller at run time. The dialog shows the file's value.
- **String style:** a single-quoted string comes back double-quoted with escapes (`'D:\logs'` → `"D:\\logs"`). Same value.
- **Second monitor with different scaling:** Tk 8.6 is system-DPI-aware only, so the dialog is slightly blurry there.
- **Elevated tray with another admin account at the UAC prompt:** the password lands in that account's HKCU, which is where the elevated tray reads it. The same as today with `setx`.

## Out of scope

- Live tuning (changes taking effect without Restart).
- A "Show password" box, a "Discard changes?" question on Cancel.
- A test-the-axes view (debug = true shows which axis moves).
- Setting Start with Windows in the dialog: it stays in the tray menu.
