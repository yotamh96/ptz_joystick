# ptz_joystick

Drive a PTZOptics camera with a USB game controller. Windows only.

The controller is read through the Windows joystick API (the same data `joy.cpl` shows). Commands go to the camera over HTTP-CGI with Digest auth.

## Setup

Needs Python 3.10+ (developed on 3.14).

```powershell
pip install -r ptz_joystick\requirements.txt
setx PTZ_PASSWORD "your-camera-password"
```

`setx` only applies to new terminals, so open a new one after running it.

## Run

From the folder that **contains** `ptz_joystick\` (for example, `Desktop`):

```powershell
python -m ptz_joystick
```

1. It lists the joystick IDs it found and asks you to move the left stick. It uses the controller that moves.
2. It drives the camera until you press **Ctrl+C**. Ctrl+C always sends a stop to the camera before exiting.

## Controls

| Input | Camera |
|---|---|
| Left stick | Pan / tilt. Speed grows with how far you push |
| Right stick up / down | Zoom in / out |
| Buttons 1–4 | Recall presets 1–4 |
| Controller unplugged | Camera stops. Plug it back in to carry on |

## Settings

All settings are in [`config.py`](config.py). Edit the default values there.

| Setting | Default | What it does |
|---|---|---|
| `host` | `http://192.168.77.3` | Camera address |
| `user` | `admin` | Camera user. The password always comes from `PTZ_PASSWORD` |
| `timeout` | `1.0` | Seconds to wait for each camera request |
| `pan_axis` / `tilt_axis` / `zoom_axis` | `X` / `Y` / `R` | Which controller axis does what (`X Y Z R U V`) |
| `invert_tilt` / `invert_zoom` | `True` | Flip direction if up/down feels backwards |
| `deadzone` | `0.15` | Stick readings at or below this are ignored |
| `full_speed_at` | `0.7` | Stick reading that gives top speed. The current pad tops out at about 0.75, not 1.0 |
| `pan_max` / `tilt_max` / `zoom_max` | `24` / `20` / `7` | Camera's top speeds |
| `buttons` | `{0: Preset(1), …}` | Button index → command. Index 0 is "button 1" in `joy.cpl` |
| `debug` | `False` | `True` logs every stick reading and every command sent |
| `log_file` | `ptz_joystick.log` | Log file, appended in the folder you run from. `""` = terminal only |

## Logs

Every line has a timestamp and goes to the terminal and to `ptz_joystick.log`:

```
14:02:11 INFO    Using joystick ID 0
14:02:11 INFO    Driving camera http://192.168.77.3. Ctrl+C to quit.
14:05:40 WARNING Controller lost, camera stopped. Waiting for it...
14:05:43 INFO    Controller back.
14:07:02 WARNING camera unreachable: ...
```

To see what happened during a session, check the file afterwards. Set `debug=True` for the full detail.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Set the camera password first` | Run `setx PTZ_PASSWORD "..."`, then **open a new terminal** |
| `No controller found` | Open `joy.cpl` (Win+R). If the controller isn't listed or its crosshair doesn't move there, it's a cable, receiver or driver problem, not this tool |
| Stuck at `Move the left stick now...` | Move the stick fully. The tool picks the first controller whose stick moves more than 0.3 |
| `Controller has no axis [...]` | Set `debug=True`, run, move each stick, and see which letter changes. Put those letters in `pan_axis` / `tilt_axis` / `zoom_axis` |
| Camera never reaches full speed | Set `debug=True` and push the stick to its edge. Set `full_speed_at` a little below the highest value you see |
| Full speed comes too early in the push | Raise `full_speed_at` (max `1.0`) |
| Up/down is backwards | Toggle `invert_tilt` or `invert_zoom` |
| `camera answered 401` | Wrong `user` or `PTZ_PASSWORD` |
| `camera unreachable` | Check `host`, the network, and that the camera's web page opens in a browser |

## Tests

```powershell
python -m unittest discover ptz_joystick\tests
```

These need no camera and no controller. Fakes stand in for both.

## How it's built

Ports and adapters. The logic never touches hardware, so you can change it and test it without a camera.

```
__main__.py        python -m ptz_joystick → app.main()
app.py             composition root: builds the real adapters, runs the loop, logging setup
config.py          Settings (every knob above)
commands.py        PanTilt, Zoom, Preset: camera-agnostic, signed speeds, 0 = stop
mapping.py         pure logic: stick → commands (deadzone, scaling, ignores small stick jitter, button presses)
sender.py          background thread: latest command per type wins, retries until the camera accepts
controllers/       Controller port (__init__.py) + winmm.py adapter
cameras/           Camera port (__init__.py) + ptzoptics.py adapter
tests/             unit tests with fake controller / camera
```

The two ports are `typing.Protocol` classes, so an adapter only needs the right method; no base class:

- `Controller.read() -> ControllerState | None` (None = unplugged)
- `Camera.send(cmd: Command) -> bool` (True = camera accepted)

## Extending

| Change | Where |
|---|---|
| New camera brand (e.g. VISCA over IP) | Add `cameras/<name>.py` with a `send(cmd) -> bool`, then change the one `PtzOpticsCamera(...)` line in `app.py` |
| New controller type (XInput, pygame) | Add `controllers/<name>.py` with a `read()`, then change the `discover()` line in `app.py` |
| New button action (home, focus, …) | 1. Add a dataclass in `commands.py` and add it to the `Command` union<br>2. Map a button to it in `config.py`<br>3. Add a `case` for it in `cameras/ptzoptics.py` `to_query()` |
| Speed curve / deadzone behaviour | `mapping.py` only, covered by `tests/test_mapping.py` |

If a camera adapter gets a command it can't handle, it raises. The sender logs the error, drops that command and keeps running, so stop commands still reach the camera.
