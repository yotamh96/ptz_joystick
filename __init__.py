"""Game controller -> PTZ camera.

Run:   python -m ptz_joystick          (from the folder that contains ptz_joystick\\)
Test:  python -m unittest discover ptz_joystick\\tests
Needs: pip install requests,  setx PTZ_PASSWORD "..."

Layout (ports & adapters): mapping.py is the logic and touches no hardware.
controllers\\ and cameras\\ hold the adapters, app.py wires them together, config.py holds every setting.
"""
