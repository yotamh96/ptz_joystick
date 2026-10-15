"""Where log lines go: the terminal (when there is one), plus the log file from the settings."""
import logging
import sys

from ..config import Settings

log = logging.getLogger(__name__)


def setup_logging(s: Settings):
    """Terminal when there is one (not in the tray exe); plus s.log_file if set. debug=True adds per-command and
    per-reading lines."""
    handlers: list[logging.Handler] = [logging.StreamHandler()] if sys.stderr else []
    file_error: OSError | None = None
    if s.log_file:
        try:
            handlers.append(logging.FileHandler(s.log_file, encoding="utf-8"))
        except OSError as e:            # locked by another program, read-only folder, ...
            file_error = e
    logging.basicConfig(level=logging.DEBUG if s.debug else logging.INFO, handlers=handlers, force=True,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("urllib3").setLevel(logging.WARNING)   # requests' own chatter at DEBUG
    if file_error:
        log.warning("Can't write log file %s (%s): terminal only.", s.log_file, file_error)
