import logging
import sys

from .app.main import main

try:
    main()
except KeyboardInterrupt:
    pass
except Exception as e:                  # SystemExit (clean, explained exits) passes through untouched
    logging.getLogger("ptz_joystick").critical("Crashed: %r", e, exc_info=True)   # traceback into the log file
    sys.exit(1)
