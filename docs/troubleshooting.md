# Logs and troubleshooting

[← README](../README.md)

## Logs

Every line has a timestamp and goes to the terminal and to `ptz_joystick.log` next to the settings file:

```
14:02:10 INFO    ptz_joystick v0.3.0
14:02:11 INFO    Using joystick ID 0
14:02:11 INFO    Driving camera http://192.168.77.3. Ctrl+C to quit.
14:05:40 WARNING Controller lost, camera stopped. Waiting for it...
14:05:43 INFO    Controller back.
14:07:02 WARNING camera unreachable: ...
14:07:30 INFO    camera back (was: unreachable)
```

A camera outage logs one warning when it starts and one line when the camera is back, not one line per retry.
While the camera is down, stick moves keep retrying. A button action (like a preset recall) the camera refuses 3 times is dropped, so it can't fire minutes later.

To see what happened during a session, check the file afterwards. Set `debug = true` for the full detail.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Set the camera password first` | Run `setx PTZ_PASSWORD "..."`, then **open a new terminal** |
| `No controller found` | Open `joy.cpl` (Win+R). If the controller isn't listed or its crosshair doesn't move there, it's a cable, receiver or driver problem, not this tool |
| Stuck at `Move the left stick now...` | Move the stick fully. The tool picks the first controller whose stick moves more than 0.3 |
| `Controller has no axis [...]` | Set `debug = true`, run, move each stick, and see which letter changes. Put those letters in `pan_axis` / `tilt_axis` / `zoom_axis` |
| Camera never reaches full speed | Set `debug = true` and push the stick to its edge. Set `full_speed_at` a little below the highest value you see |
| Full speed comes too early in the push | Raise `full_speed_at` (max `1.0`) |
| Up/down is backwards | Toggle `invert_tilt` or `invert_zoom` |
| `Camera at ... did not accept a stop command` | Startup check failed. The line above it gives the reason |
| `camera rejected the login (401)` | Wrong `user` or `PTZ_PASSWORD` |
| `camera unreachable` | Check `host`, the network, and that the camera's web page opens in a browser |
| `...ptz_joystick.toml: ...` | A setting is misspelled or has an invalid value. The message names it and the allowed range |
| Changed a setting, nothing happened | Check the `Settings:` line at startup: it shows which file was read. Restart after saving |
| `Can't write log file` | Another program has the log open, or the folder is read-only. The tool keeps running and logs to the terminal only |
| `...ptz_joystick.toml: can't read it as text` | The file was saved in an old encoding (for example ANSI with Hebrew text). In Notepad: File → Save as → Encoding: UTF-8 |
