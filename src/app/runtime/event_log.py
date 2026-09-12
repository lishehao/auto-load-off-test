from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class RunEventLog:
    """Local bounded diagnostic history, including warnings during window close."""

    def __init__(self, path: Path):
        self.path = path
        self._handler = None

    def record(self, event: object) -> None:
        if self._handler is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._handler = RotatingFileHandler(self.path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
            self._handler.setFormatter(logging.Formatter("%(message)s"))
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": type(event).__name__}
        for field in ("code", "error_code", "message"):
            if hasattr(event, field):
                entry[field] = str(getattr(event, field))
        result = getattr(event, "result", None)
        if result is not None:
            entry["point_count"] = len(result.points)
            entry["run_status"] = result.meta.get("run_status", "unknown")
        record = logging.LogRecord("sweep", logging.INFO, "", 0, json.dumps(entry), (), None)
        self._handler.handle(record)

    def close(self):
        if self._handler is not None:
            self._handler.close()
            self._handler = None
