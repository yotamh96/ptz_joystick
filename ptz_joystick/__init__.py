"""Game controller -> PTZ camera.

Run:   python -m ptz_joystick          (from the repo folder, the one with README.md)
Test:  python -m unittest discover tests
Needs: pip install -r requirements.txt,  setx PTZ_PASSWORD "..."

Layout (ports & adapters): mapping.py is the logic and touches no hardware.
controllers\\ and cameras\\ hold the adapters, app.py wires them together, config.py holds every setting (ptz_joystick.toml overrides them).
"""
