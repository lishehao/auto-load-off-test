from __future__ import annotations


def create_vendor_instrument(model: str, visa_address: str) -> object:
    try:
        from equips import inst_mapping
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing runtime dependency: pyvisa/equips is required for instrument access") from exc

    if model not in inst_mapping:
        raise ValueError(f"Unsupported instrument model: {model}")
    return inst_mapping[model](name=model, visa_address=visa_address)
