from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.application.services.instrument_discovery import (
    InstrumentDiscoveryService,
    format_connection_receipt,
    format_scan_receipt,
)
from app.domain.enums import ConnectionMode, CouplingMode, ImpedanceMode
from app.domain.instrument_capabilities import InstrumentRole
from app.domain.models import (
    AwgSettings,
    ChannelSelection,
    InstrumentEndpoint,
    InstrumentSetup,
    OscSettings,
)
from app.infrastructure.instruments.equips_factory import resolve_visa_address


class FakeScanner:
    def __init__(self, resources: tuple[str, ...]) -> None:
        self._resources = resources

    def list_resources(self) -> tuple[str, ...]:
        return self._resources


class FakeIdentityProbe:
    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses

    def identify(self, address: str, timeout_ms: int | None = None) -> str:
        _ = timeout_ms
        if address not in self._responses:
            raise TimeoutError("not reachable")
        return self._responses[address]


class InstrumentDiscoveryTests(unittest.TestCase):
    def test_scan_resources_returns_receipt(self) -> None:
        service = InstrumentDiscoveryService(
            scanner=FakeScanner(("USB::AWG::INSTR", "TCPIP0::10.0.0.2::INSTR")),
            identity_probe=FakeIdentityProbe({}),
        )

        receipt = format_scan_receipt(service.scan_resources())

        self.assertIn("2 VISA resources", receipt)
        self.assertIn("USB::AWG::INSTR", receipt)

    def test_test_setup_reports_connected_idn(self) -> None:
        service = InstrumentDiscoveryService(
            scanner=FakeScanner(()),
            identity_probe=FakeIdentityProbe(
                {
                    "USB::AWG::INSTR": "RIGOL,DG4102,123,1.0",
                    "USB::OSC::INSTR": "TEKTRONIX,MDO34,456,1.0",
                }
            ),
        )

        checks = service.test_setup(_setup(), resolve_visa_address)
        receipt = format_connection_receipt(checks)

        self.assertTrue(all(check.status == "connected" for check in checks))
        self.assertIn("RIGOL,DG4102", checks[0].idn)
        self.assertIn("AWG connected", receipt)
        self.assertIn("OSC connected", receipt)

    def test_address_empty_and_offline_states_are_clear(self) -> None:
        setup = _setup()
        setup.awg.visa_address = ""
        service = InstrumentDiscoveryService(
            scanner=FakeScanner(()),
            identity_probe=FakeIdentityProbe({"USB::OTHER::INSTR": "OTHER"}),
        )

        checks = service.test_setup(setup, resolve_visa_address)

        self.assertEqual(checks[0].status, "address_empty")
        self.assertEqual(checks[1].status, "offline")
        self.assertIn("not reachable", checks[1].message)

    def test_unsupported_model_state_does_not_probe_hardware(self) -> None:
        endpoint = InstrumentEndpoint(
            model="NEW_SCOPE",
            connect_mode=ConnectionMode.AUTO,
            visa_address="USB::NEW::INSTR",
        )
        service = InstrumentDiscoveryService(scanner=FakeScanner(()), identity_probe=FakeIdentityProbe({}))

        check = service.test_endpoint(role=InstrumentRole.OSC, endpoint=endpoint, address="USB::NEW::INSTR")

        self.assertEqual(check.status, "unsupported_model")
        self.assertIn("Unsupported OSC model", check.message)


def _setup() -> InstrumentSetup:
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


if __name__ == "__main__":
    unittest.main()
