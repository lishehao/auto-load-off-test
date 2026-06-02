from __future__ import annotations

from app.domain.enums import CorrectionMode, CouplingMode, ImpedanceMode, TriggerMode
from app.domain.instrument_capabilities import InstrumentCapability, InstrumentRole, get_capability
from app.domain.models import AppSettings, ChannelSelection, OscSettings, SweepSpec


class ValidationError(ValueError):
    pass


def validate_sweep_spec(spec: SweepSpec) -> None:
    if spec.start_hz <= 0:
        raise ValidationError("start_hz must be > 0")
    if spec.stop_hz <= 0:
        raise ValidationError("stop_hz must be > 0")
    if spec.stop_hz < spec.start_hz:
        raise ValidationError("stop_hz must be >= start_hz")

    if spec.is_log:
        if not spec.step_count or spec.step_count <= 0:
            raise ValidationError("step_count must be > 0 for logarithmic sweep")
    else:
        if not spec.step_hz or spec.step_hz <= 0:
            raise ValidationError("step_hz must be > 0 for linear sweep")


def validate_channels(channels: ChannelSelection, correction_mode: CorrectionMode, trigger_mode: TriggerMode) -> None:
    if channels.awg_ch <= 0 or channels.osc_test_ch <= 0:
        raise ValidationError("Channel index must be positive")

    if correction_mode == CorrectionMode.DUAL and not channels.osc_ref_ch:
        raise ValidationError("osc_ref_ch is required for dual correction")
    if trigger_mode == TriggerMode.TRIGGERED and not channels.osc_trig_ch:
        raise ValidationError("osc_trig_ch is required for triggered mode")


def validate_osc_settings(settings: OscSettings) -> None:
    if settings.points <= 1:
        raise ValidationError("osc points must be > 1")
    if settings.full_scale_v <= 0:
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
    validate_sweep_spec(settings.sweep)
    validate_osc_settings(settings.setup.osc_settings)
    validate_channels(
        settings.setup.channels,
        settings.run_mode.correction_mode,
        settings.run_mode.trigger_mode,
    )
    validate_capabilities(settings, include_test=include_test)


def _validate_transport(label: str, mode, capability: InstrumentCapability) -> None:
    if mode not in capability.transports:
        raise ValidationError(f"{capability.model} does not support {label} connection mode {mode.value}")


def _validate_limit(label: str, value: float, limit, model: str) -> None:
    if limit.minimum is None and limit.maximum is None:
        return
    if limit.contains(float(value)):
        return

    lower = "-inf" if limit.minimum is None else f"{limit.minimum:g}"
    upper = "inf" if limit.maximum is None else f"{limit.maximum:g}"
    unit = f" {limit.unit}" if limit.unit else ""
    raise ValidationError(f"{model} {label} {value:g}{unit} outside supported range {lower}..{upper}{unit}")
