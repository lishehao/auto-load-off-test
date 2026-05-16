from __future__ import annotations

import json
from pathlib import Path

from app.domain.models import AppSettings
from app.domain.validators import validate_settings
from app.infrastructure.persistence.file_store import FileStore
from app.infrastructure.persistence.settings_defaults import DefaultSettingsFactory
from app.infrastructure.persistence.settings_serializer import SettingsSerializer
from app.runtime.paths import AppPaths


class JsonSettingsRepository:
    def __init__(
        self,
        config_path: Path | None = None,
        *,
        defaults_factory: DefaultSettingsFactory | None = None,
        serializer: SettingsSerializer | None = None,
        file_store: FileStore | None = None,
    ) -> None:
        default_path = AppPaths.default().settings_path

        self._serializer = serializer or SettingsSerializer()
        self._defaults_factory = defaults_factory or DefaultSettingsFactory()
        self._file_store = file_store or FileStore(config_path or default_path)

    def load(self) -> AppSettings:
        if not self._file_store.exists():
            settings = self._defaults_factory.create()
            self.save(settings)
            return settings

        payload = json.loads(self._file_store.read_text(encoding="utf-8"))
        settings = self._serializer.from_payload(payload)
        validate_settings(settings)
        return settings

    def save(self, settings: AppSettings) -> None:
        validate_settings(settings)
        payload = self._serializer.to_payload(settings)
        self._file_store.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
