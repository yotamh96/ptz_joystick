"""Game controller -> PTZ camera.

Run:   python -m ptz_joystick          (from the repo folder, the one with README.md)
Test:  python -m unittest discover -s tests -t .
Needs: pip install -r requirements.txt,  setx PTZ_PASSWORD "..."

Layout (ports & adapters): core\\ is the logic and touches no hardware. cameras\\ and controllers\\ hold the
adapters, app\\ runs the program (app\\main.py wires everything), config\\ holds every setting (ptz_joystick.toml
overrides them).
"""
