import sys
import tempfile
import tomllib
import unittest
from dataclasses import fields, replace
from pathlib import Path
from unittest import mock

from ptz_joystick import config
from ptz_joystick.config import Settings, template
from ptz_joystick.core.commands import Preset, Tracking
from ptz_joystick.core.problem import Problem


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

    def test_unwritable_folder_says_where_to_move(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(Problem) as cm:
            config.write_template_if_missing(Path(d) / "missing" / config.FILE_NAME)
        self.assertEqual(cm.exception.text(),
                         f"Can't create {config.FILE_NAME}. Move the exe to a folder you can write to.")


class RenderTest(unittest.TestCase):
    def test_unusual_values_come_back_the_same(self):
        s = Settings(host='http://cam/"x"\\y', user="מפעיל\x7f", log_file="D:\\logs\\ptz.log", controller="keyboard",
                     invert_tilt=False, deadzone=0.05, timeout=2.0, pan_max=1,
                     buttons={0: Preset(7), 5: Tracking(True), 31: Preset(0)})
        for case in (s, replace(s, buttons={}, log_file="")):
            with self.subTest(case=case):
                self.assertEqual(config.from_dict(tomllib.loads(config.render(case)), ""), case)

    def test_never_writes_the_password(self):
        self.assertNotIn("secret", config.render(Settings(password="secret")))

    def test_the_installer_finds_its_two_lines(self):
        lines = config.TEMPLATE.splitlines()
        self.assertIn('host = "http://192.168.77.3"    # camera address', lines)
        self.assertIn('controller = "winmm"            # winmm (any controller joy.cpl shows) or keyboard', lines)

    def test_a_long_value_keeps_its_comment(self):
        text = config.render(Settings(host="http://" + "a" * 40))
        line = next(x for x in text.splitlines() if x.startswith("host = "))
        self.assertTrue(line.endswith('" # camera address'), line)


class SaveTest(unittest.TestCase):
    def test_a_saved_file_reads_back(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / config.FILE_NAME
            config.save(path, Settings(host="http://10.0.0.9"))
            self.assertEqual(config.read(path), Settings(host="http://10.0.0.9"))
            self.assertEqual([p.name for p in Path(d).iterdir()], [config.FILE_NAME])     # no .tmp left over

    def test_a_failed_save_leaves_the_old_file_whole(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / config.FILE_NAME
            path.write_text('host = "http://old"\n', encoding="utf-8")
            with mock.patch.object(template.os, "replace", side_effect=PermissionError("denied")), \
                    self.assertRaises(Problem) as cm:
                config.save(path, Settings())
            self.assertEqual(path.read_text(encoding="utf-8"), 'host = "http://old"\n')
        self.assertEqual(cm.exception.text(),
                         f"Can't save {config.FILE_NAME}. Check that you can write to its folder.")
        self.assertIn("denied", cm.exception.detail)


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
