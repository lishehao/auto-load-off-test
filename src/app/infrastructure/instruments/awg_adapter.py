from __future__ import annotations

from app.infrastructure.instruments.vendor_gateway import create_vendor_instrument


class EquipsAwgAdapter:
    def __init__(self, model: str, visa_address: str) -> None:
        self._inst = create_vendor_instrument(model=model, visa_address=visa_address)

    def reset(self) -> None:
        self._inst.rst()

    def output_on(self, channel: int) -> None:
        self._inst.set_on(on=True, ch=channel)

    def output_off(self, channel: int) -> None:
        self._inst.set_on(on=False, ch=channel)

    def set_impedance(self, mode: str, channel: int) -> None:
        self._inst.set_imp(imp=mode, ch=channel)

    def set_frequency(self, hz: float, channel: int) -> None:
        self._inst.set_freq(freq=hz, ch=channel)

    def get_frequency(self, channel: int) -> float:
        return float(self._inst.get_freq(ch=channel))

    def set_amplitude_vpp(self, vpp: float, channel: int) -> None:
        self._inst.set_amp(amp=vpp, ch=channel)

    def get_amplitude_vpp(self, channel: int) -> float:
        return float(self._inst.get_amp(ch=channel))

    def close(self) -> None:
        self._inst.inst_close()
