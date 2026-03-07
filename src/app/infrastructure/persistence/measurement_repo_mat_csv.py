from __future__ import annotations

from app.application.dto import LoadedMeasurement, SaveArtifacts, SaveTarget
from app.domain.models import AppSettings, SweepResult
from app.infrastructure.persistence.measurement_exporter import MeasurementExporter
from app.infrastructure.persistence.measurement_loader import MeasurementLoader


class MatCsvMeasurementRepository:
    def __init__(
        self,
        *,
        exporter: MeasurementExporter | None = None,
        loader: MeasurementLoader | None = None,
    ) -> None:
        self._exporter = exporter or MeasurementExporter()
        self._loader = loader or MeasurementLoader()

    def save(self, result: SweepResult, settings: AppSettings, target: SaveTarget) -> SaveArtifacts:
        return self._exporter.export(result=result, settings=settings, target=target)

    def load(self, file_path: str) -> LoadedMeasurement:
        return self._loader.load(file_path)
