# Development

[← README](../README.md)

## Tests

From the repo folder:

```powershell
python -m unittest discover -s tests -t .
```

These need no camera and no controller. Fakes stand in for both.

Lint and type check (CI runs the same):

```powershell
pip install ruff==0.16.10 mypy==2.4.0 types-requests==2.33.0.20261006
ruff check .
mypy
```

`mypy` reads its settings from `mypy.ini`. It is what checks that every camera and controller matches its Protocol.

## The tray from source

```powershell
python -m ptz_joystick --tray     # the tray icon, plus the log in this terminal
pythonw -m ptz_joystick --tray    # the tray icon only, like ptz_joystick_tray.exe
```

Quit from the tray menu, or close the terminal. Ctrl+C works too, at the tray's next window message (moving the mouse over the icon sends one). All three stop the camera first.

## How it's built

Ports and adapters. The logic never touches hardware, so you can change it and test it without a camera.

```
ptz_joystick/          the package
  __main__.py          python -m ptz_joystick → app/main.py
  config/              every setting (import from config: config.load, config.Settings, ...)
    settings.py        Settings: defaults + validation, BUTTON_COMMANDS
    template.py        the settings file's name, where it lives, the template a first run writes
    loading.py         ptz_joystick.toml → Settings (types, buttons, encodings, error messages)
  app/                 runs the program
    main.py            composition root: reads settings, builds the adapters, runs the checks, starts the loop;
                       --tray hands over to tray.py
    startup.py         the startup steps both modes share: settings file, settings, checks, logging
    tray.py            tray mode: hidden window, icon, menu, one session at a time
    session.py         one tray session on its own thread: the startup steps, then the loop
    status.py          what the tray shows: dot color, status text, pop-ups (plain rules)
    registry.py        CAMERAS / CONTROLLERS: every type camera = / controller = can name
    checks.py          startup checks: known types, speed ceilings, camera answers, controller has the axes
    loop.py            the control loop; always ends with the camera stopped
    logs.py            terminal + log file setup
    updates.py         startup notice when a newer GitHub release exists (never downloads)
    version.py         "dev"; CI writes the tag here for release builds
  core/                the logic: no hardware, no I/O
    commands.py        PanTilt, Zoom, Preset: camera-agnostic, signed speeds, 0 = stop
    mapping.py         stick → commands (deadzone, scaling, ignores small stick jitter, button presses)
    sender.py          background thread: latest command per type wins, retries until the camera accepts
  cameras/             Camera port (__init__.py) + ptzoptics.py adapter
  controllers/         Controller port (__init__.py) + winmm.py and keyboard.py adapters
  windows/             Windows plumbing that is neither program flow nor an adapter
    console.py         console close / logoff / shutdown → stop the camera
    focus.py           "is our window in front?" for controllers/keyboard.py
    single_instance.py "already running?": a named mutex both exes share
    autostart.py       Start with Windows: the HKCU Run key
    user_env.py        PTZ_PASSWORD as setx left it (HKCU\Environment)
    message_box.py     a message box, for errors before the tray icon exists
    tray/              the tray's Windows API: window.py (message loop), icon.py, menu.py, dots.py
tests/                 mirrors the package: tests/<folder>/test_<module>.py tests ptz_joystick/<folder>/<module>.py
  test_entry_point.py  __main__.py: crashes go to the log, Ctrl+C stays quiet
  contracts.py         the port rules as tests; every adapter's tests subclass one
  fakes.py             scripted controller and recording camera for the app tests
  windows/scratch_key.py  a throwaway registry key for the registry tests (never the real Run key)
```

Paths below are inside `ptz_joystick/` unless they start with `tests/`.

The two ports are `typing.Protocol` classes, so an adapter only needs the right method; no base class. `mypy` checks that each adapter matches, where `app/registry.py` lists it. The Protocols' docstrings hold the full rules an adapter must follow:

- `Controller.read() -> ControllerState | None` in `controllers/__init__.py` (None = unplugged)
- `Camera.send(cmd: Command) -> bool` in `cameras/__init__.py` (True = camera took it)

The rules for commands are at the top of `core/commands.py`.
