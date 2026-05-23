"""Local file-backed long-term plan storage and context helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .memory_store import read_jsonl_file, read_yaml_file


PLAN_STATUSES = {"active", "paused", "completed", "archived"}
PLAN_KINDS = {"main", "side"}
TASK_STATUSES = {"todo", "done", "skipped", "blocked"}
REMINDER_MODES = {"off", "passive", "daily"}

PLAN_FILES = {
    "plans": "plans.yaml",
    "tasks": "plan_tasks.jsonl",
    "progress": "plan_progress.jsonl",
    "reminders": "reminders.yaml",
}


@dataclass
class PlanData:
    """All local plan files plus loader diagnostics."""

    data_dir: Path
    plans: list[dict[str, Any]] = field(default_factory=list)
    tasks: list[dict[str, Any]] = field(default_factory=list)
    progress: list[dict[str, Any]] = field(default_factory=list)
    reminders: dict[str, Any] = field(default_factory=dict)
    missing_files: list[str] = field(default_factory=list)
    load_errors: list[dict[str, str]] = field(default_factory=list)


def load_plan_data(data_dir: str | Path = "data") -> PlanData:
    """Load long-term plan files, reporting diagnostics instead of raising."""

    root = Path(data_dir)
    data = PlanData(data_dir=root)

    plans_path = root / PLAN_FILES["plans"]
    if not plans_path.exists():
        data.missing_files.append(PLAN_FILES["plans"])
    else:
        try:
            raw = read_yaml_file(plans_path)
            data.plans = [_normalize_plan(plan) for plan in _ensure_list(raw.get("plans") if isinstance(raw, dict) else [])]
        except Exception as exc:  # pragma: no cover - defensive diagnostics
            data.load_errors.append({"file": PLAN_FILES["plans"], "error": str(exc)})

    reminders_path = root / PLAN_FILES["reminders"]
    if not reminders_path.exists():
        data.missing_files.append(PLAN_FILES["reminders"])
    else:
        try:
            raw = read_yaml_file(reminders_path)
            data.reminders = raw if isinstance(raw, dict) else {}
        except Exception as exc:  # pragma: no cover - defensive diagnostics
            data.load_errors.append({"file": PLAN_FILES["reminders"], "error": str(exc)})

    for attr, filename in (("tasks", PLAN_FILES["tasks"]), ("progress", PLAN_FILES["progress"])):
        path = root / filename
        if not path.exists():
            data.missing_files.append(filename)
            continue
        try:
            records = read_jsonl_file(path)
            normalized = [_normalize_task(record) if attr == "tasks" else _normalize_progress(record) for record in records]
            setattr(data, attr, normalized)
        except Exception as exc:  # pragma: no cover - defensive diagnostics
            data.load_errors.append({"file": filename, "error": str(exc)})

    return data


def list_active_plans(data_dir: str | Path = "data") -> list[dict[str, Any]]:
    data = load_plan_data(data_dir)
    return [plan for plan in data.plans if plan.get("status") == "active"]


def list_today_tasks(
    plan_id: str | None = None,
    data_dir: str | Path = "data",
    today: date | None = None,
) -> list[dict[str, Any]]:
    data = load_plan_data(data_dir)
    target_date = (today or date.today()).isoformat()
    tasks = [task for task in data.tasks if task.get("date") == target_date]
    if plan_id:
        tasks = [task for task in tasks if task.get("plan_id") == plan_id]
    return tasks


def update_task_status(
    task_id: str,
    status: str,
    note: str | None = None,
    data_dir: str | Path = "data",
) -> dict[str, Any]:
    """Update one task status in JSONL and append a lightweight progress note."""

    if status not in TASK_STATUSES:
        raise ValueError(f"Unsupported task status: {status}")

    root = Path(data_dir)
    tasks_path = root / PLAN_FILES["tasks"]
    if not tasks_path.exists():
        raise FileNotFoundError(str(tasks_path))

    tasks = read_jsonl_file(tasks_path)
    updated_task: dict[str, Any] | None = None
    for task in tasks:
        if str(task.get("id")) == task_id:
            task["status"] = status
            task["updated_at"] = _now_iso()
            if note:
                task["note"] = note
            updated_task = _normalize_task(task)
            break

    if updated_task is None:
        raise KeyError(f"Task not found: {task_id}")

    _write_jsonl_file(tasks_path, tasks)
    progress_entry = append_plan_progress(
        {
            "plan_id": updated_task.get("plan_id"),
            "summary": f"Task {task_id} marked as {status}.",
            "progress_delta": 1 if status == "done" else 0,
            "note": note or updated_task.get("title", ""),
            "source": "task_status",
            "task_id": task_id,
        },
        data_dir=root,
    )
    return {"ok": True, "task": updated_task, "progress_entry": progress_entry}


def create_plan_task(entry: dict[str, Any], data_dir: str | Path = "data") -> dict[str, Any]:
    """Append one small task for an existing long-term plan."""

    root = Path(data_dir)
    raw = dict(entry or {})
    plan_id = str(raw.get("plan_id") or "").strip()
    title = str(raw.get("title") or "").strip()
    if not plan_id:
        raise ValueError("缺少 plan_id。")
    if not title:
        raise ValueError("缺少任务标题。")

    plan_ids = {str(plan.get("id")) for plan in load_plan_data(root).plans}
    if plan_id not in plan_ids:
        raise KeyError(f"Plan not found: {plan_id}")

    tasks_path = root / PLAN_FILES["tasks"]
    existing_tasks = read_jsonl_file(tasks_path) if tasks_path.exists() else []
    existing_ids = {str(task.get("id")) for task in existing_tasks if isinstance(task, dict)}

    task = {
        "id": str(raw.get("id") or _new_task_id()).strip(),
        "plan_id": plan_id,
        "date": str(raw.get("date") or date.today().isoformat()).strip(),
        "title": title,
        "status": "todo",
        "source": str(raw.get("source") or "action_executor").strip(),
        "created_at": str(raw.get("created_at") or _now_iso()).strip(),
    }
    while task["id"] in existing_ids:
        task["id"] = _new_task_id()

    normalized = _normalize_task(task)
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    with tasks_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, ensure_ascii=False, separators=(",", ":")) + "\n")
    return normalized


def append_plan_progress(entry: dict[str, Any], data_dir: str | Path = "data") -> dict[str, Any]:
    root = Path(data_dir)
    path = root / PLAN_FILES["progress"]
    raw = dict(entry)
    raw["id"] = raw.get("id") or _new_progress_id()
    raw["created_at"] = raw.get("created_at") or _now_iso()
    raw["source"] = raw.get("source") or "manual"
    normalized = _normalize_progress(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, ensure_ascii=False, separators=(",", ":")) + "\n")
    return normalized


def build_plan_context(
    user_message: str,
    data_dir: str | Path = "data",
    max_items: int = 5,
) -> dict[str, Any]:
    """Build a small, JSON-serializable context slice for active plans."""

    data = load_plan_data(data_dir)
    active_plans = [plan for plan in data.plans if plan.get("status") == "active"][:max_items]
    active_plan_ids = {str(plan.get("id")) for plan in active_plans}
    today_tasks = [
        task for task in list_today_tasks(data_dir=data_dir) if not active_plan_ids or task.get("plan_id") in active_plan_ids
    ][:max_items]
    recent_progress = _sort_progress_recent(
        [entry for entry in data.progress if not active_plan_ids or entry.get("plan_id") in active_plan_ids]
    )[:max_items]

    sources = []
    if active_plans:
        sources.append(_source_ref(data.data_dir, PLAN_FILES["plans"], "plan"))
    if today_tasks:
        sources.append(_source_ref(data.data_dir, PLAN_FILES["tasks"], "plan_task"))
    if recent_progress:
        sources.append(_source_ref(data.data_dir, PLAN_FILES["progress"], "plan_progress"))
    if data.reminders:
        sources.append(_source_ref(data.data_dir, PLAN_FILES["reminders"], "reminder"))

    return {
        "user_message": user_message,
        "active_plans": active_plans,
        "today_tasks": today_tasks,
        "recent_progress": recent_progress,
        "reminder_settings": data.reminders,
        "sources": sources,
        "missing_files": data.missing_files,
        "load_errors": data.load_errors,
        "stats": {
            "loaded": {
                "plans": len(data.plans),
                "tasks": len(data.tasks),
                "progress": len(data.progress),
            },
            "selected": {
                "plans": len(active_plans),
                "today_tasks": len(today_tasks),
                "recent_progress": len(recent_progress),
            },
            "max_items": max_items,
        },
    }


def plan_summary(data_dir: str | Path = "data", today: date | None = None) -> dict[str, Any]:
    data = load_plan_data(data_dir)
    active_plans = [plan for plan in data.plans if plan.get("status") == "active"]
    active_plan_ids = {str(plan.get("id")) for plan in active_plans}
    today_tasks = [
        task
        for task in list_today_tasks(data_dir=data_dir, today=today)
        if not active_plan_ids or task.get("plan_id") in active_plan_ids
    ]
    recent_progress = _sort_progress_recent(
        [entry for entry in data.progress if not active_plan_ids or entry.get("plan_id") in active_plan_ids]
    )[:10]
    return {
        "ok": True,
        "data_dir": str(data.data_dir),
        "active_plans": active_plans,
        "today_tasks": today_tasks,
        "recent_progress": recent_progress,
        "reminder_settings": data.reminders,
        "missing_files": data.missing_files,
        "load_errors": data.load_errors,
        "counts": {
            "plans": len(data.plans),
            "tasks": len(data.tasks),
            "progress": len(data.progress),
        },
    }


def _normalize_plan(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict):
        plan = {"title": str(plan)}
    normalized = dict(plan)
    normalized.setdefault("id", f"plan_{abs(hash(str(normalized))) % 100000}")
    normalized.setdefault("kind", "side")
    normalized.setdefault("status", "active")
    normalized.setdefault("progress_percent", 0)
    normalized.setdefault("reminder_mode", "passive")
    normalized.setdefault("tags", [])
    if normalized["kind"] not in PLAN_KINDS:
        normalized["kind"] = "side"
    if normalized["status"] not in PLAN_STATUSES:
        normalized["status"] = "active"
    if normalized["reminder_mode"] not in REMINDER_MODES:
        normalized["reminder_mode"] = "passive"
    normalized["progress_percent"] = max(0, min(int(normalized.get("progress_percent") or 0), 100))
    return normalized


def _normalize_task(task: Any) -> dict[str, Any]:
    if not isinstance(task, dict):
        task = {"title": str(task)}
    normalized = dict(task)
    normalized.setdefault("id", f"task_{abs(hash(str(normalized))) % 100000}")
    normalized.setdefault("status", "todo")
    normalized.setdefault("source", "plan")
    if normalized["status"] not in TASK_STATUSES:
        normalized["status"] = "todo"
    return normalized


def _normalize_progress(entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict):
        entry = {"summary": str(entry)}
    normalized = dict(entry)
    normalized.setdefault("id", _new_progress_id())
    normalized.setdefault("created_at", _now_iso())
    normalized.setdefault("progress_delta", 0)
    normalized.setdefault("source", "manual")
    return normalized


def _sort_progress_recent(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(entries, key=lambda entry: str(entry.get("created_at") or ""), reverse=True)


def _source_ref(data_dir: Path, filename: str, kind: str) -> dict[str, Any]:
    return {"source": filename, "id": None, "path": str(data_dir / filename), "kind": kind}


def _write_jsonl_file(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _new_progress_id() -> str:
    return "prog_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def _new_task_id() -> str:
    return "task_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
