import logging
import os
import tempfile
import unittest

from ptz_joystick.app.logs import setup_logging
from ptz_joystick.config import Settings


class SetupLoggingTest(unittest.TestCase):
    def test_writes_timestamped_lines_to_log_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ptz.log")
            setup_logging(Settings(log_file=path))
            try:
                logging.getLogger("ptz_joystick.test").info("hello camera")
            finally:
                for h in logging.getLogger().handlers[:]:
                    h.close()
                    logging.getLogger().removeHandler(h)
            with open(path, encoding="utf-8") as f:
                line = f.read()
        self.assertRegex(line, r"^\d\d:\d\d:\d\d INFO +hello camera")

    def test_unwritable_log_file_falls_back_to_terminal(self):
        with tempfile.TemporaryDirectory() as d:          # a folder can't be opened as a log file
            with self.assertLogs("ptz_joystick.app.logs", "WARNING") as logs:
                setup_logging(Settings(log_file=d))
            for h in logging.getLogger().handlers[:]:
                logging.getLogger().removeHandler(h)
        self.assertIn("terminal only", logs.output[0])

    def test_no_file_when_log_file_empty(self):
        setup_logging(Settings(log_file=""))
        try:
            self.assertFalse(any(isinstance(h, logging.FileHandler) for h in logging.getLogger().handlers))
        finally:
            for h in logging.getLogger().handlers[:]:
                logging.getLogger().removeHandler(h)


if __name__ == "__main__":
    unittest.main()
