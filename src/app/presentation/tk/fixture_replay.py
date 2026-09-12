from __future__ import annotations

from copy import deepcopy
import time
from typing import Callable

from app.domain.models import SweepResult


class FixtureReplay:
    """A Tk-scheduler-driven data replay; it never constructs instrument ports."""

    def __init__(self, *, schedule, cancel, on_update, on_finish, clock: Callable[[], float] = time.monotonic):
        self._schedule = schedule
        self._cancel = cancel
        self._on_update = on_update
        self._on_finish = on_finish
        self._clock = clock
        self._token = 0
        self._callback_id = None
        self._full = SweepResult()
        self._index = 0
        self._started_at = 0.0
        self.active = False

    def start(self, result: SweepResult, *, interval_ms: int = 150) -> None:
        if self.active:
            raise RuntimeError("A fixture replay is already active")
        if result.is_empty or interval_ms <= 0:
            raise ValueError("Replay requires data and a positive interval")
        self._token += 1
        token = self._token
        self._full = deepcopy(result)
        self._index = 0
        self._started_at = self._clock()
        self.active = True
        self._publish("replaying")
        if self.active and token == self._token:
            self._callback_id = self._schedule(interval_ms, lambda: self._step(token, interval_ms))

    def stop(self, *, notify: bool = True) -> None:
        if not self.active:
            return
        self.active = False
        self._token += 1
        if self._callback_id is not None:
            self._cancel(self._callback_id)
            self._callback_id = None
        if notify:
            self._publish("stopped")
            self._on_finish("stopped")

    def _step(self, token: int, interval_ms: int) -> None:
        if not self.active or token != self._token:
            return
        self._callback_id = None
        self._index += 1
        finished = self._index == len(self._full.points)
        self._publish("completed" if finished else "replaying")
        if not self.active or token != self._token:
            return
        if finished:
            self.active = False
            self._on_finish("completed")
        elif self.active and token == self._token:
            self._callback_id = self._schedule(interval_ms, lambda: self._step(token, interval_ms))

    def _publish(self, status: str) -> None:
        result = SweepResult(deepcopy(self._full.points[:self._index]), deepcopy(self._full.meta))
        result.meta.update(processing="fixture_replay", run_status=status,
                           planned_points=len(self._full.points), completed_points=self._index,
                           live_hardware_used=False)
        self._on_update(result, self._index, len(self._full.points), self._clock() - self._started_at)
