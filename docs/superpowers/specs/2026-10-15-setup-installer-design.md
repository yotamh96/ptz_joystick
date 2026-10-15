# Setup installer: design

2026-10-15 · Design approved in chat, section by section. This file is the reference for the implementation plan.

## Goal

An operator on a fresh Draco PC goes from download to a green tray dot with one file: no terminal, no `setx`, no Notepad.

- CI builds `ptz_joystick_setup.exe` on every run and attaches it to each GitHub Release.
- The setup installs the tray and console exes, asks for the camera address, password and controller, and can turn on Start with Windows.
- Running a newer setup over an old install upgrades it and keeps the settings.
- The two loose exes stay on every Release, for a copy without installing.

## Decisions

| Topic | Decision |
|---|---|
| Tool | Inno Setup, version pinned in CI. One script split into small `.iss` files. |
| Rejected | WiX / MSI: a dual per-user / per-machine MSI is fiddly and its dialogs are long XML; only worth it if IT pushes it by Group Policy. Own installer in Python: we would hand-write the wizard, the uninstaller, the Add/Remove Programs entry and locked-file handling. |
| Install mode | The operator picks: Inno's built-in "Install for me only / for all users" dialog. |
| Folder | Asked on first install, with a default per mode. An upgrade reuses it. |
| Settings, per machine | `C:\ProgramData\ptz_joystick`, shared by every account on the PC. |
| Asked at install | Camera address, camera password, controller type, Start with Windows. |
| Release | `ptz_joystick_setup.exe` plus the two loose exes. |
| Updates | Unchanged: the update pop-up and log line point at the Release page; the operator downloads the setup there. |
| Silent install | `/HOST=` and `/CONTROLLER=` (`winmm` or `keyboard`) on the command line; left out, the template's defaults stay. No `/PASSWORD=`: every process on the PC can read a command line, so a silent install writes no password. |

## What goes where

| | Per user | Per machine |
|---|---|---|
| Exes (default folder) | `%LOCALAPPDATA%\Programs\ptz_joystick` | `C:\Program Files\ptz_joystick` |
| Settings + log | next to the exes | `C:\ProgramData\ptz_joystick`, all users may modify |
| Start menu, Add/Remove Programs | this account | every account |
| `PTZ_PASSWORD`, Start with Windows | the installing account (`HKCU`) | the installing account (`HKCU`) |

Start menu shortcuts: **ptz_joystick** (the tray exe) and **ptz_joystick (troubleshooting)** (the console exe).

`PTZ_PASSWORD` and the Run key live in `HKCU`, the same places `setx` and the tray's Start with Windows checkbox use. In a per-machine install where an admin types their own credentials at the UAC prompt, both land in the admin's account; the operator then sets them as today (`setx`, tray menu).

## Finding the settings: `config/template.py`

The one code change. `default_path()`, for a frozen exe, looks for `ptz_joystick.toml` in this order:

1. Next to the exe: use it. A per-user install puts it there.
2. `%PROGRAMDATA%\ptz_joystick\ptz_joystick.toml`: use it. A per-machine install puts it there, and nothing next to the exe.
3. Neither: next to the exe. The first run writes the template there, as today.

A source run (`python -m ptz_joystick`) is unchanged: next to README.md.

The rule looks at which files exist, not at the folder's name or write rights. The tray runs as admin and can write where the console exe can't, so a rule based on write rights would give the two exes different files. With this rule both exes always pick the same file, wherever the operator installed.

Side effect: loose exes copied to a PC that has a per-machine install, with no settings file next to them, use that PC's shared settings.

## The wizard

### First install

"First install" means: no settings file where the lookup above would find it for the chosen mode and folder (`<folder>\ptz_joystick.toml` per user, `C:\ProgramData\ptz_joystick\ptz_joystick.toml` per machine).

| Page | Content |
|---|---|
| Install for | Inno's built-in "me only / all users" dialog |
| Folder | Default `{autopf}\ptz_joystick`: `%LOCALAPPDATA%\Programs\ptz_joystick` per user, `C:\Program Files\ptz_joystick` per machine |
| Camera | Address, pre-filled `http://192.168.77.3`; must start with `http://` or `https://` and hold no spaces, quotes or backslashes |
| Password | Masked, required. Skipped when `PTZ_PASSWORD` is already set in `HKCU\Environment` |
| Controller | ◉ Game controller (`winmm`) ○ Keyboard (`keyboard`), with the note "keys only count while Zao Virtual Cabin is in front" |
| Options | ☐ Start with Windows, unticked |
| Finish | ☑ Start ptz_joystick now |

What setup writes:

- **Settings file**: the template from `config/template.py` (CI saves it into the setup at build time), with the `host` and `controller` lines replaced by the answers. UTF-8.
- **Password**: `HKCU\Environment\PTZ_PASSWORD`, a string value, with the environment-changed broadcast so new programs see it. Only when the page was filled in.
- **Start with Windows**: `HKCU\...\Run\ptz_joystick` = `"<folder>\ptz_joystick_tray.exe"`, exactly what `autostart.command_for()` writes, so the tray menu shows the box ticked.
- **Per machine**: creates `C:\ProgramData\ptz_joystick` with modify rights for all users.

"Start ptz_joystick now" starts the tray as the original user, not as the setup's admin, the same as a double-click.

### Upgrade

A settings file already exists (same mode and folder as before):

