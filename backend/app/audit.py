"""
Acá iría el modulo de Trazabilidad.

- `logs/app.log`           es un log técnico (rotado) + salida stdout, con `request_id`.
- `logs/conversions.jsonl` una línea JSON por evento: conversión (`ok` / `error` / `cancelled`),
                           edición y borrado. Es la fuente de `/api/logs`.
"""

import json
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

log = logging.getLogger("pseudo2code")


def setup_logging(logs_dir: Path, level: str = "INFO") -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    file_handler = RotatingFileHandler(logs_dir / "app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    console = logging.StreamHandler()
    for h in (file_handler, console):
        h.setFormatter(fmt)
    log.handlers[:] = [file_handler, console]
    log.setLevel(level.upper())
    log.propagate = False


class AuditLog:
    def __init__(self, logs_dir: Path):
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.path = logs_dir / "conversions.jsonl"
        self._lock = threading.Lock()

    def write(self, event: str, **fields) -> dict:
        record = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "event": event, **fields}
        line = json.dumps(record, ensure_ascii=False)
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return record

    def tail(self, limit: int = 200, *, event: str | None = None, status: str | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        out: deque[dict] = deque(maxlen=limit)
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event and rec.get("event") != event:
                    continue
                if status and rec.get("status") != status:
                    continue
                out.append(rec)
        return list(reversed(out))
