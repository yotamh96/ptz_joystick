# Logs and troubleshooting

[← README](../README.md)

## Logs

Every line has a timestamp and goes to `ptz_joystick.log` next to the settings file, and to the terminal when there is one (the console version):

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

To see what happened during a session, check the file afterwards. Set `debug = true` for the full detail.

## Troubleshooting

| Symptom | Fix |
|---|---|
| No tray dot | Windows 11 hides it behind **^** on the taskbar. Settings → Personalization → Taskbar → Other system tray icons → turn on ptz_joystick_tray |
| Tray dot red | Hover over it, or **Open log**: the message names the fix (see the rows below). Fix it, then **Restart** |
| Tray dot yellow, `Waiting for the camera at ...` | The camera hasn't answered yet. Once it says why, the hover text shows that instead: see `The camera refused the login` and `Can't reach the camera` below. It tries again every 5 s |
| `Move the left stick to start` (tray dot yellow, or the console stuck there) | Move the stick fully. The tool picks the first controller whose stick moves more than 0.3 |
| Console window shows `Press Enter to close.` | The console exe stopped on one of the messages below; it waits so you can read it. Fix it, press Enter, run it again |
| `Another ptz_joystick is already running` | Another copy runs: a tray dot (look behind **^**) or a console window. Quit it first |
| Keyboard controller: keys do nothing | Keys only count while Zao Virtual Cabin is in front. Click its window first |
| `Not running as administrator` | Zao runs as admin, so its keys only reach an admin. Tray: start it again and answer **Yes** to the UAC prompt. Console: open the terminal with **Run as administrator** |
| `The camera password is not set` | Type it in **Settings…** (tray), or run `setx PTZ_PASSWORD "..."` in a terminal, then run ptz_joystick again (console, any terminal) or click **Restart** (tray) |
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
| Changed a setting, nothing happened | Answer **Yes** to "Restart now?" after Save in Settings…, or click **Restart**. After editing in Notepad: check the `Settings:` line at startup, it shows which file was read |
| `Can't write the log file` | Another program has the log open, or the folder is read-only. The tool keeps running and logs to the terminal only (the tray version then has no log) |
| `Wrong text encoding in ptz_joystick.toml` | The file was saved in an old encoding (for example ANSI with Hebrew text). In Notepad: File → Save as → Encoding: UTF-8 |
| `Unexpected error in ptz_joystick` | Something failed that the tool doesn't expect. The log has the details (a traceback). Restart; if it comes back, send the log to whoever maintains the tool |
