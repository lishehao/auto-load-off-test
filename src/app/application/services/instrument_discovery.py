from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.application.ports.instruments import InstrumentIdentityProbePort, ResourceScannerPort
from app.domain.instrument_capabilities import InstrumentRole, get_capability
from app.domain.models import InstrumentEndpoint, InstrumentSetup


@dataclass(frozen=True, slots=True)
class ResourceScan:
    resources: tuple[str, ...]
    scanned_at: str


@dataclass(frozen=True, slots=True)
class ConnectionCheck:
    role: InstrumentRole
    model: str
    address: str
    status: str
    message: str
    idn: str = ""
    backend: str = "pyvisa"
    last_seen: str = ""


class InstrumentDiscoveryService:
    def __init__(
        self,
        *,
        scanner: ResourceScannerPort,
        identity_probe: InstrumentIdentityProbePort,
        timeout_ms: int = 2_000,
    ) -> None:
        self._scanner = scanner
        self._identity_probe = identity_probe
        self._timeout_ms = timeout_ms

    def scan_resources(self) -> ResourceScan:
        resources = self._scanner.list_resources()
        return ResourceScan(resources=resources, scanned_at=_timestamp())

    def test_setup(self, setup: InstrumentSetup, resolve_address) -> tuple[ConnectionCheck, ConnectionCheck]:
        return (
            self.test_endpoint(
                role=InstrumentRole.AWG,
                endpoint=setup.awg,
                address=resolve_address(setup.awg),
            ),
            self.test_endpoint(
                role=InstrumentRole.OSC,
                endpoint=setup.osc,
                address=resolve_address(setup.osc),
            ),
        )

    def test_endpoint(self, *, role: InstrumentRole, endpoint: InstrumentEndpoint, address: str) -> ConnectionCheck:
        if not address:
            return ConnectionCheck(
                role=role,
                model=endpoint.model,
                address="",
                status="address_empty",
                message=f"{role.value.upper()} address empty",
            )

        try:
            capability = get_capability(endpoint.model, role)
        except ValueError:
            return ConnectionCheck(
                role=role,
                model=endpoint.model,
                address=address,
                status="unsupported_model",
                message=f"Unsupported {role.value.upper()} model: {endpoint.model}",
            )

        if endpoint.connect_mode not in capability.transports:
            return ConnectionCheck(
                role=role,
                model=endpoint.model,
                address=address,
                status="unsupported_transport",
                message=f"{endpoint.model} does not support {endpoint.connect_mode.value} connection mode",
            )

        try:
            idn = self._identity_probe.identify(address, timeout_ms=self._timeout_ms)
        except Exception as exc:  # noqa: BLE001
            return ConnectionCheck(
                role=role,
                model=endpoint.model,
                address=address,
                status="offline",
                message=f"{role.value.upper()} offline or unreachable: {exc}",
            )

        return ConnectionCheck(
            role=role,
            model=endpoint.model,
            address=address,
            status="connected",
            message=f"{role.value.upper()} connected: {idn}",
            idn=idn,
            last_seen=_timestamp(),
        )


def format_scan_receipt(scan: ResourceScan, *, limit: int = 4) -> str:
    if not scan.resources:
        return f"No VISA resources found · {scan.scanned_at}"
    visible = ", ".join(scan.resources[:limit])
    suffix = "" if len(scan.resources) <= limit else f", +{len(scan.resources) - limit} more"
    return f"{len(scan.resources)} VISA resources · {visible}{suffix}"


def format_connection_receipt(checks: tuple[ConnectionCheck, ...]) -> str:
    return " | ".join(check.message for check in checks)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
