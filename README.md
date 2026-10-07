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

**No Python?** Download `ptz_joystick.exe` from the latest GitHub Release, run the `setx` line, then run the exe from a new terminal. The exe carries the `config.py` settings it was built with. To change a setting, edit `config.py` and make a new release (see [Releases](#releases)).

## Run

From the folder that **contains** `ptz_joystick\` (for example, `Desktop`):

```powershell
python -m ptz_joystick
```

1. It sends the camera a stop command to check the address and password. If the camera doesn't accept it, the tool exits with the reason.
2. It lists the joystick IDs it found and asks you to move the left stick. It uses the controller that moves.
3. It drives the camera until you press **Ctrl+C** or close the window. Both send a stop to the camera before exiting.

## Controls

| Input | Camera |
|---|---|
| Left stick | Pan / tilt. Speed grows with how far you push |
| Right stick up / down | Zoom in / out |
| Buttons 1–4 | Recall presets 1–4 |
| Controller unplugged | Camera stops. Plug it back in to carry on |
| Ctrl+C, closing the window, logoff, shutdown | Camera stops |
| Crash | Camera stops. The reason and traceback go to the log file |

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
14:07:30 INFO    camera back (was: unreachable)
```

A camera outage logs one warning when it starts and one line when the camera is back, not one line per retry.
While the camera is down, moves keep retrying. A preset the camera refuses 3 times is dropped, so it can't fire minutes later.

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
| `Camera at ... did not accept a stop command` | Startup check failed. The line above it gives the reason |
| `camera rejected the login (401)` | Wrong `user` or `PTZ_PASSWORD` |
| `camera unreachable` | Check `host`, the network, and that the camera's web page opens in a browser |
| `config.py: ...` | A setting has an invalid value. The message names it and the allowed range |
| `Can't write log file` | Another program has the log open, or the folder is read-only. The tool keeps running and logs to the terminal only |

## Tests

```powershell
python -m unittest discover ptz_joystick\tests
```

These need no camera and no controller. Fakes stand in for both.

Lint (CI runs the same check):

```powershell
pip install ruff==0.16.10
ruff check ptz_joystick
```

## Releases

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs on every push and PR:

1. `lint`: `ruff check`
2. `test`: the unit tests on Python 3.10 and 3.14, on Windows
3. `build`: PyInstaller → `ptz_joystick.exe`, signed, smoke-tested (it must reach the password check). Download it from the run's **Artifacts**.

To publish a release:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

The tag's run attaches the signed `ptz_joystick.exe` to a GitHub Release named after the tag.

### Signing certificate (one-time setup)

The exe is signed with a self-signed certificate, so only Draco PCs trust it. IT pushes the certificate to them through Group Policy. On any other PC it behaves like an unsigned exe.

On your PC, in PowerShell:

```powershell
$c = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=Draco ptz_joystick" -CertStoreLocation Cert:\CurrentUser\My -NotAfter (Get-Date).AddYears(5)
$pw = Read-Host -AsSecureString "PFX password"
Export-PfxCertificate -Cert $c -FilePath ptz-signing.pfx -Password $pw
[Convert]::ToBase64String([IO.File]::ReadAllBytes("$PWD\ptz-signing.pfx")) | Set-Clipboard
Export-Certificate -Cert $c -FilePath draco-ptz.cer
```

1. GitHub repo → Settings → Secrets and variables → Actions → add `SIGNING_PFX` (paste the clipboard) and `SIGNING_PFX_PASSWORD`.
2. Delete `ptz-signing.pfx`. GitHub now holds the only copy of the exported key you need.
3. Send `draco-ptz.cer` (public part only) to IT. Ask them to deploy it with Group Policy to **Trusted Root Certification Authorities** and **Trusted Publishers**.
4. Check on a Draco PC: `Get-AuthenticodeSignature ptz_joystick.exe` should say `Valid`.

Without the secrets, pushes still build an unsigned exe and show a warning. Tag runs fail, so an unsigned exe is never released.

SmartScreen judges downloaded files by reputation, so a browser download may still show "More info → Run anyway" once. Copying the exe from a network share, or running `Unblock-File ptz_joystick.exe`, avoids that.

## How it's built

Ports and adapters. The logic never touches hardware, so you can change it and test it without a camera.

```
__main__.py        python -m ptz_joystick → app.main()
app.py             composition root: builds the real adapters, runs the loop, logging setup
config.py          Settings (every knob above)
commands.py        PanTilt, Zoom, Preset: camera-agnostic, signed speeds, 0 = stop
mapping.py         pure logic: stick → commands (deadzone, scaling, ignores small stick jitter, button presses)
sender.py          background thread: latest command per type wins, retries until the camera accepts
winconsole.py      Windows console close / logoff / shutdown → stop the camera
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
