"""Problem: something the operator must fix, in their words. Raised (or logged) where the facts are known; the
console (app/main.py) and the tray (app/status.py) show it, each adding its own restart step. How to word one:
docs/extending.md, "Writing a message"."""


class Problem(Exception):
    """what: what is wrong. fix: what to do about it. detail: the technical cause, for the log only."""

    def __init__(self, what: str, fix: str = "", detail: str = ""):
        super().__init__(what)
        self.what, self.fix, self.detail = what, fix, detail

    def text(self, then: str = "") -> str:
        """What the operator sees. then: the restart step ("click Restart"), only when the app stopped."""
        if self.fix:
            return f"{self.what}. {self.fix}, then {then}." if then else f"{self.what}. {self.fix}."
        return f"{self.what}. {then[:1].upper()}{then[1:]}." if then else f"{self.what}."

    def log_line(self, then: str = "") -> str:
        """text(then), plus the detail in brackets."""
        return f"{self.text(then)} ({self.detail})" if self.detail else self.text(then)


def crashed(e: BaseException) -> Problem:
    """An exception nobody expected: a plain sentence for the operator, its repr for the log."""
    return Problem("Unexpected error in ptz_joystick", fix="See the log for details", detail=repr(e))
