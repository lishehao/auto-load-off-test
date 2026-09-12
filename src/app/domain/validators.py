from __future__ import annotations

import math

from app.domain.enums import CorrectionMode, CouplingMode, ImpedanceMode, TriggerMode
from app.domain.instrument_capabilities import InstrumentCapability, InstrumentRole, get_capability
from app.domain.models import AppSettings, ChannelSelection, OscSettings, SweepSpec
from app.domain.sweep_engine import MAX_SWEEP_POINTS, estimate_linear_sweep_points


class ValidationError(ValueError):
    pass


# Software guards prevent accidental giant allocations; they do not claim
# hardware capability limits.
MAX_CAPTURE_POINTS = 10_000_000


def validate_sweep_spec(spec: SweepSpec) -> None:
    start_hz = _finite_number("start_hz", spec.start_hz)
    stop_hz = _finite_number("stop_hz", spec.stop_hz)
    if start_hz <= 0:
        raise ValidationError("start_hz must be > 0")
    if stop_hz <= 0:
        raise ValidationError("stop_hz must be > 0")
    if stop_hz < start_hz:
        raise ValidationError("stop_hz must be >= start_hz")

    if spec.is_log:
        if spec.step_count is None:
            raise ValidationError("step_count must be > 0 for logarithmic sweep")
        step_count = _positive_integer("step_count", spec.step_count)
        if step_count > MAX_SWEEP_POINTS:
            raise ValidationError(f"step_count exceeds software guard MAX_SWEEP_POINTS={MAX_SWEEP_POINTS}")
    else:
        if spec.step_hz is None:
            raise ValidationError("step_hz must be > 0 for linear sweep")
        step_hz = _finite_number("step_hz", spec.step_hz)
        if step_hz <= 0:
            raise ValidationError("step_hz must be > 0 for linear sweep")
        estimated = estimate_linear_sweep_points(start_hz, stop_hz, step_hz)
        if estimated > MAX_SWEEP_POINTS:
            raise ValidationError(
                f"sweep has {estimated} points, exceeding software guard "
                f"MAX_SWEEP_POINTS={MAX_SWEEP_POINTS}"
            )


def validate_channels(channels: ChannelSelection, correction_mode: CorrectionMode, trigger_mode: TriggerMode) -> None:
    _positive_integer("awg_ch", channels.awg_ch)
    _positive_integer("osc_test_ch", channels.osc_test_ch)
    for name, value in (("osc_ref_ch", channels.osc_ref_ch), ("osc_trig_ch", channels.osc_trig_ch)):
        if value is not None:
            _positive_integer(name, value)

    if correction_mode == CorrectionMode.DUAL and channels.osc_ref_ch is None:
        raise ValidationError("osc_ref_ch is required for dual correction")
    if trigger_mode == TriggerMode.TRIGGERED and channels.osc_trig_ch is None:
        raise ValidationError("osc_trig_ch is required for triggered mode")


def validate_osc_settings(settings: OscSettings) -> None:
    points = _positive_integer("osc points", settings.points)
    if points <= 1:
        raise ValidationError("osc points must be > 1")
    if points > MAX_CAPTURE_POINTS:
        raise ValidationError(f"osc points exceeds software guard MAX_CAPTURE_POINTS={MAX_CAPTURE_POINTS}")
    full_scale_v = _finite_number("osc full_scale_v", settings.full_scale_v)
    _finite_number("osc offset_v", settings.offset_v)
    if full_scale_v <= 0:
        raise ValidationError("osc full_scale_v must be > 0")

    if settings.impedance == ImpedanceMode.R50 and settings.coupling == CouplingMode.AC:
        raise ValidationError("50-ohm impedance does not support AC coupling")


