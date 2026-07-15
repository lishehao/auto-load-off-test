from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.enums import ConnectionMode, CorrectionMode, CouplingMode, ImpedanceMode, MagnitudePhaseMode, TriggerMode
from app.domain.instrument_capabilities import InstrumentRole, get_capability, model_names_for_role
from app.domain.models import (
    AppSettings,
    AwgSettings,
    ChannelSelection,
    InstrumentEndpoint,
    InstrumentSetup,
    OscSettings,
    RunMode,
    SweepSpec,
)
from app.domain.validators import ValidationError, validate_settings
from app.infrastructure.persistence.settings_defaults import DefaultSettingsFactory


class InstrumentCapabilityTests(unittest.TestCase):
    def test_registry_exposes_current_production_models_only_by_default(self) -> None:
        self.assertEqual(model_names_for_role(InstrumentRole.AWG), ("DSG4102", "DSG836"))
        self.assertEqual(model_names_for_role(InstrumentRole.OSC), ("MDO34", "MDO3024", "DHO1202", "DHO1204"))
        self.assertNotIn("MOCK_AWG", model_names_for_role(InstrumentRole.AWG))
        self.assertIn("MOCK_AWG", model_names_for_role(InstrumentRole.AWG, include_test=True))

    def test_dho_profile_documents_high_z_only_impedance(self) -> None:
        capability = get_capability("DHO1202", InstrumentRole.OSC)

        self.assertEqual(capability.channel_count, 2)
        self.assertEqual(capability.supported_impedances, frozenset((ImpedanceMode.HIGH_Z,)))
        self.assertIn("1 MOhm", " ".join(capability.safety_notes))

    def test_default_settings_pass_capability_validation(self) -> None:
        validate_settings(DefaultSettingsFactory().create())

    def test_unsupported_model_fails_clearly(self) -> None:
        settings = DefaultSettingsFactory().create()
        settings.setup.awg.model = "NEW_AWG"

        with self.assertRaisesRegex(ValueError, "Unsupported awg model"):
            validate_settings(settings)

    def test_osc_channel_and_impedance_are_capability_aware(self) -> None:
        settings = DefaultSettingsFactory().create()
        settings.setup.osc.model = "DHO1202"
        settings.setup.osc_settings.impedance = ImpedanceMode.R50

        with self.assertRaisesRegex(ValidationError, "does not support OSC impedance"):
            validate_settings(settings)

        settings.setup.osc_settings.impedance = ImpedanceMode.HIGH_Z
        settings.setup.channels.osc_test_ch = 3
        with self.assertRaisesRegex(ValidationError, "channel 3 exceeds DHO1202"):
            validate_settings(settings)

    def test_awg_channel_and_known_frequency_limits_are_capability_aware(self) -> None:
        settings = DefaultSettingsFactory().create()
        settings.setup.awg.model = "DSG836"
        settings.setup.awg_settings.impedance = ImpedanceMode.R50
        settings.setup.channels.awg_ch = 2

        with self.assertRaisesRegex(ValidationError, "AWG channel 2 exceeds DSG836"):
            validate_settings(settings)

        settings = DefaultSettingsFactory().create()
        settings.sweep.stop_hz = 200e6
        with self.assertRaisesRegex(ValidationError, "stop frequency"):
            validate_settings(settings)

    def test_test_only_profiles_validate_only_when_explicitly_enabled(self) -> None:
        settings = _mock_settings()

        with self.assertRaisesRegex(ValueError, "Unsupported awg model"):
            validate_settings(settings)

        validate_settings(settings, include_test=True)


def _mock_settings() -> AppSettings:
    return AppSettings(
        schema_version=1,
        freq_unit="Hz",
        sweep=SweepSpec(start_hz=1_000.0, stop_hz=10_000.0, step_hz=1_000.0, step_count=None, is_log=False),
        run_mode=RunMode(
            correction_mode=CorrectionMode.NONE,
            trigger_mode=TriggerMode.FREE_RUN,
            auto_range=False,
            auto_reset=False,
        ),
        setup=InstrumentSetup(
            awg=InstrumentEndpoint(model="MOCK_AWG", connect_mode=ConnectionMode.AUTO),
            osc=InstrumentEndpoint(model="MOCK_OSC", connect_mode=ConnectionMode.AUTO),
            channels=ChannelSelection(awg_ch=1, osc_test_ch=1, osc_ref_ch=2, osc_trig_ch=2),
            awg_settings=AwgSettings(amplitude_vpp=1.0, impedance=ImpedanceMode.R50),
            osc_settings=OscSettings(
                full_scale_v=1.0,
                offset_v=0.0,
                points=1_000,
                impedance=ImpedanceMode.R50,
                coupling=CouplingMode.DC,
            ),
        ),
        magnitude_phase_mode=MagnitudePhaseMode.MAG,
        auto_save_data=False,
    )
if __name__ == "__main__":
    unittest.main()
