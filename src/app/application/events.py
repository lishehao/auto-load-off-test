from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.models import AppSettings, SweepPoint, SweepResult


class EventEmitter(Protocol):
    def emit(self, event: object) -> None:  # pragma: no cover - protocol
        ...


@dataclass(slots=True)
class SweepStarted:
    total_points: int


@dataclass(slots=True)
class SweepProgress:
    freq_hz: float
    point_index: int
    total_points: int


@dataclass(slots=True)
class SweepDataUpdated:
    last_point: SweepPoint
    partial_result: SweepResult


@dataclass(slots=True)
class SweepWarning:
    code: str
    message: str


@dataclass(slots=True)
class SweepFailed:
    error_code: str
    message: str
    result: SweepResult | None = None


@dataclass(slots=True)
class SweepCompleted:
    result: SweepResult


@dataclass(slots=True)
class SweepStopped:
    result: SweepResult


@dataclass(slots=True)
class SweepWorkerFinished:
    result: SweepResult


@dataclass(slots=True)
class SweepAutoSaved:
    artifacts: object
    result: SweepResult
    settings: AppSettings


@dataclass(slots=True)
class ConnectionStatusUpdated:
    awg_connected: bool
    osc_connected: bool
