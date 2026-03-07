from __future__ import annotations

from app.application.services.sweep.models import AcquiredPointData
from app.domain.enums import CorrectionMode, TriggerMode
from app.domain.models import AppSettings, SweepPoint
from app.domain.signal_processing import calc_vin_peak, measure_dual_channel, measure_single_channel


class PointMeasurementService:
    def measure(self, *, settings: AppSettings, acquired: AcquiredPointData) -> SweepPoint:
        setup = settings.setup
        run_mode = settings.run_mode

        if run_mode.correction_mode == CorrectionMode.DUAL:
            gain_linear, gain_db, phase_deg, gain_complex = measure_dual_channel(
                acquired.test_times,
                acquired.test_volts,
                acquired.ref_times if acquired.ref_times is not None else acquired.test_times,
                acquired.ref_volts if acquired.ref_volts is not None else acquired.test_volts,
                acquired.actual_freq_hz,
            )
        else:
            vin_peak = calc_vin_peak(
                vpp_panel=acquired.read_amp_vpp,
                awg_impedance=setup.awg_settings.impedance.value,
                osc_impedance=setup.osc_settings.impedance.value,
            )
            gain_linear, gain_db, phase_deg, gain_complex = measure_single_channel(
                acquired.test_times,
                acquired.test_volts,
                acquired.actual_freq_hz,
                vin_peak,
                compute_phase=run_mode.trigger_mode == TriggerMode.TRIGGERED,
            )

        return SweepPoint(
            freq_hz=float(acquired.actual_freq_hz),
            gain_linear=float(gain_linear),
            gain_db=float(gain_db),
            phase_deg=float(phase_deg) if phase_deg is not None else None,
            gain_complex=complex(gain_complex) if gain_complex is not None else None,
        )
