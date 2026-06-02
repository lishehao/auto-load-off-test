from __future__ import annotations

import numpy as np


class MockAwgAdapter:
    def __init__(self) -> None:
        self.frequency_hz = 1_000.0
        self.amplitude_vpp = 1.0
        self.output_channels: set[int] = set()
        self.closed = False

    def reset(self) -> None:
        self.output_channels.clear()

    def output_on(self, channel: int) -> None:
        self.output_channels.add(channel)

    def output_off(self, channel: int) -> None:
        self.output_channels.discard(channel)

    def set_impedance(self, mode: str, channel: int) -> None:
        _ = (mode, channel)

    def set_frequency(self, hz: float, channel: int) -> None:
        _ = channel
        self.frequency_hz = float(hz)

    def get_frequency(self, channel: int) -> float:
        _ = channel
        return self.frequency_hz

    def set_amplitude_vpp(self, vpp: float, channel: int) -> None:
        _ = channel
        self.amplitude_vpp = float(vpp)

    def get_amplitude_vpp(self, channel: int) -> float:
        _ = channel
        return self.amplitude_vpp

    def close(self) -> None:
        self.closed = True


class MockOscAdapter:
    def __init__(self, awg: MockAwgAdapter | None = None) -> None:
        self._awg = awg or MockAwgAdapter()
        self._range_v = 1.0
        self._offset_v = 0.0
        self.closed = False

    def reset(self) -> None:
        return None

    def output_on(self, channel: int) -> None:
        _ = channel

    def set_timebase(self, window_s: float, offset_s: float | None = None) -> None:
        _ = (window_s, offset_s)

    def set_vertical(self, channel: int, full_scale_v: float, offset_v: float) -> None:
        _ = channel
        self._range_v = float(full_scale_v)
        self._offset_v = float(offset_v)

    def get_vertical(self, channel: int) -> tuple[float, float]:
        _ = channel
        return self._range_v, self._offset_v

    def set_coupling(self, channel: int, mode: str) -> None:
        _ = (channel, mode)

    def set_impedance(self, channel: int, mode: str) -> None:
        _ = (channel, mode)

    def arm_trigger(self, channel: int, level_v: float) -> None:
        _ = (channel, level_v)

    def set_free_run(self) -> None:
        return None

    def single_acquire(self, triggered: bool) -> None:
        _ = triggered

    def read_waveform(self, channel: int, points: int | None) -> tuple[np.ndarray, np.ndarray]:
        _ = channel
        n = int(points or 4_000)
        sample_rate = self.get_sample_rate()
        times = np.arange(n, dtype=float) / sample_rate
        peak = max(self._awg.amplitude_vpp * 0.25, 1e-6)
        volts = peak * np.sin(2.0 * np.pi * self._awg.frequency_hz * times) + self._offset_v
        return times, volts

    def get_sample_rate(self) -> float:
        return 200_000.0

    def close(self) -> None:
        self.closed = True