- Inno reuses the earlier mode and folder and skips those pages.
- Skips Camera, Controller and Options. The settings file and the Run key are never touched: operators change them with Open settings and the tray menu.
- Shows Password only when `PTZ_PASSWORD` is not set, as on a first install.
- Shows Finish, with "Start ptz_joystick now", as on a first install.

The same rules apply after an uninstall, because uninstall keeps the settings file.

### A copy still running

The exes are locked while running, and the tray runs as admin: a per-user setup can neither close it nor open its mutex. Setup opens `Local\ptz_joystick` itself and treats "access denied" as running too, then shows:

> ptz_joystick is running. Quit it from its tray icon (right-click → Quit), then click Retry.

Retry checks again; Cancel exits setup. Install, upgrade and uninstall all check. Quitting by hand keeps the camera stop that Quit does. In a silent install, setup fails with an exit code instead of asking.

### Uninstall

- Removes: both exes, the shortcuts, the uninstaller, and the Run value if it is exactly this install's command.
- Keeps: the settings file, the log and `PTZ_PASSWORD`. The last page names the folder that holds the settings.

## Repo layout

```
installer/
  setup.iss       [Setup], files, shortcuts, the ProgramData folder; includes the files below
  pages.iss       Camera and Controller pages, which pages to skip, writing the settings file and the password
  upgrade.iss     the "still running" check, Start with Windows, the Run value on uninstall
  sign.ps1        signs one file with the Draco certificate; used by the exe step and by Inno's SignTool hook
```

## CI: the `build` job

New steps after "Smoke test (tray)":

1. **Install Inno Setup** with Chocolatey, pinned to the newest Inno Setup 6 release when this is implemented (`choco install innosetup --version ...`), like the pinned `ruff` and `mypy`.
2. **Build the setup.** Write the settings template from `config/template.py` into the build folder, then `iscc installer\setup.iss` → `dist\ptz_joystick_setup.exe`. Version: the tag without its `v` on tag runs, `0.0.0` otherwise. `AppId` is a fixed GUID that never changes: upgrades find the old install through it.
3. **Sign.** The existing exe signing moves into `installer/sign.ps1` (same checks: throws if the signer isn't our certificate). The exe step calls it per exe; Inno's `SignTool` hook calls it for the setup and its uninstaller. No secret: no `SignTool`, unsigned with a warning; tag runs still fail without it.
4. **Smoke test (setup)**, silent, both modes, with `/HOST=http://10.0.0.9 /CONTROLLER=keyboard /LOG=<file>`:
   - Per user (`/CURRENTUSER`): both exes in `%LOCALAPPDATA%\Programs\ptz_joystick`; the toml next to them holds both values; the installed console exe stops at the password check, like the existing smoke test.
   - Per machine (`/ALLUSERS`; the runner is admin): exes in `C:\Program Files\ptz_joystick`, no toml there; the toml in `C:\ProgramData\ptz_joystick` holds both values; the installed console exe stops at the password check and its log lands in ProgramData, which proves the settings lookup end to end.
   - Silent uninstall of each: exes gone, toml kept.
   - On failure, print the setup log.
5. **Upload and release**: add `dist\ptz_joystick_setup.exe` to the artifact and to `gh release create`.

## Errors the operator can see

| When | What they see |
|---|---|
| ptz_joystick is running | The Retry / Cancel message above |
| Address empty or not `http(s)://…` | The page stays: "Enter the camera address, like http://192.168.77.3" |
| Password empty | The page stays: "Enter the camera password" |
| Folder not writable (per user, e.g. inside Program Files) | Inno's own "access denied" error |

## Testing

- **Python**: unit tests for `default_path()`: next to the exe wins; ProgramData when only it exists; next to the exe when neither exists; source run unchanged. `sys.frozen`, `sys.executable` and `PROGRAMDATA` patched, files in a temp folder.
- **Installer**: the CI smoke tests above. No unit tests for the Inno code.
- **Manual check list** in the PR, on a Draco PC: interactive install per user and per machine; the pages and their validation; Start ptz_joystick now; upgrade with the tray running (the Retry message, then success); the settings untouched after upgrade; uninstall (what's gone, what's kept); Start with Windows ticked in the tray menu after ticking it in setup.

## Docs

| Page | Change |
|---|---|
| README | Setup: "Download and run `ptz_joystick_setup.exe`" is the main path; Python and the loose exes come after. Updating: run the newer setup. |
| `docs/settings.md` | Where the settings file lives: the three-step lookup, and the per-machine folder |
| `docs/releases.md` | CI builds and signs the setup; the Inno Setup version pin |
| `docs/development.md` | The `installer/` folder in the layout; building the setup locally with `iscc` |

## To verify during implementation

- Opening `Local\ptz_joystick` from a non-admin setup while an admin tray holds it gives "access denied", not "not found". If it gives "not found", fall back to looking for `ptz_joystick_tray.exe` / `ptz_joystick.exe` in the process list.
- The pinned Inno Setup version installs through Chocolatey on `windows-latest`.
- Inno's `SignTool` hook runs `sign.ps1` with the signing secrets in its environment.

## Out of scope

- Downloading or installing updates automatically.
- An MSI or Group Policy deployment.
- Testing the camera from the setup: the tray does that at its first start.
- A desktop shortcut.
- Changing settings on upgrade: Open settings does that.
