from __future__ import annotations


class PyVisaIdentityProbe:
    def identify(self, address: str, timeout_ms: int | None = None) -> str:
        try:
            import pyvisa as visa
        except ModuleNotFoundError as exc:
            raise RuntimeError("pyvisa is not installed") from exc

        resource = None
        rm = visa.ResourceManager()
        try:
            resource = rm.open_resource(address)
            if timeout_ms is not None:
                resource.timeout = int(timeout_ms)
            response = resource.query("*IDN?")
            return str(response).strip()
        finally:
            if resource is not None:
                resource.close()
            try:
                rm.close()
            except Exception:
                pass
