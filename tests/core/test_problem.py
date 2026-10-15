import unittest

from ptz_joystick.core.problem import Problem, crashed


class TextTest(unittest.TestCase):
    def test_what_and_fix(self):
        self.assertEqual(Problem("No controller found", fix="Plug it in").text(), "No controller found. Plug it in.")

    def test_then_joins_the_fix(self):
        self.assertEqual(Problem("A", fix="B").text(then="click Restart"), "A. B, then click Restart.")

    def test_then_alone_becomes_the_order(self):
        self.assertEqual(Problem("A").text(then="click Restart"), "A. Click Restart.")

    def test_what_alone(self):
        self.assertEqual(Problem("A").text(), "A.")

    def test_detail_only_in_the_log_line(self):
        p = Problem("A", fix="B", detail="HTTP 401")
        self.assertEqual(p.text(), "A. B.")
        self.assertEqual(p.log_line(), "A. B. (HTTP 401)")
        self.assertEqual(p.log_line(then="click Restart"), "A. B, then click Restart. (HTTP 401)")

    def test_no_detail_no_brackets(self):
        self.assertEqual(Problem("A", fix="B").log_line(), "A. B.")

    def test_str_is_what(self):
        self.assertEqual(str(Problem("A", fix="B", detail="x")), "A")


class CrashedTest(unittest.TestCase):
    def test_plain_sentence_for_the_operator_repr_for_the_log(self):
        p = crashed(RuntimeError("boom"))
        self.assertEqual(p.text(), "Unexpected error in ptz_joystick. See the log for details.")
        self.assertEqual(p.detail, "RuntimeError('boom')")


if __name__ == "__main__":
    unittest.main()
