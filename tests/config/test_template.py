import sys
import tempfile
import tomllib
import unittest
from dataclasses import fields
from pathlib import Path
from unittest import mock

from ptz_joystick import config
from ptz_joystick.config import Settings


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
        repo = Path(__file__).resolve().parents[2]         # tests/config/ is two below the repo
        self.assertTrue((repo / "README.md").exists())
        self.assertEqual(config.default_path(), repo / config.FILE_NAME)

    def test_exe_uses_its_own_folder(self):
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "executable", r"C:\tools\ptz_joystick.exe"):
            self.assertEqual(config.default_path(), Path(r"C:\tools") / config.FILE_NAME)


if __name__ == "__main__":
    unittest.main()
