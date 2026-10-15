"""Commands go out on one background thread so a slow camera never stalls the controller loop.
Latest command per type wins; it stays pending until the camera accepts it (failures retry)."""
import logging
import threading
import time
from collections.abc import Callable

from ..cameras import Camera
from .commands import MOVES, Command

log = logging.getLogger(__name__)

# One-shot actions (anything but a stick move) are dropped after this many refusals: a preset recall arriving
# minutes late, when the camera comes back, would surprise the operator. Moves are current state and retry
# until accepted.
GIVE_UP_AFTER = 3


class CommandSender:
    def __init__(self, camera: Camera, backoff=0.2, on_camera: Callable[[bool], None] | None = None):
        # on_camera(ok): called from the sender thread when the camera starts (True) or stops (False) taking commands
        self._camera, self._backoff, self._on_camera = camera, backoff, on_camera
        self._pending: dict[type, Command] = {}             # command type -> latest command
        self._tries: dict[type, tuple[Command, int]] = {}   # command type -> (command, refusals); sender thread only
        self._answering: bool | None = None  # did the camera take the last command it answered? sender thread only
        self._closed = False         # set by drain_with: nothing may follow the final stops
        self._cv = threading.Condition()
        threading.Thread(target=self._run, daemon=True).start()

    def send(self, cmd: Command):
        with self._cv:
            if not self._closed:
                self._pending[type(cmd)] = cmd
                self._cv.notify_all()

    def drain_with(self, stops: list[Command], timeout=3.0) -> bool:
        """Final: drop everything pending, send `stops`, ignore later send()s, wait for the camera to take
        the stops. -> True if it did."""
        with self._cv:
            self._closed = True
            self._pending = {type(c): c for c in stops}
            self._cv.notify_all()
            return self._cv.wait_for(lambda: not self._pending, timeout)

    def _run(self):
        while True:
            with self._cv:
                self._cv.wait_for(lambda: self._pending)
                batch = list(self._pending.values())
            failed = False
            for cmd in batch:                   # a refused command must not hold back the ones after it (stop!)
                with self._cv:
                    if self._pending.get(type(cmd)) != cmd:
                        continue                # replaced meanwhile, or drain_with swapped in the stops
                if not self._send(cmd):
                    failed = True
                    # Counted per type and compared with ==, so a command never needs to be hashable.
                    prev, tries = self._tries.get(type(cmd), (None, 0))
                    tries = tries + 1 if prev == cmd else 1
                    self._tries[type(cmd)] = (cmd, tries)
                    if isinstance(cmd, MOVES) or tries < GIVE_UP_AFTER:
                        continue
                    log.warning("gave up on %s after %d tries", cmd, tries)
                self._tries.pop(type(cmd), None)
                with self._cv:
                    if self._pending.get(type(cmd)) == cmd:
                        del self._pending[type(cmd)]
                    self._cv.notify_all()
            if failed:
                time.sleep(self._backoff)        # camera unhappy: back off, then retry with the latest commands

    def _send(self, cmd) -> bool:
        """True = done with cmd (the camera took it, or never can). False = try again."""
        try:
            ok = self._camera.send(cmd)
        except TypeError:                       # this camera can't do this kind of command: retrying won't help
            log.exception("dropped %s", cmd)
            return True
        except Exception:
            # The adapter should have returned False. Retry anyway, so a network error can never swallow a
            # stop. Full traceback the first time per command, not on every retry.
            again = self._tries.get(type(cmd), (None, 0))[0] == cmd
            log.log(logging.DEBUG if again else logging.ERROR, "sending %s failed", cmd, exc_info=True)
            ok = False
        else:
            log.debug("sent %s" if ok else "camera refused %s", cmd)
        self._answered(ok)
        return ok

    def _answered(self, ok: bool):
        """Tell on_camera when the camera starts or stops taking commands: on a change, not on every send."""
        if ok == self._answering:
            return
        self._answering = ok
        if self._on_camera:
            try:
                self._on_camera(ok)
            except Exception:
                log.exception("on_camera failed")
