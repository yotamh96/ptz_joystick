import os
import sys
import tempfile
import tomllib
import unittest
from dataclasses import fields
from pathlib import Path
from typing import Any
from unittest import mock

from ptz_joystick import config
from ptz_joystick.config import Settings
from ptz_joystick.core.commands import PanTilt, Preset


class ValidationTest(unittest.TestCase):
    def test_defaults_are_valid(self):
        Settings()

    def test_bad_values_named_in_error(self):
        cases: list[tuple[dict[str, Any], str]] = [
            ({"full_speed_at": 0.15}, "full_speed_at"),      # == deadzone: would divide by zero
            ({"deadzone": 0.8}, "deadzone"),                 # above full_speed_at
            ({"full_speed_at": 1.2}, "full_speed_at"),
            ({"pan_axis": "x"}, "pan_axis"),
            ({"zoom_axis": "W"}, "zoom_axis"),
            ({"tilt_max": 0}, "tilt_max"),
            ({"zoom_max": 2.5}, "zoom_max"),                 # each camera's own top: app.main.check_types
            ({"timeout": 0}, "timeout"),
            ({"timeout": 2.5}, "timeout"),                   # would eat the 3 s shutdown window
            ({"timeout": float("inf")}, "timeout"),
            ({"save_hold_seconds": -1}, "save_hold_seconds"),
            ({"save_hold_seconds": 11}, "save_hold_seconds"),
            ({"host": "192.168.77.3"}, "host"),              # missing http://
            ({"buttons": {0: 1}}, "buttons"),                # not a command
            ({"buttons": {0: PanTilt(1, 0)}}, "buttons"),    # a button-started move would never stop
        ]
        for bad, word in cases:
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, word):
                Settings(**bad)


class TemplateTest(unittest.TestCase):
    def test_template_matches_defaults(self):
        self.assertEqual(config.from_dict(tomllib.loads(config.TEMPLATE), "x"), Settings(password="x"))

    def test_template_lists_every_setting(self):
        self.assertEqual(set(tomllib.loads(config.TEMPLATE)), {f.name for f in fields(Settings)} - {"password"})

    def test_written_once_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / config.FILE_NAME
            self.assertTrue(config.write_template_if_missing(path))
            path.write_text('host = "http://10.0.0.1"', encoding="utf-8")
            self.assertFalse(config.write_template_if_missing(path))
            self.assertEqual(path.read_text(encoding="utf-8"), 'host = "http://10.0.0.1"')


class DefaultPathTest(unittest.TestCase):
    def test_source_run_uses_repo_folder(self):
        repo = Path(__file__).resolve().parent.parent      # tests/ sits in the repo folder
        self.assertTrue((repo / "README.md").exists())
        self.assertEqual(config.default_path(), repo / config.FILE_NAME)

    def test_exe_uses_its_own_folder(self):
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "executable", r"C:\tools\ptz_joystick.exe"):
            self.assertEqual(config.default_path(), Path(r"C:\tools") / config.FILE_NAME)


class LoadTest(unittest.TestCase):
    def load(self, text):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"PTZ_PASSWORD": "pw"}):
            path = Path(d) / config.FILE_NAME
            path.write_text(text, encoding="utf-8")
            return config.load(path)

    def test_file_overrides_defaults_password_from_env(self):
        s = self.load('host = "http://10.0.0.1"\ntimeout = 2\n[buttons]\n5 = "Preset 9"\n')
        self.assertEqual((s.host, s.timeout, s.password, s.buttons), ("http://10.0.0.1", 2, "pw", {5: Preset(9)}))
        self.assertEqual(s.pan_max, Settings().pan_max)

    def test_relative_log_file_sits_next_to_settings_file(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"PTZ_PASSWORD": "pw"}):
            path = Path(d) / config.FILE_NAME
            for text, want in [
                ("", str(Path(d) / "ptz_joystick.log")),                 # default
                ("log_file = 'logs\\ptz.log'", str(Path(d) / "logs" / "ptz.log")),
                ("log_file = 'C:\\elsewhere\\ptz.log'", "C:\\elsewhere\\ptz.log"),   # full path kept
                ('log_file = ""', ""),                                   # terminal only
            ]:
                path.write_text(text, encoding="utf-8")
                with self.subTest(text=text):
                    self.assertEqual(config.load(path).log_file, want)

    def test_bad_file_is_clean_exit_naming_file_and_key(self):
        for text, word in [
            ('hots = "x"', "unknown setting 'hots'"),
            ('password = "x"', "PTZ_PASSWORD"),
            ('pan_max = "24"', "pan_max must be a whole number"),
            ("buttons = 3", r"buttons must be a \[table\]"),
            ("pan_max = true", "pan_max"),
            ('debug = "yes"', "debug must be true or false"),
            ("deadzone = 0.9", "deadzone"),                  # Settings validation still runs
            ('[buttons]\n0 = "home"', "bad command 'home'"),
            ('[buttons]\n0 = "preset"', "bad command"),
            ('[buttons]\n0 = "preset -1"', "bad command 'preset -1'"),
            ('[buttons]\n5 = "tracking 1"', "bad command 'tracking 1'"),     # tracking takes no number
            ("timeout = inf", "timeout"),                    # TOML allows inf
            ('[buttons]\n0 = 3', "bad command"),
            ('[buttons]\nx = "preset 1"', "index must be a number"),
            ("[buttons]\n40 = \"preset 1\"", "buttons"),
            ("host = ", "Invalid value"),                    # TOML syntax error
        ]:
            with self.subTest(text=text), self.assertRaisesRegex(SystemExit, f"{config.FILE_NAME}: .*{word}"):
                self.load(text)

    def test_password_checked_before_file(self):
        with mock.patch.dict(os.environ, {"PTZ_PASSWORD": ""}), \
                self.assertRaisesRegex(SystemExit, "Set the camera password first"):
            config.load(Path("does-not-exist.toml"))

    def test_unreadable_file_is_clean_exit(self):
        with mock.patch.dict(os.environ, {"PTZ_PASSWORD": "pw"}), \
                self.assertRaisesRegex(SystemExit, "Can't read settings file"):
            config.load(Path("does-not-exist.toml"))


class EncodingTest(unittest.TestCase):
    """Notepad can save the settings file in several encodings: each loads, or the error says what to do."""

    def load_bytes(self, raw):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"PTZ_PASSWORD": "pw"}):
            path = Path(d) / config.FILE_NAME
            path.write_bytes(raw)
            return config.load(path)

    def test_utf8_with_bom_and_utf16_load(self):
        for name, raw in [("UTF-8 with BOM", b"\xef\xbb\xbf" + config.TEMPLATE.encode()),
                          ('"Unicode" (UTF-16)', config.TEMPLATE.encode("utf-16"))]:
            with self.subTest(name):
                self.assertEqual(self.load_bytes(raw).host, Settings().host)

    def test_other_encoding_says_save_as_utf8(self):
        raw = '# הגדרות\nhost = "http://10.0.0.1"\n'.encode("cp1255")      # Hebrew comment saved as ANSI
        with self.assertRaisesRegex(SystemExit, f"{config.FILE_NAME}: can't read it as text. Save it as UTF-8"):
            self.load_bytes(raw)


if __name__ == "__main__":
    unittest.main()
