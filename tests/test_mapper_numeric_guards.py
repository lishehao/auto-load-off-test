from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.presentation.tk.mapper import vm_to_settings


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _vm(**overrides):
    values = {
        "freq_unit": "Hz", "is_log": False, "start_freq": "1000", "stop_freq": "3000", "step_freq": "1000",
        "step_count": "100", "correction_mode": "none", "trigger_mode": "free_run", "auto_range": False,
        "auto_reset": False, "awg_model": "DSG4102", "osc_model": "MDO34", "awg_connect_mode": "auto",
        "osc_connect_mode": "auto", "awg_visa": "", "osc_visa": "", "awg_ip": "0.0.0.0", "osc_ip": "0.0.0.0",
        "awg_ch": "1", "osc_test_ch": "1", "osc_ref_ch": "", "osc_trig_ch": "", "awg_amp": "1",
        "awg_imp": "50", "osc_range": "1", "osc_offset": "0", "osc_points": "1000", "osc_imp": "50",
        "osc_coupling": "DC", "magnitude_phase_mode": "magnitude", "auto_save_data": False,
    }
    values.update(overrides)
    return SimpleNamespace(**{name: Value(value) for name, value in values.items()})


class MapperNumericGuardTests(unittest.TestCase):
    def test_integer_controls_reject_invalid_or_noninteger_text(self) -> None:
        for field in ("step_count", "awg_ch", "osc_points"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "Expected integer"):
                    vm_to_settings(_vm(is_log=field == "step_count", **{field: "2.5"}))

    def test_points_are_not_silently_raised_and_optional_channels_can_be_empty(self) -> None:
        settings = vm_to_settings(_vm(osc_points="1"))
        self.assertEqual(settings.setup.osc_settings.points, 1)
        self.assertIsNone(settings.setup.channels.osc_ref_ch)
        self.assertIsNone(settings.setup.channels.osc_trig_ch)

    def test_float_controls_reject_nan_tokens_instead_of_parser_zero_fill(self) -> None:
        with self.assertRaisesRegex(ValueError, "osc_offset"):
            vm_to_settings(_vm(osc_offset="nan"))

    def test_mapper_does_not_import_tk_view_model_at_runtime(self) -> None:
        self.assertNotIn("app.presentation.tk.view_model", sys.modules)


if __name__ == "__main__":
    unittest.main()
