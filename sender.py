"""Commands go out on one background thread so a slow camera never stalls the controller loop.
Latest command per type wins; it stays pending until the camera accepts it (failures retry)."""
import logging
import threading
import time

from .cameras import Camera
from .commands import Command, Preset

log = logging.getLogger(__name__)

# One-shot actions are dropped after this many refusals: a preset recall arriving minutes late, when the
# camera comes back, would surprise the operator. Moves are current state and retry until accepted.
GIVE_UP_AFTER = {Preset: 3}


class CommandSender:
    def __init__(self, camera: Camera, backoff=0.2):
        self.camera, self.backoff = camera, backoff
        self.pending = {}           # command type -> latest command
        self.tries = {}             # command -> refusals so far (sender thread only)
        self.cv = threading.Condition()
        threading.Thread(target=self._run, daemon=True).start()

    def send(self, cmd: Command):
        with self.cv:
            self.pending[type(cmd)] = cmd
            self.cv.notify_all()

    def drain_with(self, stops: list[Command], timeout=3.0) -> bool:
        """Drop everything pending, send `stops`, wait for the camera to take them. -> True if it did."""
        with self.cv:
            self.pending = {type(c): c for c in stops}
            self.cv.notify_all()
            return self.cv.wait_for(lambda: not self.pending, timeout)

    def _run(self):
        while True:
            with self.cv:
                self.cv.wait_for(lambda: self.pending)
                batch = list(self.pending.values())
            failed = False
            for cmd in batch:                   # a refused command must not hold back the ones after it (stop!)
                try:
                    ok = self.camera.send(cmd)
                except Exception:               # adapter bug (e.g. command it can't translate): drop it, keep
                    log.exception("dropped %s", cmd)   # this thread alive so stops still go out
                    ok = True
                else:
                    log.debug("sent %s" if ok else "camera refused %s", cmd)
                if not ok:
                    failed = True
                    tries = self.tries[cmd] = self.tries.get(cmd, 0) + 1
                    if tries < GIVE_UP_AFTER.get(type(cmd), float("inf")):
                        continue
                    log.warning("gave up on %s after %d tries", cmd, tries)
                self.tries.pop(cmd, None)
                with self.cv:
                    if self.pending.get(type(cmd)) == cmd:
                        del self.pending[type(cmd)]
                    self.cv.notify_all()
            if failed:
                time.sleep(self.backoff)        # camera unhappy: back off, then retry with the latest commands
