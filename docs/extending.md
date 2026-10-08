# Extending

[← README](../README.md)

Paths are inside `ptz_joystick/` unless they start with `tests/`. How the pieces fit together: [development.md](development.md#how-its-built).

Users pick the camera and controller with `camera =` and `controller =` in `ptz_joystick.toml`. Each name comes from the `CAMERAS` / `CONTROLLERS` tables in `app/registry.py`. Adding a type is one adapter file, one line in that table and one test class. Nothing else changes.

## Adding a camera (e.g. VISCA over IP)

1. Read the rules on `Camera.send` in `cameras/__init__.py`.
2. Add `cameras/<name>.py` with:
   - a class that has `send(cmd) -> bool`
   - `TOP_SPEEDS = {"pan_max": …, "tilt_max": …, "zoom_max": …}`: the highest speed the camera accepts for each. Startup refuses settings above them.
3. Add a line to `CAMERAS` in `app/registry.py`: `"<name>": CameraType(lambda s: YourCamera(s.host, …), <name>.TOP_SPEEDS)`. `mypy` checks the class against `Camera` there.
4. Add `tests/cameras/test_<name>.py` with a class that subclasses `contracts.CameraContract` (`from tests import contracts`). Fill in two hooks:
   - `make(up)`: your camera with a fake connection that always works (`up=True`) or always fails
   - `top_speeds`

   The contract checks that stops always work, every command is sent or refused with `TypeError`, a camera that's down returns `False` and logs once, and `TOP_SPEEDS` is complete. `tests/cameras/test_ptzoptics.py` is the example.
5. Add `<name>` to the `camera` comment in `TEMPLATE` (`config/template.py`) and to the `camera` row in [settings.md](settings.md). A camera that needs new settings (a COM port, say) adds them to `Settings` (`config/settings.py`) and `TEMPLATE` too.

If a camera adapter raises `TypeError` (a command it can't do at all), the sender logs it and drops that command. Any other error from an adapter counts as a refusal and is retried, so a network error can never lose a stop.

## Adding a controller (XInput, pygame, MIDI)

1. Read the rules on `Controller.read` in `controllers/__init__.py`.
2. Add `controllers/<name>.py` with a class that has `read()`, and a function that takes `Settings` and returns a ready controller (like `keyboard.start`).
3. Add a line to `CONTROLLERS` in `app/registry.py`: `"<name>": <name>.start`. `mypy` checks it against `Controller` there.
4. Add `tests/controllers/test_<name>.py` with a class that subclasses `contracts.ControllerContract`. Fill in three hooks:
   - `at_rest()`: a reading with sticks centred and nothing held
   - `full_push()`: a reading with every axis pushed to one end and only button 1 held
   - `unplugged()`: a reading with the device gone. Leave it out if the device can't be unplugged

   The contract checks the axis letters, the -1..1 range, that button 1 is bit 0, and that unplugged reads `None`. `tests/controllers/test_winmm.py` and `test_keyboard.py` are the examples.
5. Add `<name>` to the `controller` comment in `TEMPLATE` (`config/template.py`) and to the `controller` row in [settings.md](settings.md).

## New button action (home, focus, …)

1. Read the rules at the top of `core/commands.py`: a complete instruction that is safe to send twice.
2. Add a frozen dataclass there and add it to `Command`.
3. Give it a name in `BUTTON_COMMANDS` in `config/settings.py`, then map a button to it in `ptz_joystick.toml`.
4. Add an example to `EXAMPLES` in `tests/contracts.py`, and a `case` for it in every camera's adapter (`to_query()` in `cameras/ptzoptics.py`). The contract tests fail until you do both.

The sender needs no change: anything that isn't a stick move gets 3 tries, then is dropped.

## Speed curve / deadzone behaviour

`core/mapping.py` only, covered by `tests/core/test_mapping.py`.
