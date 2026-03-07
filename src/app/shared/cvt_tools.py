from __future__ import annotations

import math
import re

import numpy as np


class CvtTools:
    @staticmethod
    def parse_general_val(input: str, default_unit: str | None = None) -> float | int:
        input = input.replace(" ", "")
        input_match = re.search(r"([+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?)([A-Za-zµ]?)", input)
        if input_match is None:
            return 0.0

        input_val = input_match.group(1)
        input_unit = input_match.group(2)

        try:
            input_val = int(input_val) if input_val.isdigit() else float(input_val)
        except Exception:
            return 0.0

        if not input_unit:
            val = input_val * CvtTools.convert_general_unit(default_unit)
            try:
                return int(val) if float(val).is_integer() else val
            except Exception:
                return val

        prefix = input_unit[0]
        scale = CvtTools._scale_for_prefix(prefix)
        val = input_val * scale
        try:
            return int(val) if float(val).is_integer() else val
        except Exception:
            return val

    @staticmethod
    def convert_general_unit(unit: str | None) -> float | int:
        if not unit:
            return 1

        input_match = re.search(r"([+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?)([A-Za-zµ]?)", unit)
        if input_match is None:
            return 1

        input_unit = input_match.group(2)
        if not input_unit:
            return 1

        return CvtTools._scale_for_prefix(input_unit[0])

    @staticmethod
    def parse_to_hz(freq: str, default_unit: str = "") -> float:
        new_freq = CvtTools.parse_general_val(input=freq, default_unit=default_unit)
        return float(new_freq) if new_freq else 0.0

    @staticmethod
    def parse_to_Vpp(vpp: str) -> float:
        vpp = vpp.replace(" ", "")
        vpp_match = re.search(r"([+-]?\d*(?:\.\d+)?(?:[eE][+-]?\d+)?)([A-Za-zµ]*)", vpp)
        if vpp_match is None:
            return 0.0

        vpp_val = vpp_match.group(1)
        vpp_unit = vpp_match.group(2)

        if not vpp_val:
            return 0.0

        value = float(vpp_val)
        if not vpp_unit:
            scale = 1.0
        elif "Vpp".lower() in vpp_unit.lower():
            scale = 1.0
        elif "Vpk".lower() in vpp_unit.lower():
            scale = 2.0
        elif "Vrms".lower() in vpp_unit.lower():
            scale = math.sqrt(8)
        else:
            scale = 1.0

        if vpp_unit and vpp_unit[0] == "m":
            scale *= 0.001
        return value * scale

    @staticmethod
    def parse_to_V(volts: str) -> float | int:
        return CvtTools.parse_general_val(input=volts)

    @staticmethod
    def _parabolic_interp_delta(m1: float, m0: float, p1: float) -> float:
        eps = 1e-30
        m1 = np.log(max(m1, eps))
        m0 = np.log(max(m0, eps))
        p1 = np.log(max(p1, eps))
        denom = m1 - 2 * m0 + p1
        if abs(denom) < 1e-12:
            return 0.0
        return 0.5 * (m1 - p1) / denom

    @staticmethod
    def _complex_tone_at(times: np.ndarray, volts_ac: np.ndarray, f_hz: float, window: np.ndarray | None = None) -> complex:
        if window is None:
            return np.sum(volts_ac * np.exp(-1j * 2 * np.pi * f_hz * times))
        return np.sum(window * volts_ac * np.exp(-1j * 2 * np.pi * f_hz * times))

    @staticmethod
    def _scale_for_prefix(prefix: str) -> float:
        if prefix in ("G", "g"):
            return 1e9
        if prefix == "M":
            return 1e6
        if prefix in ("k", "K"):
            return 1e3
        if prefix == "m":
            return 1e-3
        if prefix in ("u", "µ", "μ"):
            return 1e-6
        if prefix in ("n", "N"):
            return 1e-9
        if prefix in ("p", "P"):
            return 1e-12
        return 1.0
