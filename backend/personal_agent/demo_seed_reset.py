"""Demo-only seed reset helper for the Growth Loop walkthrough."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .audit_log import append_audit_event


PLAN_TASKS_FILENAME = "plan_tasks.jsonl"
ARCHIVE_DIRNAME = "demo_reset_archive"


def reset_demo_today_tasks(
    data_dir: str | Path = "data",
    today: date | None = None,
    write_audit: bool = True,
) -> dict[str, Any]:
    """Move tasks dated today out of the active task file for repeatable demos."""

    root = Path(data_dir)
    tasks_path = root / PLAN_TASKS_FILENAME
    target_date = (today or date.today()).isoformat()
    if not tasks_path.exists():
        return {
            "ok": True,
            "data_dir": str(root),
            "target_date": target_date,
            "removed_count": 0,
            "kept_count": 0,
            "archive_path": "",
            "audit_event": None,
            "note": f"{PLAN_TASKS_FILENAME} does not exist; today's task list is already empty.",
        }

    original_lines = tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept_lines: list[str] = []
    removed_records: list[dict[str, Any]] = []
    malformed_count = 0

    for line in original_lines:
        stripped = line.strip()
        if not stripped:
            kept_lines.append(line)
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError:
            malformed_count += 1
            kept_lines.append(line)
            continue
        if isinstance(record, dict) and str(record.get("date") or "") == target_date:
            removed_records.append(record)
        else:
            kept_lines.append(line)

    if not removed_records:
        return {
            "ok": True,
            "data_dir": str(root),
            "target_date": target_date,
            "removed_count": 0,
            "kept_count": len([line for line in kept_lines if line.strip()]),
            "malformed_count": malformed_count,
            "archive_path": "",
            "audit_event": None,
            "note": "No tasks dated today were found; no files were changed.",
        }

    archive_dir = root / ARCHIVE_DIRNAME
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / _archive_filename(target_date)
    _write_jsonl(archive_path, removed_records)
    tasks_path.write_text("".join(kept_lines), encoding="utf-8")

    audit_event = None
    if write_audit:
        audit_event = append_audit_event(
            {
                "event_type": "demo_seed_reset",
                "actor": "system",
                "module": "demo_seed_reset",
                "action_kind": "reset_today_tasks",
                "target": PLAN_TASKS_FILENAME,
                "status": "success",
                "summary": f"Demo seed reset moved {len(removed_records)} task(s) dated {target_date} to archive.",
                "payload": {
                    "target_date": target_date,
                    "removed_count": len(removed_records),
                    "kept_count": len([line for line in kept_lines if line.strip()]),
                    "malformed_count": malformed_count,
                    "archive_path": str(archive_path),
                },
                "source": "demo_seed_reset",
            },
            data_dir=root,
        )

    return {
        "ok": True,
        "data_dir": str(root),
        "target_date": target_date,
        "removed_count": len(removed_records),
        "kept_count": len([line for line in kept_lines if line.strip()]),
        "malformed_count": malformed_count,
        "archive_path": str(archive_path),
        "audit_event": audit_event,
        "note": "Today's demo tasks were archived and removed from the active task list.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reset Growth Loop demo seed data to an empty today task list.")
    parser.add_argument(
        "--data-dir",
        default=str(Path(__file__).resolve().parents[2] / "data"),
        help="Path to the Personal Agent data directory. Defaults to the repo data directory.",
    )
    parser.add_argument(
        "--today",
        default="",
        help="Override today's date in YYYY-MM-DD form. Intended for tests or rehearsals.",
    )
    parser.add_argument(
        "--no-audit",
        action="store_true",
        help="Do not append the demo_seed_reset audit event.",
    )
    args = parser.parse_args(argv)

    target_day = _parse_date(args.today) if args.today else None
    result = reset_demo_today_tasks(args.data_dir, today=target_day, write_audit=not args.no_audit)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("ok") else 1


def _archive_filename(target_date: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    safe_date = target_date.replace("-", "")
    return f"plan_tasks_{safe_date}_reset_{stamp}.jsonl"


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"--today must be YYYY-MM-DD, got: {value}") from exc


if __name__ == "__main__":  # pragma: no cover - exercised through the repo-root wrapper.
    raise SystemExit(main())
