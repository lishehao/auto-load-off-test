from __future__ import annotations

from app.application.ports.persistence import ReferenceRepository
from app.domain.calibration import build_reference_interpolator
from app.domain.models import ReferenceCurve


class LoadReferenceUseCase:
    def __init__(self, repository: ReferenceRepository) -> None:
        self._repository = repository

    def execute(self, path: str) -> tuple[ReferenceCurve, object]:
        curve = self._repository.load_reference(path)
        interpolator = build_reference_interpolator(curve)
        return curve, interpolator
