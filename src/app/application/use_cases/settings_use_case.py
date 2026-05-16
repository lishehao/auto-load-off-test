from __future__ import annotations

from app.application.ports.persistence import SettingsRepository
from app.domain.models import AppSettings


class SettingsUseCase:
    def __init__(self, repository: SettingsRepository) -> None:
        self._repository = repository

    def load(self) -> AppSettings:
        return self._repository.load()

    def save(self, settings: AppSettings) -> None:
        self._repository.save(settings)
