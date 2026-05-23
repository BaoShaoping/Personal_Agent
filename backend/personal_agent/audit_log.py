"""Append-only audit log foundation for future action execution."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .memory_store import read_jsonl_file


AUDIT_LOG_FILE = "audit_log.jsonl"

EVENT_TYPES = {
    "suggestion_generated",
    "permission_evaluated",
    "action_confirmed",
    "action_canceled",
    "action_executed",
    "action_failed",
    "memory_written",
    "plan_updated",
    "settings_updated",
}

EVENT_STATUSES = {"success", "failed", "canceled", "pending"}

SENSITIVE_KEY_PARTS = (
    "api_key",
    "token",
    "password",
    "secret",
    "authorization",
)


def append_audit_event(event: dict[str, Any], data_dir: str | Path = "data") -> dict[str, Any]:
    """Append one redacted audit event and return the stored record."""

    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / AUDIT_LOG_FILE
    now = datetime.now().astimezone()

    record = redact_sensitive(_json_safe(dict(event or {})))
    if not isinstance(record, dict):
        record = {}

    record.setdefault("id", _next_audit_id(root, now))
    record.setdefault("created_at", now.isoformat(timespec="seconds"))
    record["event_type"] = _clean_text(record.get("event_type") or "suggestion_generated")
    record["actor"] = _clean_text(record.get("actor") or "system")
    record["module"] = _clean_text(record.get("module") or "unknown")
    record["action_id"] = _clean_text(record.get("action_id") or "")
    record["action_kind"] = _clean_text(record.get("action_kind") or "")
    record["target"] = _clean_text(record.get("target") or "")
    record["risk_level"] = _clean_text(record.get("risk_level") or "")
    record["permission_mode"] = _clean_text(record.get("permission_mode") or "")
    record["requires_confirmation"] = bool(record.get("requires_confirmation", False))
    record["status"] = _normalize_status(record.get("status"))
    record["summary"] = _clean_text(record.get("summary") or "")
    record["payload"] = redact_sensitive(_json_safe(record.get("payload", {})))
    record["source"] = _clean_text(record.get("source") or "system")

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def read_audit_events(
    data_dir: str | Path = "data",
    limit: int = 50,
    event_type: str | None = None,
    action_id: str | None = None,
) -> list[dict[str, Any]]:
    """Read recent audit events newest-first, optionally filtered."""

    path = Path(data_dir) / AUDIT_LOG_FILE
    if not path.exists():
        return []

    records = [redact_sensitive(_json_safe(record)) for record in read_jsonl_file(path)]
    events = [record for record in records if isinstance(record, dict)]

    if event_type:
        events = [event for event in events if event.get("event_type") == event_type]
    if action_id:
        events = [event for event in events if event.get("action_id") == action_id]

    safe_limit = _coerce_limit(limit, default=50, maximum=500)
    if safe_limit <= 0:
        return []
    return events[-safe_limit:][::-1]


def build_audit_summary(data_dir: str | Path = "data", limit: int = 20) -> dict[str, Any]:
    """Return recent audit events and simple counts for the debug console."""

    recent_events = read_audit_events(data_dir=data_dir, limit=limit)
    counts_by_type: dict[str, int] = {}
    counts_by_status: dict[str, int] = {}
    for event in recent_events:
        event_type = str(event.get("event_type") or "unknown")
        status = str(event.get("status") or "unknown")
        counts_by_type[event_type] = counts_by_type.get(event_type, 0) + 1
        counts_by_status[status] = counts_by_status.get(status, 0) + 1

    return {
        "ok": True,
        "recent_events": recent_events,
        "counts_by_type": counts_by_type,
        "counts_by_status": counts_by_status,
    }


def redact_sensitive(value: Any) -> Any:
    """Recursively redact common secret-bearing keys."""

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                redacted[key_text] = "[redacted]"
            else:
                redacted[key_text] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive(item) for item in value]
    return value


def _next_audit_id(data_dir: Path, now: datetime) -> str:
    prefix = f"audit_{now.strftime('%Y%m%d')}_"
    max_index = 0
    path = data_dir / AUDIT_LOG_FILE
    if path.exists():
        for record in read_jsonl_file(path):
            raw_id = str(record.get("id") or "")
            if not raw_id.startswith(prefix):
                continue
            try:
                max_index = max(max_index, int(raw_id.removeprefix(prefix)))
            except ValueError:
                continue
    return f"{prefix}{max_index + 1:03d}"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_status(status: Any) -> str:
    text = _clean_text(status or "success")
    return text if text in EVENT_STATUSES else "success"


def _coerce_limit(limit: Any, default: int, maximum: int) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = default
    return max(0, min(value, maximum))