def validate_capabilities(settings: AppSettings, *, include_test: bool = False) -> None:
    setup = settings.setup
    run_mode = settings.run_mode

    awg_capability = get_capability(setup.awg.model, InstrumentRole.AWG, include_test=include_test)
    osc_capability = get_capability(setup.osc.model, InstrumentRole.OSC, include_test=include_test)

    _validate_transport("AWG", setup.awg.connect_mode, awg_capability)
    _validate_transport("OSC", setup.osc.connect_mode, osc_capability)

    if setup.channels.awg_ch > awg_capability.channel_count:
        raise ValidationError(f"AWG channel {setup.channels.awg_ch} exceeds {setup.awg.model} channel count")
    for label, channel in (
        ("test", setup.channels.osc_test_ch),
        ("reference", setup.channels.osc_ref_ch),
        ("trigger", setup.channels.osc_trig_ch),
    ):
        if channel is not None and channel > osc_capability.channel_count:
            raise ValidationError(f"OSC {label} channel {channel} exceeds {setup.osc.model} channel count")

    if setup.awg_settings.impedance not in awg_capability.supported_impedances:
        raise ValidationError(
            f"{setup.awg.model} does not support AWG impedance {setup.awg_settings.impedance.value}"
        )
    if setup.osc_settings.impedance not in osc_capability.supported_impedances:
        raise ValidationError(
            f"{setup.osc.model} does not support OSC impedance {setup.osc_settings.impedance.value}"
        )
    if setup.osc_settings.coupling not in osc_capability.supported_couplings:
        raise ValidationError(
            f"{setup.osc.model} does not support OSC coupling {setup.osc_settings.coupling.value}"
        )
    if run_mode.trigger_mode not in osc_capability.supported_trigger_modes:
        raise ValidationError(f"{setup.osc.model} does not support trigger mode {run_mode.trigger_mode.value}")

    _validate_limit("start frequency", settings.sweep.start_hz, awg_capability.frequency_hz, setup.awg.model)
    _validate_limit("stop frequency", settings.sweep.stop_hz, awg_capability.frequency_hz, setup.awg.model)
    _validate_limit("AWG amplitude", setup.awg_settings.amplitude_vpp, awg_capability.amplitude_vpp, setup.awg.model)
    _validate_limit("OSC full-scale range", setup.osc_settings.full_scale_v, osc_capability.osc_full_scale_v, setup.osc.model)


def validate_settings(settings: AppSettings, *, include_test: bool = False) -> None:
    if _finite_number("AWG amplitude", settings.setup.awg_settings.amplitude_vpp) <= 0:
        raise ValidationError("AWG amplitude must be > 0")
    validate_sweep_spec(settings.sweep)
    validate_osc_settings(settings.setup.osc_settings)
    validate_channels(
        settings.setup.channels,
        settings.run_mode.correction_mode,
        settings.run_mode.trigger_mode,
    )
    validate_capabilities(settings, include_test=include_test)


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{name} must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{name} must be finite") from exc
    if not math.isfinite(number):
        raise ValidationError(f"{name} must be finite")
    return number


def _positive_integer(name: str, value: object) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{name} must be an integer")
    number = _finite_number(name, value)
    if not number.is_integer():
        raise ValidationError(f"{name} must be an integer")
    integer = int(number)
    if integer <= 0:
        raise ValidationError(f"{name} must be > 0")
    return integer


def _validate_transport(label: str, mode, capability: InstrumentCapability) -> None:
    if mode not in capability.transports:
        raise ValidationError(f"{capability.model} does not support {label} connection mode {mode.value}")


def _validate_limit(label: str, value: float, limit, model: str) -> None:
    _finite_number(label, value)
    if limit.minimum is None and limit.maximum is None:
        return
    if limit.contains(float(value)):
        return

    lower = "-inf" if limit.minimum is None else f"{limit.minimum:g}"
    upper = "inf" if limit.maximum is None else f"{limit.maximum:g}"
    unit = f" {limit.unit}" if limit.unit else ""
    raise ValidationError(f"{model} {label} {value:g}{unit} outside supported range {lower}..{upper}{unit}")
