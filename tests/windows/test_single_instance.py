import os
import unittest

from ptz_joystick.windows import single_instance


def unique(tag):
    """A name no real copy uses, so the tests pass while ptz_joystick runs."""
    return f"Local\\ptz_joystick_test_{tag}_{os.getpid()}"


class ClaimTest(unittest.TestCase):
    def test_a_second_claim_of_the_same_name_fails(self):
        self.assertTrue(single_instance.claim(unique("same")))
        self.assertFalse(single_instance.claim(unique("same")))

    def test_other_names_are_free(self):
        self.assertTrue(single_instance.claim(unique("a")))
        self.assertTrue(single_instance.claim(unique("b")))


if __name__ == "__main__":
    unittest.main()
