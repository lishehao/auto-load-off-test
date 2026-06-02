from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.enums import ConnectionMode, CouplingMode, ImpedanceMode, TriggerMode


class InstrumentRole(str, Enum):
    AWG = "awg"
    OSC = "osc"


class ValidationStatus(str, Enum):
    LEGACY_SUPPORTED = "legacy_supported"
    SOFTWARE_PROFILE = "software_profile"
    TEST_ONLY = "test_only"


@dataclass(frozen=True, slots=True)
class NumericLimit:
    minimum: float | None = None
    maximum: float | None = None
    unit: str = ""
    source: str = "not specified"

    def contains(self, value: float) -> bool:
        if self.minimum is not None and value < self.minimum:
            return False
        if self.maximum is not None and value > self.maximum:
            return False
        return True


@dataclass(frozen=True, slots=True)
class InstrumentCapability:
    model: str
    role: InstrumentRole
    channel_count: int
    supported_impedances: frozenset[ImpedanceMode]
    supported_couplings: frozenset[CouplingMode] = frozenset()
    supported_trigger_modes: frozenset[TriggerMode] = frozenset()
    transports: frozenset[ConnectionMode] = frozenset((ConnectionMode.AUTO, ConnectionMode.LAN))
    frequency_hz: NumericLimit = NumericLimit(unit="Hz")
    amplitude_vpp: NumericLimit = NumericLimit(unit="Vpp")
    osc_full_scale_v: NumericLimit = NumericLimit(unit="V")
    timeout_s: float = 15.0
    validation_status: ValidationStatus = ValidationStatus.SOFTWARE_PROFILE
    validation_source: str = "software profile; not live-hardware validation"
    safety_notes: tuple[str, ...] = ()
    visible_in_ui: bool = True


_CURRENT_PRODUCTION_CAPABILITIES: tuple[InstrumentCapability, ...] = (
    InstrumentCapability(
        model="DSG4102",
        role=InstrumentRole.AWG,
        channel_count=2,
        frequency_hz=NumericLimit(minimum=1e-6, maximum=100e6, unit="Hz", source="legacy driver/default sweep profile"),
        amplitude_vpp=NumericLimit(minimum=0.001, maximum=10.0, unit="Vpp", source="conservative software preflight"),
        supported_impedances=frozenset((ImpedanceMode.R50, ImpedanceMode.HIGH_Z)),
        validation_status=ValidationStatus.LEGACY_SUPPORTED,
        validation_source="legacy equips.py DG4102-compatible adapter; bench revalidation recommended",
        safety_notes=(
            "Software label maps to the legacy DG4102-compatible driver path.",
            "Confirm real front-panel limits before live sweeps.",
        ),
    ),
    InstrumentCapability(
        model="DSG836",
        role=InstrumentRole.AWG,
        channel_count=1,
        supported_impedances=frozenset((ImpedanceMode.R50,)),
        validation_status=ValidationStatus.LEGACY_SUPPORTED,
        validation_source="legacy equips.py RF-generator adapter; frequency/amplitude limits require bench/manual confirmation",
        safety_notes=(
            "Single-channel RF generator path; channel selection is ignored by the legacy adapter.",
            "Keep output-level assumptions conservative until bench-validated.",
        ),
    ),
    InstrumentCapability(
        model="MDO34",
        role=InstrumentRole.OSC,
        channel_count=4,
        supported_impedances=frozenset((ImpedanceMode.R50, ImpedanceMode.HIGH_Z)),
        supported_couplings=frozenset((CouplingMode.AC, CouplingMode.DC)),
        supported_trigger_modes=frozenset((TriggerMode.FREE_RUN, TriggerMode.TRIGGERED)),
        validation_status=ValidationStatus.LEGACY_SUPPORTED,
        validation_source="legacy equips.py Tektronix MDO3 adapter path",
        safety_notes=("Verify probe attenuation, termination, and range before live acquisition.",),
    ),
    InstrumentCapability(
        model="MDO3024",
        role=InstrumentRole.OSC,
        channel_count=4,
        supported_impedances=frozenset((ImpedanceMode.R50, ImpedanceMode.HIGH_Z)),
        supported_couplings=frozenset((CouplingMode.AC, CouplingMode.DC)),
        supported_trigger_modes=frozenset((TriggerMode.FREE_RUN, TriggerMode.TRIGGERED)),
        validation_status=ValidationStatus.LEGACY_SUPPORTED,
        validation_source="legacy equips.py Tektronix MDO3 adapter path",
        safety_notes=("Verify probe attenuation, termination, and range before live acquisition.",),
    ),
    InstrumentCapability(
        model="DHO1202",
        role=InstrumentRole.OSC,
        channel_count=2,
        supported_impedances=frozenset((ImpedanceMode.HIGH_Z,)),
        supported_couplings=frozenset((CouplingMode.AC, CouplingMode.DC)),
        supported_trigger_modes=frozenset((TriggerMode.FREE_RUN, TriggerMode.TRIGGERED)),
        validation_status=ValidationStatus.LEGACY_SUPPORTED,
        validation_source="legacy equips.py DHO1000 adapter; code path documents 1 MOhm-only termination",
        safety_notes=("DHO1000 series adapter treats termination as 1 MOhm only; do not select 50 ohm.",),
    ),
    InstrumentCapability(
        model="DHO1204",
        role=InstrumentRole.OSC,
        channel_count=4,
        supported_impedances=frozenset((ImpedanceMode.HIGH_Z,)),
        supported_couplings=frozenset((CouplingMode.AC, CouplingMode.DC)),
        supported_trigger_modes=frozenset((TriggerMode.FREE_RUN, TriggerMode.TRIGGERED)),
        validation_status=ValidationStatus.LEGACY_SUPPORTED,
        validation_source="legacy equips.py DHO1000 adapter; code path documents 1 MOhm-only termination",
        safety_notes=("DHO1000 series adapter treats termination as 1 MOhm only; do not select 50 ohm.",),
    ),
)


