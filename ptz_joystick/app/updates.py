"""Tell the user when a newer release is on GitHub. Never downloads or replaces anything."""
import logging
import re
import threading
from collections.abc import Callable

import requests

LATEST = "https://api.github.com/repos/yotamh96/ptz_joystick/releases/latest"   # skips drafts and pre-releases

log = logging.getLogger(__name__)


def parse(tag) -> tuple[int, ...] | None:
    """'v0.3.0' -> (0, 3, 0). Anything else ('dev', 'main', 'v1.2') -> None."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag) if isinstance(tag, str) else None
    return tuple(map(int, m.groups())) if m else None


def newer_release(current, get=requests.get) -> tuple[str, str] | None:
    """(tag, url) of the latest release if it's newer than current. None otherwise, or if anything goes wrong."""
    mine = parse(current)
    if mine is None:                    # source run or branch build: nothing to compare
        return None
    try:
        r = get(LATEST, timeout=3, headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()            # 403 = rate limited
        latest = r.json()
        tag, url = latest["tag_name"], latest["html_url"]
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        log.debug("update check failed: %r", e)
        return None
    theirs = parse(tag)
    return (tag, url) if theirs and theirs > mine else None


def check_in_background(current, get=requests.get,
                        on_found: Callable[[str, str], None] | None = None) -> threading.Thread:
    """Startup never waits for GitHub: the answer is logged whenever it arrives, then passed to on_found(tag, url)."""
    def check():
        if found := newer_release(current, get):
            log.info("Update available: %s (you have %s) %s", found[0], current, found[1])
            if on_found:
                on_found(*found)

    t = threading.Thread(target=check, name="update-check", daemon=True)
    t.start()
    return t
