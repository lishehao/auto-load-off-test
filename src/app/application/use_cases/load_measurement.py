from __future__ import annotations

from app.application.dto import LoadedMeasurement
from app.application.ports.persistence import MeasurementRepository


class LoadMeasurementUseCase:
    def __init__(self, repository: MeasurementRepository) -> None:
        self._repository = repository

    def execute(self, path: str) -> LoadedMeasurement:
        return self._repository.load(path)
