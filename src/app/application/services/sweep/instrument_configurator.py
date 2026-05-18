from __future__ import annotations

from app.application.ports.instruments import AwgPort, OscPort
from app.domain.enums import CorrectionMode, TriggerMode
from app.domain.models import AppSettings


class InstrumentConfigurator:
    def __init__(self, awg: AwgPort, osc: OscPort) -> None:
        self._awg = awg
        self._osc = osc

    def configure(self, settings: AppSettings) -> None:
        setup = settings.setup
        run_mode = settings.run_mode

        awg_ch = setup.channels.awg_ch
        test_ch = setup.channels.osc_test_ch

        if run_mode.auto_reset:
            self._awg.reset()
            self._osc.reset()

        self._awg.output_off(awg_ch)
        self._awg.set_impedance(setup.awg_settings.impedance.value, awg_ch)
        self._awg.set_amplitude_vpp(setup.awg_settings.amplitude_vpp, awg_ch)

        self._osc.output_on(test_ch)
        self._osc.set_coupling(test_ch, setup.osc_settings.coupling.value)
        self._osc.set_impedance(test_ch, setup.osc_settings.impedance.value)
        self._osc.set_vertical(test_ch, setup.osc_settings.full_scale_v, setup.osc_settings.offset_v)

        if run_mode.correction_mode == CorrectionMode.DUAL and setup.channels.osc_ref_ch:
            ref_ch = setup.channels.osc_ref_ch
            self._osc.output_on(ref_ch)
            self._osc.set_coupling(ref_ch, setup.osc_settings.coupling.value)
            self._osc.set_impedance(ref_ch, setup.osc_settings.impedance.value)
            self._osc.set_vertical(ref_ch, setup.osc_settings.full_scale_v, setup.osc_settings.offset_v)

        if run_mode.trigger_mode == TriggerMode.TRIGGERED:
            trig_ch = int(setup.channels.osc_trig_ch or test_ch)
            self._osc.output_on(trig_ch)
            self._osc.arm_trigger(trig_ch, level_v=0.0)
        else:
            self._osc.set_free_run()
