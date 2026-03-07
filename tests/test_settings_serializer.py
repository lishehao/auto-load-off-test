from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.enums import TriggerMode
from app.infrastructure.persistence.settings_defaults import DefaultSettingsFactory
from app.infrastructure.persistence.settings_serializer import SettingsSerializer


class SettingsSerializerTests(unittest.TestCase):
    def test_schema_version_one_round_trip(self) -> None:
        serializer = SettingsSerializer()
        settings = DefaultSettingsFactory().create()
        settings.run_mode.trigger_mode = TriggerMode.TRIGGERED
        settings.setup.awg.visa_address = "USB::MOCK::INSTR"

        payload = serializer.to_payload(settings)
        loaded = serializer.from_payload(payload)

        self.assertEqual(loaded.schema_version, 1)
        self.assertEqual(loaded.run_mode.trigger_mode, TriggerMode.TRIGGERED)
        self.assertEqual(loaded.setup.awg.visa_address, "USB::MOCK::INSTR")


if __name__ == "__main__":
    unittest.main()
