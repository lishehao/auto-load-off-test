from __future__ import annotations

from app.application.dto import SaveArtifacts, SaveTarget
from app.application.ports.persistence import MeasurementRepository
from app.domain.models import AppSettings, SweepResult


class SaveMeasurementUseCase:
    def __init__(self, repository: MeasurementRepository) -> None:
        self._repository = repository

    def execute(self, result: SweepResult, settings: AppSettings, target: SaveTarget) -> SaveArtifacts:
        return self._repository.save(result=result, settings=settings, target=target)
