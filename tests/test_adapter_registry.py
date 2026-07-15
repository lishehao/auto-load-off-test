from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.domain.enums import ConnectionMode, CouplingMode, ImpedanceMode
from app.domain.models import (
    AwgSettings,
    ChannelSelection,
    InstrumentEndpoint,
    InstrumentSetup,
    OscSettings,
)
from app.infrastructure.instruments.adapter_registry import (
    AdapterRegistry,
    build_mock_adapter_registry,
)
from app.infrastructure.instruments.equips_factory import create_instrument_ports_with_registry


class AdapterRegistryTests(unittest.TestCase):
    def test_registered_models_resolve_through_explicit_registry(self) -> None:
        registry = AdapterRegistry()
        awg = object()
        osc = object()
        registry.register_awg("DSG4102", lambda model, address: (model, address, awg))
        registry.register_osc("MDO34", lambda model, address: (model, address, osc))

        ports = create_instrument_ports_with_registry(_production_setup(), registry)

        self.assertEqual(ports.awg, ("DSG4102", "USB::AWG::INSTR", awg))
        self.assertEqual(ports.osc, ("MDO34", "USB::OSC::INSTR", osc))
        self.assertEqual(ports.awg_address, "USB::AWG::INSTR")
        self.assertEqual(ports.osc_address, "USB::OSC::INSTR")

    def test_unsupported_model_fails_before_implicit_equips_mapping(self) -> None:
        registry = AdapterRegistry()

        with self.assertRaisesRegex(ValueError, "Unsupported awg model"):
            registry.register_awg("NOT_SUPPORTED", lambda model, address: object())

    def test_missing_adapter_registration_fails_clearly(self) -> None:
        registry = AdapterRegistry()
        registry.register_awg("DSG4102", lambda model, address: object())

        with self.assertRaisesRegex(ValueError, "No OSC adapter registered"):
            create_instrument_ports_with_registry(_production_setup(), registry)

    def test_mock_registry_provides_hardware_free_ports(self) -> None:
        ports = create_instrument_ports_with_registry(_mock_setup(), build_mock_adapter_registry())

        ports.awg.set_frequency(2_000.0, 1)
        ports.awg.set_amplitude_vpp(1.2, 1)
        ports.awg.output_on(1)
        times, volts = ports.osc.read_waveform(1, 1000)

        self.assertEqual(len(times), 1000)
        self.assertEqual(len(volts), 1000)
        self.assertGreater(float(volts.max() - volts.min()), 0.1)


def _production_setup() -> InstrumentSetup:
    return InstrumentSetup(
        awg=InstrumentEndpoint(
            model="DSG4102",
            connect_mode=ConnectionMode.AUTO,
            visa_address="USB::AWG::INSTR",
        ),
        osc=InstrumentEndpoint(
            model="MDO34",
            connect_mode=ConnectionMode.AUTO,
            visa_address="USB::OSC::INSTR",
        ),
        channels=ChannelSelection(awg_ch=1, osc_test_ch=1, osc_ref_ch=2, osc_trig_ch=2),
        awg_settings=AwgSettings(amplitude_vpp=1.0, impedance=ImpedanceMode.R50),
        osc_settings=OscSettings(
            full_scale_v=1.0,
            offset_v=0.0,
            points=1000,
            impedance=ImpedanceMode.R50,
            coupling=CouplingMode.DC,
        ),
    )


def _mock_setup() -> InstrumentSetup:
    return InstrumentSetup(
        awg=InstrumentEndpoint(model="MOCK_AWG", connect_mode=ConnectionMode.AUTO),
        osc=InstrumentEndpoint(model="MOCK_OSC", connect_mode=ConnectionMode.AUTO),
        channels=ChannelSelection(awg_ch=1, osc_test_ch=1, osc_ref_ch=2, osc_trig_ch=2),
        awg_settings=AwgSettings(amplitude_vpp=1.0, impedance=ImpedanceMode.R50),
        osc_settings=OscSettings(
            full_scale_v=1.0,
            offset_v=0.0,
            points=1000,
            impedance=ImpedanceMode.R50,
            coupling=CouplingMode.DC,
        ),
    )


if __name__ == "__main__":
    unittest.main()
