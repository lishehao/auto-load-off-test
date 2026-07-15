from __future__ import annotations

from app.application.ports.instruments import InstrumentPorts
from app.domain.enums import ConnectionMode
from app.domain.models import InstrumentEndpoint, InstrumentSetup
from app.infrastructure.instruments.adapter_registry import AdapterRegistry, build_production_adapter_registry


_PRODUCTION_REGISTRY: AdapterRegistry | None = None


def resolve_visa_address(endpoint: InstrumentEndpoint) -> str:
    if endpoint.connect_mode == ConnectionMode.LAN and endpoint.ip_address.strip():
        return f"TCPIP0::{endpoint.ip_address.strip()}::INSTR"
    return endpoint.visa_address.strip()



def create_instrument_ports(setup: InstrumentSetup) -> InstrumentPorts:
    return create_instrument_ports_with_registry(setup=setup, registry=_production_registry())


def create_instrument_ports_with_registry(setup: InstrumentSetup, registry: AdapterRegistry) -> InstrumentPorts:
    awg_address = resolve_visa_address(setup.awg)
    osc_address = resolve_visa_address(setup.osc)
    return registry.create_ports(setup=setup, awg_address=awg_address, osc_address=osc_address)


def _production_registry() -> AdapterRegistry:
    global _PRODUCTION_REGISTRY
    if _PRODUCTION_REGISTRY is None:
        _PRODUCTION_REGISTRY = build_production_adapter_registry()
    return _PRODUCTION_REGISTRY
