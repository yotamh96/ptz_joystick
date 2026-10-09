# Settings

[← README](../README.md)

Settings live in `ptz_joystick.toml`: next to `ptz_joystick.exe`, or in the repo folder (next to README.md) when run with Python. If it's missing, the first run writes it with every setting, its default and a comment. Edit it, save, then restart (tray: right-click the dot → Restart).

To use a different file: `python -m ptz_joystick --config D:\cams\studio2.toml` (same flag for the exe).

A misspelled setting, a wrong type (`"24"` instead of `24`) or a `password` line stops startup with a message naming the file and the setting. The password only comes from `PTZ_PASSWORD`.

| Setting | Default | What it does |
|---|---|---|
| `camera` | `"ptzoptics"` | Camera type. Only `ptzoptics` for now (see [Adding a camera](extending.md#adding-a-camera-eg-visca-over-ip)) |
| `host` | `"http://192.168.77.3"` | Camera address |
| `user` | `"admin"` | Camera user. The password always comes from `PTZ_PASSWORD` |
| `timeout` | `1.0` | Seconds to wait for each camera request. Max `2`, so the final stop always fits the 3 s shutdown window |
| `controller` | `"winmm"` | Controller type: `winmm` (any controller `joy.cpl` shows) or `keyboard`. `--keyboard` on the command line does the same as `"keyboard"` here |
| `pan_axis` / `tilt_axis` / `zoom_axis` | `X` / `Y` / `R` | Which controller axis does what (`X Y Z R U V`) |
| `invert_tilt` / `invert_zoom` | `true` | Flip direction if up/down feels backwards |
| `deadzone` | `0.15` | Stick readings at or below this are ignored |
| `full_speed_at` | `0.7` | Stick reading that gives top speed. The current pad tops out at about 0.75, not 1.0 |
| `pan_max` / `tilt_max` / `zoom_max` | `24` / `20` / `7` | Camera's top speeds. Lower them for slower moves. Each camera type has its own ceiling, and startup names it if you go over. For PTZOptics, the defaults are the ceiling |
| `[buttons]` | `0 = "preset 1"` … `3 = "preset 4"` | Button index → `preset N` or `tracking` (toggles auto-tracking, PTZOptics Move SE / Move 4K only). Index 0 is "button 1" in `joy.cpl` |
| `save_hold_seconds` | `2.0` | Hold a preset button this long to save the current view there. `0` turns saving off, and presets then fire on press instead of on release |
| `debug` | `false` | `true` logs every stick reading and every command sent |
| `log_file` | `"ptz_joystick.log"` | Log file, appended next to `ptz_joystick.toml` (so next to the exe). A full path goes there instead: `log_file = 'D:\logs\ptz.log'` (single quotes, so the backslashes stay as typed). `""` = terminal only (the tray version then keeps no log) |
| `check_updates` | `true` | At startup, log a line if a newer release is on GitHub. Set `false` on PCs without internet. Running from Python source never checks |
