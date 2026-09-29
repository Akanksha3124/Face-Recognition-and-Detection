"""
Convert Python values that aren't natively JSON-serializable (date,
datetime, Enum) into something audit_logs.extra_data (JSONB) can
actually store. asyncpg's JSON encoding doesn't know about these types
on its own.
"""
import enum
from datetime import date, datetime
from typing import Any


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value
