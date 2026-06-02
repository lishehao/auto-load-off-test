from __future__ import annotations

from collections.abc import Callable

from app.application.ports.instruments import AwgPort, InstrumentPorts, OscPort
from app.domain.instrument_capabilities import InstrumentRole, get_capability
from app.domain.models import InstrumentSetup
from app.infrastructure.instruments.awg_adapter import EquipsAwgAdapter
from app.infrastructure.instruments.mock_adapters import MockAwgAdapter, MockOscAdapter
from app.infrastructure.instruments.osc_adapter import EquipsOscAdapter


AwgAdapterFactory = Callable[[str, str], AwgPort]
OscAdapterFactory = Callable[[str, str], OscPort]


class AdapterRegistry:
    def __init__(self) -> None:
        self._awg_factories: dict[str, AwgAdapterFactory] = {}
        self._osc_factories: dict[str, OscAdapterFactory] = {}

    def register_awg(self, model: str, factory: AwgAdapterFactory) -> None:
        get_capability(model, InstrumentRole.AWG, include_test=True)
        self._awg_factories[model] = factory

    def register_osc(self, model: str, factory: OscAdapterFactory) -> None:
        get_capability(model, InstrumentRole.OSC, include_test=True)
        self._osc_factories[model] = factory

    def create_awg(self, *, model: str, address: str) -> AwgPort:
        try:
            factory = self._awg_factories[model]
        except KeyError as exc:
            raise ValueError(f"No AWG adapter registered for model: {model}") from exc
        return factory(model, address)

    def create_osc(self, *, model: str, address: str) -> OscPort:
        try:
            factory = self._osc_factories[model]
        except KeyError as exc:
            raise ValueError(f"No OSC adapter registered for model: {model}") from exc
        return factory(model, address)

    def create_ports(self, *, setup: InstrumentSetup, awg_address: str, osc_address: str) -> InstrumentPorts:
        awg = self.create_awg(model=setup.awg.model, address=awg_address)
        osc = self.create_osc(model=setup.osc.model, address=osc_address)
        return InstrumentPorts(awg=awg, osc=osc, awg_address=awg_address, osc_address=osc_address)


def build_production_adapter_registry() -> AdapterRegistry:
    registry = AdapterRegistry()
    for model in ("DSG4102", "DSG836"):
        registry.register_awg(model, lambda registered_model, address: EquipsAwgAdapter(registered_model, address))
    for model in ("MDO34", "MDO3024", "DHO1202", "DHO1204"):
        registry.register_osc(model, lambda registered_model, address: EquipsOscAdapter(registered_model, address))
    return registry


def build_mock_adapter_registry() -> AdapterRegistry:
    registry = AdapterRegistry()
    awg = MockAwgAdapter()
    registry.register_awg("MOCK_AWG", lambda _model, _address: awg)
    registry.register_osc("MOCK_OSC", lambda _model, _address: MockOscAdapter(awg))
    return registry
