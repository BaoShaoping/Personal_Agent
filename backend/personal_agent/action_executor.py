"""Confirmed, allowlisted local action execution for the MVP."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .audit_log import append_audit_event, redact_sensitive
from .memory_store import read_yaml_file
from .plan_store import PLAN_KINDS, PLAN_STATUSES, REMINDER_MODES, create_plan_task, update_task_status


SUPPORTED_ACTION_KINDS = {
    "update_plan_task_status",
    "create_plan_candidate",
    "create_today_task_candidate",
    "save_memory_candidate",
}

MEMORY_TARGETS = {
    "memories.jsonl": ("mem", "memory"),
    "decisions.jsonl": ("dec", "decision"),
}


def execute_confirmed_action(
    action: dict[str, Any],
    permission_decision: dict[str, Any],
    confirmed: bool,
    data_dir: str | Path = "data",
) -> dict[str, Any]:
    """Execute one confirmed allowlisted action and always write audit events."""

    root = Path(data_dir)
    action = action if isinstance(action, dict) else {}
    permission_decision = permission_decision if isinstance(permission_decision, dict) else {}
    action_kind = _action_kind(action)
    audit_events: list[dict[str, Any]] = []

    if not confirmed:
        event = _append_action_event(
            "action_canceled",
            action,
            permission_decision,
            "canceled",
            f"操作 {action_kind} 在执行前已取消。",
            root,
            payload={"reason": "confirmed=false"},
        )
        return _result(False, "canceled", action, permission_decision, audit_events + [event])

    audit_events.append(
        _append_action_event(
            "action_confirmed",
            action,
            permission_decision,
            "pending",
            f"用户已确认操作 {action_kind}。",
            root,
        )
    )

    if permission_decision.get("hard_block") is True:
        audit_events.append(
            _append_action_event(
                "action_failed",
                action,
                permission_decision,
                "failed",
                f"操作 {action_kind} 被权限策略阻止。",
                root,
                payload={"reason": "hard_block"},
            )
        )
        return _result(False, "failed", action, permission_decision, audit_events, "操作被权限策略硬阻止（hard_block）。")

    if not permission_decision:
        audit_events.append(
            _append_action_event(
                "action_failed",
                action,
                permission_decision,
                "failed",
                f"操作 {action_kind} 失败：缺少 permission_decision。",
                root,
            )
        )
        return _result(False, "failed", action, permission_decision, audit_events, "缺少 permission_decision。")

    if action_kind not in SUPPORTED_ACTION_KINDS:
        audit_events.append(
            _append_action_event(
                "action_failed",
                action,
                permission_decision,
                "failed",
                f"不支持的 action kind：{action_kind}。",
                root,
            )
        )
        return _result(False, "failed", action, permission_decision, audit_events, f"不支持的 action kind：{action_kind}")

    try:
        execution_payload = _execute_action(action, root)
    except Exception as exc:
        audit_events.append(
            _append_action_event(
                "action_failed",
                action,
                permission_decision,
                "failed",
                f"操作 {action_kind} 执行失败：{exc}",
                root,
                payload={"error": {"message": str(exc), "type": exc.__class__.__name__}},
            )
        )
        return _result(False, "failed", action, permission_decision, audit_events, str(exc))

    audit_events.append(
        _append_action_event(
            "action_executed",
            action,
            permission_decision,
            "success",
            f"操作 {action_kind} 已成功执行。",
            root,
            payload={"execution_result": execution_payload},
        )
    )
    return _result(True, "executed", action, permission_decision, audit_events, execution_result=execution_payload)


def cancel_action(
    action: dict[str, Any],
    permission_decision: dict[str, Any] | None = None,
    data_dir: str | Path = "data",
) -> dict[str, Any]:
    """Cancel one proposed action without executing it."""

    root = Path(data_dir)
    action = action if isinstance(action, dict) else {}
    permission_decision = permission_decision if isinstance(permission_decision, dict) else {}
    action_kind = _action_kind(action)
    event = _append_action_event(
        "action_canceled",
        action,
        permission_decision,
        "canceled",
        f"用户已取消操作 {action_kind}。",
        root,
    )
    return _result(False, "canceled", action, permission_decision, [event])


def _execute_action(action: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    action_kind = _action_kind(action)
    if action_kind == "update_plan_task_status":
        return _execute_update_plan_task_status(action, data_dir)
    if action_kind == "create_plan_candidate":
        return {"created_plan": _execute_create_plan_candidate(action, data_dir)}
    if action_kind == "create_today_task_candidate":
        return {"created_task": _execute_create_today_task_candidate(action, data_dir)}
    if action_kind == "save_memory_candidate":
        return {"saved_record": _execute_save_memory_candidate(action, data_dir)}
    raise ValueError(f"不支持的 action kind：{action_kind}")


def _execute_update_plan_task_status(action: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
    task_id = str(action.get("target") or payload.get("task_id") or "").strip()
    status = str(payload.get("status") or "").strip()
    note = payload.get("note")
    if not task_id:
        raise ValueError("缺少任务 target。")
    if not status:
        raise ValueError("缺少 payload.status。")
    return update_task_status(task_id, status, note=str(note) if note else None, data_dir=data_dir)


def _execute_create_plan_candidate(action: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
    path = data_dir / "plans.yaml"
    plans = _read_plans(path)
    plan = _normalize_new_plan(payload)
    existing_ids = {str(item.get("id")) for item in plans if isinstance(item, dict)}
    while plan["id"] in existing_ids:
        plan["id"] = _new_id("plan")
    plans.append(plan)
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_plans(path, plans)
    return plan


def _execute_create_today_task_candidate(action: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
    plan_id = str(payload.get("plan_id") or action.get("target") or "").strip()
    title = str(payload.get("title") or "").strip()
    if not plan_id:
        raise ValueError("缺少长期计划 plan_id。")
    if not title:
        raise ValueError("缺少今日任务标题。")
    return create_plan_task(
        {
            "id": payload.get("id"),
            "plan_id": plan_id,
            "date": payload.get("date"),
            "title": title,
            "source": payload.get("source") or "action_executor",
            "created_at": payload.get("created_at"),
        },
        data_dir=data_dir,
    )


def _execute_save_memory_candidate(action: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    target = Path(str(action.get("target") or "memories.jsonl")).name
    if target not in MEMORY_TARGETS:
        raise ValueError("save_memory_candidate 的 target 必须是 memories.jsonl 或 decisions.jsonl。")
    payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
    content = str(payload.get("content") or "").strip()
    if not content:
        raise ValueError("缺少 payload.content。")

    prefix, record_type = MEMORY_TARGETS[target]
    record = redact_sensitive(dict(payload))
    record["id"] = record.get("id") or _new_id(prefix)
    record["created_at"] = record.get("created_at") or _now_iso()
    record["type"] = record_type
    record["content"] = content
    record["source"] = record.get("source") or "action_executor"
    record["confidence"] = record.get("confidence", 0.7)
    record["tags"] = record.get("tags") if isinstance(record.get("tags"), list) else []

    path = data_dir / target
    data_dir.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return record


def _read_plans(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = read_yaml_file(path)
    if not isinstance(raw, dict):
        return []
    plans = raw.get("plans")
    if not isinstance(plans, list):
        return []
    return [dict(plan) for plan in plans if isinstance(plan, dict)]


def _normalize_new_plan(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "未命名计划").strip()
    goal = str(payload.get("goal") or title).strip()
    kind = str(payload.get("kind") or "side").strip()
    status = str(payload.get("status") or "active").strip()
    reminder_mode = str(payload.get("reminder_mode") or "passive").strip()
    plan = {
        "id": str(payload.get("id") or _new_id("plan")).strip(),
        "title": title,
        "kind": kind if kind in PLAN_KINDS else "side",
        "status": status if status in PLAN_STATUSES else "active",
        "goal": goal,
        "progress_percent": _coerce_progress(payload.get("progress_percent")),
        "reminder_mode": reminder_mode if reminder_mode in REMINDER_MODES else "passive",
    }
    if payload.get("cadence"):
        plan["cadence"] = str(payload.get("cadence"))
    if payload.get("current_stage"):
        plan["current_stage"] = str(payload.get("current_stage"))
    plan["tags"] = payload.get("tags") if isinstance(payload.get("tags"), list) else []
    return plan


def _write_plans(path: Path, plans: list[dict[str, Any]]) -> None:
    lines = ["plans:"]
    for plan in plans:
        lines.append(f"  - id: {_yaml_scalar(plan.get('id'))}")
        for key in (
            "title",
            "kind",
            "status",
            "goal",
            "progress_percent",
            "cadence",
            "reminder_mode",
            "current_stage",
        ):
            if key in plan and plan.get(key) is not None:
                lines.append(f"    {key}: {_yaml_scalar(plan.get(key))}")
        tags = plan.get("tags") if isinstance(plan.get("tags"), list) else []
        lines.append("    tags:")
        for tag in tags:
            lines.append(f"      - {_yaml_scalar(tag)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_action_event(
    event_type: str,
    action: dict[str, Any],
    permission_decision: dict[str, Any],
    status: str,
    summary: str,
    data_dir: Path,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return append_audit_event(
        {
            "event_type": event_type,
            "actor": "system",
            "module": "action_executor",
            "action_id": action.get("id") or "",
            "action_kind": _action_kind(action),
            "target": action.get("target") or "",
            "risk_level": permission_decision.get("risk_level", ""),
            "permission_mode": permission_decision.get("permission_mode", ""),
            "requires_confirmation": permission_decision.get("requires_confirmation", False),
            "status": status,
            "summary": summary,
            "payload": {
                "action": action,
                "permission_decision": permission_decision,
                **(payload or {}),
            },
            "source": "action_executor",
        },
        data_dir=data_dir,
    )


def _result(
    ok: bool,
    status: str,
    action: dict[str, Any],
    permission_decision: dict[str, Any],
    audit_events: list[dict[str, Any]],
    error_message: str | None = None,
    execution_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": ok,
        "status": status,
        "action_kind": _action_kind(action),
        "action_id": action.get("id") or "",
        "target": action.get("target") or "",
        "permission_decision": permission_decision,
        "execution_result": execution_result or {},
        "audit_events": audit_events,
    }
    if error_message:
        result["error"] = {"message": error_message}
    return result


def _action_kind(action: dict[str, Any]) -> str:
    return str(action.get("kind") or "unknown").strip() or "unknown"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().astimezone().strftime('%Y%m%d_%H%M%S_%f')}"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _coerce_progress(value: Any) -> int:
    try:
        return max(0, min(int(value or 0), 100))
    except (TypeError, ValueError):
        return 0


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value or "")
    if not text or any(char in text for char in ":#[]{}&,*!|>'\"%@`"):
        return json.dumps(text, ensure_ascii=False)
    return text
