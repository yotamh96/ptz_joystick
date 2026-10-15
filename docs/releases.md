# Releases

[← README](../README.md)

CI ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) runs on every push and PR:

1. `lint`: `ruff check` and `mypy`
2. `test`: the unit tests on Python 3.11 and 3.14, on Windows
3. `build`: PyInstaller → `ptz_joystick.exe` (console) and `ptz_joystick_tray.exe` (tray, no console window), both signed and smoke-tested. The console exe must write `ptz_joystick.toml` next to itself and reach the password check; the tray exe must log the password check to `ptz_joystick.log` next to itself. Download them from the run's **Artifacts**.

To publish a release:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

The tag's run attaches both signed exes to a GitHub Release named after the tag. The tag is baked into the exe as its version (`ptz_joystick/app/version.py`), which is what the update check compares. Tags must look like `v1.2.3`, or the check ignores them.

## Signing certificate (one-time setup)

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
