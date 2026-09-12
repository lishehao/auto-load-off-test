from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

from app.shared.cvt_tools import CvtTools

from app.domain.enums import (
    ConnectionMode,
    CorrectionMode,
    CouplingMode,
    ImpedanceMode,
    MagnitudePhaseMode,
    TriggerMode,
)
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
if TYPE_CHECKING:
    from app.presentation.tk.view_model import ViewModel


def _safe_int(value: str, default: int | None = None) -> int:
    """Parse an integer control without silently replacing invalid input."""
    del default  # Kept for callers of the legacy helper.
    text = str(value).strip()
    if re.fullmatch(r"[+-]?\d+", text) is None:
        raise ValueError(f"Expected integer value, got {value!r}")
    try:
        return int(text, 10)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Expected integer value, got {value!r}") from exc


def _optional_int(value: str) -> int | None:
    text = str(value).strip()
    return None if not text else _safe_int(text)


def _finite_float(name: str, value: str, parser) -> float:
    text = str(value).strip()
    if re.search(r"\d", text) is None:
        raise ValueError(f"Expected finite numeric value for {name}, got {value!r}")
    try:
        parsed = float(parser(text))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Expected finite numeric value for {name}, got {value!r}") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"Expected finite numeric value for {name}, got {value!r}")
    return parsed



def vm_to_settings(vm: ViewModel) -> AppSettings:
    freq_unit = vm.freq_unit.get()
    is_log = bool(vm.is_log.get())

    start_hz = _finite_float(
        "start_freq", vm.start_freq.get(), lambda text: CvtTools.parse_to_hz(text, freq_unit)
    )
    stop_hz = _finite_float(
        "stop_freq", vm.stop_freq.get(), lambda text: CvtTools.parse_to_hz(text, freq_unit)
    )

    step_hz = (
        None
        if is_log
        else _finite_float(
            "step_freq", vm.step_freq.get(), lambda text: CvtTools.parse_to_hz(text, freq_unit)
        )
    )
    step_count = _safe_int(vm.step_count.get()) if is_log else None

    correction_mode = CorrectionMode(vm.correction_mode.get())
    trigger_mode = TriggerMode(vm.trigger_mode.get())

    return AppSettings(
        schema_version=1,
        freq_unit=freq_unit,
        sweep=SweepSpec(
            start_hz=start_hz,
            stop_hz=stop_hz,
            step_hz=step_hz,
            step_count=step_count,
            is_log=is_log,
        ),
        run_mode=RunMode(
            correction_mode=correction_mode,
            trigger_mode=trigger_mode,
            auto_range=bool(vm.auto_range.get()),
            auto_reset=bool(vm.auto_reset.get()),
        ),
        setup=InstrumentSetup(
            awg=InstrumentEndpoint(
                model=vm.awg_model.get(),
                connect_mode=ConnectionMode(vm.awg_connect_mode.get()),
                visa_address=vm.awg_visa.get().strip(),
                ip_address=vm.awg_ip.get().strip(),
            ),
            osc=InstrumentEndpoint(
                model=vm.osc_model.get(),
                connect_mode=ConnectionMode(vm.osc_connect_mode.get()),
                visa_address=vm.osc_visa.get().strip(),
                ip_address=vm.osc_ip.get().strip(),
            ),
            channels=ChannelSelection(
                awg_ch=_safe_int(vm.awg_ch.get(), 1),
                osc_test_ch=_safe_int(vm.osc_test_ch.get(), 1),
                osc_ref_ch=_optional_int(vm.osc_ref_ch.get()),
                osc_trig_ch=_optional_int(vm.osc_trig_ch.get()),
            ),
            awg_settings=AwgSettings(
                amplitude_vpp=_finite_float("awg_amp", vm.awg_amp.get(), CvtTools.parse_to_Vpp),
                impedance=ImpedanceMode(vm.awg_imp.get()),
            ),
            osc_settings=OscSettings(
                full_scale_v=_finite_float("osc_range", vm.osc_range.get(), CvtTools.parse_to_V),
                offset_v=_finite_float("osc_offset", vm.osc_offset.get(), CvtTools.parse_to_V),
                points=_safe_int(vm.osc_points.get()),
                impedance=ImpedanceMode(vm.osc_imp.get()),
                coupling=CouplingMode(vm.osc_coupling.get()),
            ),
        ),
        magnitude_phase_mode=MagnitudePhaseMode(vm.magnitude_phase_mode.get()),
        auto_save_data=bool(vm.auto_save_data.get()),
    )



def settings_to_vm(settings: AppSettings, vm: ViewModel) -> None:
    vm.freq_unit.set(settings.freq_unit)

    scale = CvtTools.convert_general_unit(settings.freq_unit)
    vm.start_freq.set(str(round(settings.sweep.start_hz / scale, 6)))
    vm.stop_freq.set(str(round(settings.sweep.stop_hz / scale, 6)))
    if settings.sweep.step_hz is not None:
        vm.step_freq.set(str(round(settings.sweep.step_hz / scale, 6)))
    vm.step_count.set(str(settings.sweep.step_count or 100))
    vm.is_log.set(settings.sweep.is_log)

    vm.awg_model.set(settings.setup.awg.model)
    vm.osc_model.set(settings.setup.osc.model)
    vm.awg_connect_mode.set(settings.setup.awg.connect_mode.value)
    vm.osc_connect_mode.set(settings.setup.osc.connect_mode.value)
    vm.awg_visa.set(settings.setup.awg.visa_address)
    vm.osc_visa.set(settings.setup.osc.visa_address)
    vm.awg_ip.set(settings.setup.awg.ip_address)
    vm.osc_ip.set(settings.setup.osc.ip_address)

    vm.awg_amp.set(str(settings.setup.awg_settings.amplitude_vpp))
    vm.awg_imp.set(settings.setup.awg_settings.impedance.value)

    vm.osc_range.set(str(settings.setup.osc_settings.full_scale_v))
    vm.osc_offset.set(str(settings.setup.osc_settings.offset_v))
    vm.osc_points.set(str(settings.setup.osc_settings.points))
    vm.osc_imp.set(settings.setup.osc_settings.impedance.value)
    vm.osc_coupling.set(settings.setup.osc_settings.coupling.value)

    vm.awg_ch.set(str(settings.setup.channels.awg_ch))
    vm.osc_test_ch.set(str(settings.setup.channels.osc_test_ch))
    vm.osc_ref_ch.set(str(settings.setup.channels.osc_ref_ch or 2))
    vm.osc_trig_ch.set(str(settings.setup.channels.osc_trig_ch or 2))

    vm.correction_mode.set(settings.run_mode.correction_mode.value)
    vm.trigger_mode.set(settings.run_mode.trigger_mode.value)
    vm.auto_range.set(settings.run_mode.auto_range)
    vm.auto_reset.set(settings.run_mode.auto_reset)

    vm.magnitude_phase_mode.set(settings.magnitude_phase_mode.value)
    vm.auto_save_data.set(settings.auto_save_data)