_TEST_CAPABILITIES: tuple[InstrumentCapability, ...] = (
    InstrumentCapability(
        model="MOCK_AWG",
        role=InstrumentRole.AWG,
        channel_count=2,
        frequency_hz=NumericLimit(minimum=1.0, maximum=10e6, unit="Hz", source="test fake"),
        amplitude_vpp=NumericLimit(minimum=0.001, maximum=5.0, unit="Vpp", source="test fake"),
        supported_impedances=frozenset((ImpedanceMode.R50, ImpedanceMode.HIGH_Z)),
        validation_status=ValidationStatus.TEST_ONLY,
        validation_source="hardware-free fake adapter",
        safety_notes=("Test-only profile; never present as live hardware.",),
        visible_in_ui=False,
    ),
    InstrumentCapability(
        model="MOCK_OSC",
        role=InstrumentRole.OSC,
        channel_count=4,
        supported_impedances=frozenset((ImpedanceMode.R50, ImpedanceMode.HIGH_Z)),
        supported_couplings=frozenset((CouplingMode.AC, CouplingMode.DC)),
        supported_trigger_modes=frozenset((TriggerMode.FREE_RUN, TriggerMode.TRIGGERED)),
        validation_status=ValidationStatus.TEST_ONLY,
        validation_source="hardware-free fake adapter",
        safety_notes=("Test-only profile; never present as live hardware.",),
        visible_in_ui=False,
    ),
)


ALL_CAPABILITIES: tuple[InstrumentCapability, ...] = _CURRENT_PRODUCTION_CAPABILITIES + _TEST_CAPABILITIES


def capabilities_for_role(
    role: InstrumentRole,
    *,
    include_test: bool = False,
    visible_only: bool = True,
) -> tuple[InstrumentCapability, ...]:
    capabilities = []
    for capability in ALL_CAPABILITIES:
        if capability.role != role:
            continue
        if capability.validation_status == ValidationStatus.TEST_ONLY and not include_test:
            continue
        if visible_only and not capability.visible_in_ui:
            continue
        capabilities.append(capability)
    return tuple(capabilities)


def model_names_for_role(role: InstrumentRole, *, include_test: bool = False) -> tuple[str, ...]:
    return tuple(
        capability.model
        for capability in capabilities_for_role(
            role,
            include_test=include_test,
            visible_only=not include_test,
        )
    )


def get_capability(model: str, role: InstrumentRole | None = None, *, include_test: bool = False) -> InstrumentCapability:
    for capability in ALL_CAPABILITIES:
        if capability.model != model:
            continue
        if role is not None and capability.role != role:
            continue
        if capability.validation_status == ValidationStatus.TEST_ONLY and not include_test:
            break
        return capability
    role_text = f" {role.value}" if role is not None else ""
    raise ValueError(f"Unsupported{role_text} model: {model}")


def is_supported_model(model: str, role: InstrumentRole | None = None, *, include_test: bool = False) -> bool:
    try:
        get_capability(model, role, include_test=include_test)
    except ValueError:
        return False
    return True
