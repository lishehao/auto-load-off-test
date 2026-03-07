from __future__ import annotations

import numpy as np

from app.application.ports.instruments import AwgPort, OscPort
from app.application.services.sweep.models import AcquiredPointData, SweepServiceWarning
from app.application.services.sweep.planner import SweepPlanner
from app.domain.auto_range import AutoRangePolicy
from app.domain.enums import CorrectionMode, TriggerMode
from app.domain.models import AppSettings


class WaveformAcquirer:
    def __init__(
        self,
        awg: AwgPort,
        osc: OscPort,
        planner: SweepPlanner,
        auto_range_policy: AutoRangePolicy,
    ) -> None:
        self._awg = awg
        self._osc = osc
        self._planner = planner
        self._auto_range_policy = auto_range_policy

    def acquire(self, *, target_freq_hz: float, settings: AppSettings) -> AcquiredPointData:
        setup = settings.setup
        run_mode = settings.run_mode

        warnings: list[SweepServiceWarning] = []
        awg_ch = setup.channels.awg_ch
        self._awg.set_frequency(float(target_freq_hz), awg_ch)
        actual_freq = self._awg.get_frequency(awg_ch)
        if not np.isclose(actual_freq, target_freq_hz, atol=1e-3, rtol=5e-6):
            warnings.append(
                SweepServiceWarning(
                    code="FREQ_MISMATCH",
                    message=f"Requested {target_freq_hz:.6f} Hz, actual {actual_freq:.6f} Hz",
                )
            )

        requested_amp = float(setup.awg_settings.amplitude_vpp)
        read_amp = self._awg.get_amplitude_vpp(awg_ch)
        if not np.isclose(read_amp, requested_amp, atol=1e-2, rtol=1e-3):
            warnings.append(
                SweepServiceWarning(
                    code="AMP_MISMATCH",
                    message=f"Requested {requested_amp:.6f} Vpp, actual {read_amp:.6f} Vpp",
                )
            )

        sample_rate = self._osc.get_sample_rate()
        window_s = self._planner.compute_sampling_window_s(
            freq_hz=actual_freq,
            sample_rate_hz=sample_rate,
            points=setup.osc_settings.points,
        )

        self._osc.set_timebase(window_s)
        triggered = run_mode.trigger_mode == TriggerMode.TRIGGERED
        self._osc.single_acquire(triggered=triggered)

        test_ch = setup.channels.osc_test_ch
        times_t, volts_t = self._osc.read_waveform(test_ch, setup.osc_settings.points)

        if run_mode.auto_range:
            current_range, current_offset = self._osc.get_vertical(test_ch)
            decision = self._auto_range_policy.decide(
                volts=volts_t,
                current_range_v=current_range,
                current_offset_v=current_offset,
                requested_offset_v=setup.osc_settings.offset_v,
            )
            if decision.changed:
                self._osc.set_vertical(test_ch, decision.target_range_v, decision.target_offset_v)
                self._osc.single_acquire(triggered=triggered)
                times_t, volts_t = self._osc.read_waveform(test_ch, setup.osc_settings.points)

        ref_times = None
        ref_volts = None
        if run_mode.correction_mode == CorrectionMode.DUAL:
            ref_ch = int(setup.channels.osc_ref_ch or test_ch)
            ref_times, ref_volts = self._osc.read_waveform(ref_ch, setup.osc_settings.points)

        return AcquiredPointData(
            actual_freq_hz=float(actual_freq),
            read_amp_vpp=float(read_amp),
            test_times=np.asarray(times_t, dtype=float),
            test_volts=np.asarray(volts_t, dtype=float),
            ref_times=None if ref_times is None else np.asarray(ref_times, dtype=float),
            ref_volts=None if ref_volts is None else np.asarray(ref_volts, dtype=float),
            warnings=warnings,
        )
