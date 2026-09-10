"""Central helper for writing rows into the `logs` table + files."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from models import Log

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
_SYSTEM_LOG = LOG_DIR / "system.log"
_ERROR_LOG = LOG_DIR / "error.log"


def write_log(
    db: Session,
    message: str,
    *,
    level: str = "info",
    category: str = "config",
    device_id: int | None = None,
    detail: str | None = None,
) -> Log:
    row = Log(
        message=message, level=level, category=category, device_id=device_id, detail=detail
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    line = f"{row.timestamp.isoformat()} [{level.upper()}] {category}: {message}\n"
    try:
        _SYSTEM_LOG.open("a", encoding="utf-8").write(line)
        if level == "error":
            _ERROR_LOG.open("a", encoding="utf-8").write(line + (f"  detail: {detail}\n" if detail else ""))
    except OSError:
        pass
    return row
