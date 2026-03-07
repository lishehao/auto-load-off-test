from __future__ import annotations

from app.domain.enums import ConnectionMode, CorrectionMode, CouplingMode, ImpedanceMode, MagnitudePhaseMode, TriggerMode
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
from app.shared.mapping import Mapping


class DefaultSettingsFactory:
    def create(self) -> AppSettings:
        return AppSettings(
            schema_version=1,
            freq_unit=Mapping.mapping_mhz,
            sweep=SweepSpec(
                start_hz=1e6,
                stop_hz=100e6,
                step_hz=1e6,
                step_count=100,
                is_log=False,
            ),
            run_mode=RunMode(
                correction_mode=CorrectionMode.NONE,
                trigger_mode=TriggerMode.FREE_RUN,
                auto_range=True,
                auto_reset=True,
            ),
            setup=InstrumentSetup(
                awg=InstrumentEndpoint(
                    model=Mapping.mapping_DSG_4102,
                    connect_mode=ConnectionMode.AUTO,
                    visa_address="",
                    ip_address="0.0.0.0",
                ),
                osc=InstrumentEndpoint(
                    model=Mapping.mapping_MDO_34,
                    connect_mode=ConnectionMode.AUTO,
                    visa_address="",
                    ip_address="0.0.0.0",
                ),
                channels=ChannelSelection(awg_ch=1, osc_test_ch=1, osc_ref_ch=2, osc_trig_ch=2),
                awg_settings=AwgSettings(amplitude_vpp=1.0, impedance=ImpedanceMode.R50),
                osc_settings=OscSettings(
                    full_scale_v=1.0,
                    offset_v=0.0,
                    points=10_000,
                    impedance=ImpedanceMode.R50,
                    coupling=CouplingMode.DC,
                ),
            ),
            magnitude_phase_mode=MagnitudePhaseMode.MAG,
            auto_save_data=True,
        )
