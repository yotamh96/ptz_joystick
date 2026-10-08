# ptz_joystick

Drive a PTZOptics camera with a USB game controller. Windows only.

The controller is read through the Windows joystick API (the same data `joy.cpl` shows). Commands go to the camera over HTTP-CGI with Digest auth.

## Setup

Needs Python 3.11+ (developed on 3.14). From the repo folder (the one with this README):

```powershell
pip install -r requirements.txt
setx PTZ_PASSWORD "your-camera-password"
```

`setx` only applies to new terminals, so open a new one after running it.

**No Python?** Download `ptz_joystick.exe` from the latest GitHub Release, run the `setx` line, then run the exe from a new terminal. The first run creates `ptz_joystick.toml` next to the exe. Edit it to change settings ([every setting](docs/settings.md)); no rebuild needed.

### Updating

At startup the exe checks GitHub and logs a line when a newer release exists:

```
14:02:10 INFO    Update available: v0.4.0 (you have v0.3.0) https://github.com/yotamh96/ptz_joystick/releases/tag/v0.4.0
```

It never downloads or replaces anything itself. To update, close the tool, download the new `ptz_joystick.exe` from that page, and put it over the old one. `ptz_joystick.toml` sits next to it, so your settings stay. `ptz_joystick.exe --version` shows the version you have. Exes before v0.3.0 don't check.

## Run

From the repo folder:

```powershell
python -m ptz_joystick
```

1. It sends the camera a stop command to check the address and password. If the camera doesn't accept it, the tool exits with the reason.
2. It lists the joystick IDs it found and asks you to move the left stick. It uses the controller that moves.
3. It drives the camera until you press **Ctrl+C** or close the window. Both send a stop to the camera before exiting.

**No controller at hand?** `python -m ptz_joystick --keyboard` (same flag for the exe, or `controller = "keyboard"` in the settings) skips step 2 and drives with the keyboard: arrows = left stick, **W / S** = zoom in / out, keys **1–4** = buttons 1–4 (tap = go to preset, hold 2 s = save it). Each key is a full push, so moves run at top speed; lower `pan_max` / `tilt_max` / `zoom_max` for gentler moves. Keys only count while the tool's window (console, Windows Terminal or VS Code) is in front. Click another window and the camera stops.

## Controls

| Input | Camera |
|---|---|
| Left stick | Pan / tilt. Speed grows with how far you push |
| Right stick up / down | Zoom in / out |
| Tap buttons 1–4 | Go to presets 1–4 (fires when you let go) |
| Hold button 1–4 for 2 s | Save the current view as that preset. The log says `Saving the current position as preset N.` |
| Controller unplugged | Camera stops. Plug it back in to carry on |
| Ctrl+C, closing the window, logoff, shutdown | Camera stops |
| Crash | Camera stops. The reason and traceback go to the log file |

## More

| Page | What's in it |
|---|---|
| [Settings](docs/settings.md) | Every setting in `ptz_joystick.toml`, its default and what it does |
| [Logs and troubleshooting](docs/troubleshooting.md) | What the log lines mean, and error message → fix |
| [Development](docs/development.md) | Running the tests and lint, how the code is laid out |
| [Extending](docs/extending.md) | Adding a camera, a controller or a button action |
| [Releases](docs/releases.md) | Publishing a version, the signing certificate |
