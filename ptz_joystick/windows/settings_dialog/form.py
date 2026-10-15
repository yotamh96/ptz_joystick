"""The settings dialog's fields, without Tk: each setting's tab and label, Settings ↔ the text in the fields, and
which field an error is about. tabs.py builds the widgets from FIELDS."""
import re
from collections.abc import Callable
from dataclasses import dataclass, fields
from typing import Any, cast

from ... import config
from ...config import BUTTON_COMMANDS, MAX_TIMEOUT, Settings, takes_number

TABS = ("Camera", "Controller", "Buttons", "Other")
NOTHING = "nothing"                 # a button row that fires nothing: left out of [buttons]
ACTIONS = [NOTHING, *BUTTON_COMMANDS]
MIN_ROWS = 12                       # button rows shown even when the file maps fewer


@dataclass(frozen=True)
class Field:
    setting: str                    # a Settings field
    tab: str
    label: str
    hint: str = ""                  # grey text at the right


FIELDS = [                          # every Settings field, in the order the tabs show them
    Field("camera", "Camera", "Camera type"),
    Field("host", "Camera", "Address"),
    Field("user", "Camera", "User"),
    Field("password", "Camera", "Password", "saved for this Windows user"),
    Field("timeout", "Camera", "Timeout (seconds)", f"max {MAX_TIMEOUT:g}"),
    Field("pan_max", "Camera", "Top speed: pan"),           # hint: the camera's ceiling, added by tabs.py
    Field("tilt_max", "Camera", "Top speed: tilt"),
    Field("zoom_max", "Camera", "Top speed: zoom"),
    Field("controller", "Controller", "Controller", "winmm = any controller joy.cpl shows"),
    Field("pan_axis", "Controller", "Pan axis", "joystick only"),
    Field("tilt_axis", "Controller", "Tilt axis"),
    Field("zoom_axis", "Controller", "Zoom axis"),
    Field("invert_tilt", "Controller", "Invert tilt"),
    Field("invert_zoom", "Controller", "Invert zoom"),
    Field("deadzone", "Controller", "Deadzone", "readings at or below are ignored"),
    Field("full_speed_at", "Controller", "Full speed at", "reading that gives top speed"),
    Field("buttons", "Buttons", "Buttons"),
    Field("save_hold_seconds", "Buttons", "Hold to save (s)", "0 = saving off"),
    Field("log_file", "Other", "Log file", "empty = no log"),
    Field("check_updates", "Other", "Check for updates"),
    Field("debug", "Other", "Debug log", "every reading and command"),
]
TYPES = {f.name: cast(type, f.type) for f in fields(Settings)}
NAMED = re.compile(r"\b(" + "|".join(f.setting for f in FIELDS) + r")\b")


class FieldError(Exception):
    """A value Save can't take. setting: the field to mark; row: the button row, for a button."""

    def __init__(self, setting: str, message: str, row: int | None = None):
        super().__init__(message)
        self.setting, self.message, self.row = setting, message, row


def numbered(action: str) -> bool:
    """Whether a button action takes a preset number ("preset 3"), so its number box is on."""
    return action != NOTHING and takes_number(action)


def to_fields(s: Settings) -> dict[str, Any]:
    """What each field shows: text for entries and dropdowns, True/False for checkboxes, the password from
    s.password, and the button rows as (action, number) pairs, numbered from 0."""
    values: dict[str, Any] = {f.setting: getattr(s, f.setting) if TYPES[f.setting] is bool
                              else str(getattr(s, f.setting)) for f in FIELDS if f.setting != "buttons"}
    count = max(MIN_ROWS, max(s.buttons, default=-1) + 1)
    values["buttons"] = [_row(s.buttons.get(i)) for i in range(count)]
    return values


def from_fields(values: dict[str, Any], type_error: Callable[[Settings], str | None]) -> Settings:
    """The fields as Settings, password included, checked as startup checks them. Raises FieldError for the first
    value that's wrong."""
    if not values["password"]:
        raise FieldError("password", "The camera password is not set")
    table: dict[str, Any] = {f.setting: _typed(f.setting, values[f.setting]) for f in FIELDS
                             if f.setting not in ("password", "buttons")}
    table["buttons"] = _buttons(values["buttons"])
    try:
        s = config.from_dict(table, values["password"])
    except ValueError as e:
        raise FieldError(_named_in(str(e)), str(e)) from None
    if message := type_error(s):
        raise FieldError(_named_in(message), message)
    return s


def _row(cmd) -> tuple[str, str]:
    if cmd is None:
        return NOTHING, ""
    action, _, number = config.command_text(cmd).partition(" ")
    return action, number


def _typed(setting: str, value: Any) -> Any:
    """An entry's text without spaces around it (a pasted address often has one), as its setting's number type.
    Text that isn't a number stays text, so from_dict says so in its own words ("deadzone must be a number, got
    '0,15'"). The password never comes here: it's kept as typed."""
    if not isinstance(value, str):
        return value
    want, value = TYPES[setting], value.strip()
    if want in (int, float):
        try:
            return want(value)
        except ValueError:
            pass
    return value


def _buttons(rows: list[tuple[str, str]]) -> dict[str, str]:
    """The button rows as the file's [buttons] table, {"0": "preset 1", ...}, each checked here so an error names
    its row."""
    table = {}
    for i, (action, number) in enumerate(rows):
        if action == NOTHING:
            continue
        text = f"{action} {number.strip()}" if numbered(action) else action
        try:
            config.parse_command(text)
        except ValueError as e:
            raise FieldError("buttons", f"button {i + 1}: {e}", row=i) from None
        table[str(i)] = text
    return table


def _named_in(message: str) -> str:
    """The field an error is about: the first setting its message names. "need 0 <= deadzone < full_speed_at"
    names two: the first is marked."""
    m = NAMED.search(message)
    return m[1] if m else FIELDS[0].setting
