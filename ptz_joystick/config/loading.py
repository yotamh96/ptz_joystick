"""Reading ptz_joystick.toml into Settings: type checks, button commands, encodings, clean error messages."""
import os
import tomllib
from dataclasses import fields, replace
from pathlib import Path
from typing import Any, cast

from ..core.commands import Command
from ..core.problem import Problem
from .settings import BUTTON_COMMANDS, Settings, takes_number


def parse_command(text) -> Command:
    """'preset 1' -> Preset(1)."""
    words = text.split() if isinstance(text, str) else []
    entry = BUTTON_COMMANDS.get(words[0].lower()) if words else None
    if entry is not None and all(w.isdecimal() for w in words[1:]):   # whole numbers, 0 or more ("-1" fails)
        try:
            return entry[0](*map(int, words[1:]))
        except TypeError:                       # wrong number of values
            pass
    usage = ", ".join(how for _, how in BUTTON_COMMANDS.values())
    raise ValueError(f"bad command {text!r}, use one of: {usage}")


def command_text(cmd: Command) -> str:
    """Preset(3) -> "preset 3": the reverse of parse_command, for writing the settings file."""
    for name, (make, _) in BUTTON_COMMANDS.items():
        args = [getattr(cmd, f.name) for f in fields(cmd)] if takes_number(name) else []
        if make(*args) == cmd:
            return " ".join([name, *map(str, args)])
    raise ValueError(f"no button action makes {cmd!r}")


def parse_buttons(table: dict) -> dict:
    if bad := [b for b in table if not b.isdecimal()]:
        raise ValueError(f"buttons: index must be a number 0-31, got {bad}")
    try:
        return {int(b): parse_command(c) for b, c in table.items()}
    except ValueError as e:
        raise ValueError(f"buttons: {e}") from None


TYPE_NAMES = {str: "text in quotes", int: "a whole number", float: "a number", bool: "true or false", dict: "a [table]"}


def has_type(v, want: type) -> bool:
    """isinstance, except true/false is not a number, and a whole number is fine where a float is wanted."""
    return isinstance(v, bool) == (want is bool) and isinstance(v, (int, float) if want is float else want)


def from_dict(d: dict, password: str) -> Settings:
    known = {f.name: cast(type, f.type) for f in fields(Settings) if f.name != "password"}   # classes, not strings
    values: dict[str, Any] = {"password": password}     # each value checked below, then by Settings itself
    for key, v in d.items():
        if key == "password":
            raise ValueError('remove password, set it with setx PTZ_PASSWORD "..." instead')
        if key not in known:
            raise ValueError(f"unknown setting {key!r}")
        if not has_type(v, known[key]):
            raise ValueError(f"{key} must be {TYPE_NAMES[known[key]]}, got {v!r}")
        values[key] = parse_buttons(v) if key == "buttons" else v
    return Settings(**values)


def bad_setting(path: Path, message: object) -> Problem:
    """The one wording for any wrong setting. message: what's wrong with it, e.g. "unknown setting 'hots'"."""
    return Problem(f"Bad setting in {path.name}: {message}", fix="Fix it and save", detail=str(path))


def read_text(path: Path) -> str:
    """The settings file as text, in any encoding Notepad saves: UTF-8 (with or without BOM) or "Unicode"."""
    raw = path.read_bytes()
    encoding = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    try:
        return raw.decode(encoding)
    except UnicodeDecodeError:
        raise Problem(f"Wrong text encoding in {path.name}", fix="In Notepad: File > Save as > Encoding: UTF-8",
                      detail=str(path)) from None


def read(path: Path) -> Settings:
    """The settings in path as written: password "", log_file as typed. Raises Problem like load()."""
    try:
        return from_dict(tomllib.loads(read_text(path)), "")
    except (tomllib.TOMLDecodeError, ValueError) as e:
        raise bad_setting(path, e) from None
    except OSError as e:
        raise Problem(f"Can't read {path.name}", fix="Check that you can open it in Notepad", detail=str(e)) from None


def load(path: Path) -> Settings:
    password = os.environ.get("PTZ_PASSWORD")
    if not password:
        raise Problem("The camera password is not set", fix='Run setx PTZ_PASSWORD "..." in a terminal')
    s = replace(read(path), password=password)
    # A relative log file sits next to the settings file (and so the exe), whatever folder you run from.
    return replace(s, log_file=str(path.parent / s.log_file)) if s.log_file else s
