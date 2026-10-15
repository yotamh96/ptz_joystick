"""Every Problem(...) in the package follows docs/extending.md, "Writing a message". It reads the source, so a new
message is checked the day it's written. Only plain-text parts are checked: an f-string's values aren't known."""
import ast
import unittest
from pathlib import Path

import ptz_joystick
from ptz_joystick.app.main import RUN_AGAIN
from ptz_joystick.core.problem import Problem

PACKAGE = Path(ptz_joystick.__file__).parent


def literal(node):
    """A plain string literal's text; None for anything else (an f-string, a name)."""
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def problems():
    """(where, what, fix) for every Problem(...) call. None = not plain text; fix "" = not given."""
    for path in sorted(PACKAGE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Problem":
                args = dict(zip(("what", "fix", "detail"), node.args))
                for k in node.keywords:
                    if k.arg:
                        args[k.arg] = k.value
                fix = literal(args["fix"]) if "fix" in args else ""
                yield f"{path.relative_to(PACKAGE)}:{node.lineno}", literal(args.get("what")), fix


class MessageStyleTest(unittest.TestCase):
    def test_the_scan_finds_the_problems(self):
        self.assertGreaterEqual(len(list(problems())), 15, "renamed Problem, or imported it under another name?")

    def test_every_problem_follows_the_rules(self):
        for where, what, fix in problems():
            with self.subTest(where):
                if what is not None:
                    self.assertTrue(what[:1].isupper(), f"rule 1, capital first letter: {what!r}")
                    self.assertFalse(what.endswith("."), f"rule 1, no period: {what!r}")
                if fix:
                    self.assertFalse(fix.endswith("."), f"rule 2, no period: {fix!r}")
                    self.assertNotRegex(fix.lower(), r"restart|run .*again", "rule 3: the console or tray adds it")
                if what is not None and fix is not None:
                    text = Problem(what, fix).text(then=RUN_AGAIN)
                    self.assertLessEqual(len(text), 120, f"rule 5: {text}")


if __name__ == "__main__":
    unittest.main()
