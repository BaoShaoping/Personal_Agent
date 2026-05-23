"""Rule-based, read-only suggestion engine for the MVP."""

from __future__ import annotations

from datetime import datetime
from typing import Any


TASK_DONE_TERMS = ("完成", "做完", "已完成", "finished", "done", "completed")
TASK_SKIPPED_TERMS = ("没完成", "没有完成", "未完成", "跳过", "skipped", "skip")
TASK_BLOCKED_TERMS = ("卡住", "阻塞", "不会做", "不會做", "blocked", "stuck")

MEMORY_TERMS = (
    "记住",
    "記住",
    "保存",
    "帮我记",
    "幫我記",
    "这是一个决定",
    "這是一個決定",
    "以后提醒我",
    "以後提醒我",
    "remember",
    "save this",
    "decision",
)

PLAN_TERMS = ("长期", "長期", "计划", "計劃", "每天", "每周", "提升", "学习", "學習", "准备", "準備", "坚持")

PLAN_TERMS = PLAN_TERMS + (
    "long-term",
    "plan",
    "every day",
    "every week",
    "improve",
    "learn",
    "study",
    "prepare",
)

TODAY_TASK_REQUEST_TERMS = (
    "今天做什么",
    "今天我适合",
    "今天应该",
    "今天可以完成",
    "今日任务",
    "生成今日任务",
    "安排今天任务",
    "给我安排今天",
    "下一步",
    "最小任务",
    "what should i do today",
    "today task",
    "next step",
)

ACTION_KINDS = {
    "save_memory_candidate",
    "create_plan_candidate",
    "update_plan_task_status",
    "create_today_task_candidate",
}


def suggest_next_action(
    user_message: str,
    context_pack: dict[str, Any],
    ask_result: dict[str, Any] | None = None,
    plan_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return answer_only or a suggested_action shape without side effects."""

    message = str(user_message or "").strip()
    normalized = message.lower()
    context_pack = context_pack or {}
    ask_result = ask_result or {}
    plan_context = plan_context or context_pack.get("plan_context") or {}

    today_tasks = _ensure_list(plan_context.get("today_tasks"))
    if today_tasks:
        task = today_tasks[0]
        status = _infer_task_status(normalized)
        if status:
            return _suggest_task_status(message, task, status)

    active_plans = _ensure_list(plan_context.get("active_plans")) or _ensure_list(context_pack.get("active_plans"))
    if _should_suggest_today_task(normalized, today_tasks, active_plans):
        return _suggest_today_task(message, active_plans[0])

    if _contains_any(normalized, MEMORY_TERMS):
        return _suggest_memory_candidate(message, context_pack)

    if _contains_any(normalized, PLAN_TERMS) and not _has_matching_active_plan(normalized, context_pack, plan_context):
        return _suggest_create_plan(message)

    return {
        "type": "answer_only",
        "answer": ask_result.get("answer") or "",
        "reason": "当前没有需要执行的安全具体操作。",
    }


def _infer_task_status(message: str) -> str | None:
    if _contains_any(message, TASK_SKIPPED_TERMS):
        return "skipped"
    if _contains_any(message, TASK_BLOCKED_TERMS):
        return "blocked"
    if _contains_any(message, TASK_DONE_TERMS):
        return "done"
    return None


def _suggest_task_status(user_message: str, task: dict[str, Any], status: str) -> dict[str, Any]:
    task_id = str(task.get("id") or "")
    title = str(task.get("title") or task_id)
    status_messages = {
        "done": "你提到今天的任务已完成。要把它标记为 done 吗？",
        "skipped": "你提到今天的任务被跳过或未完成。要把它标记为 skipped 吗？",
        "blocked": "你提到今天的任务卡住了。要把它标记为 blocked 吗？",
    }
    notes = {
        "done": "用户表示任务已完成。",
        "skipped": "用户表示任务被跳过或未完成。",
        "blocked": "用户表示任务卡住了。",
    }
    return {
        "type": "suggested_action",
        "title": "更新任务状态",
        "message": status_messages[status],
        "action": _build_action(
            kind="update_plan_task_status",
            title="更新任务状态",
            summary=status_messages[status],
            target=task_id,
            payload={
                "status": status,
                "note": notes[status],
                "task_title": title,
                "user_message": user_message,
            },
        ),
        "buttons": ["confirm", "cancel"],
        "reason": "用户意图指向一个明确的计划任务状态更新。",
    }


def _suggest_memory_candidate(user_message: str, context_pack: dict[str, Any]) -> dict[str, Any]:
    target = "decisions.jsonl" if _contains_any(user_message.lower(), ("决定", "決定", "decision")) else "memories.jsonl"
    return {
        "type": "suggested_action",
        "title": "保存记忆候选",
        "message": "这段内容可能适合作为长期上下文。要保存为记忆候选吗？",
        "action": _build_action(
            kind="save_memory_candidate",
            title="保存记忆候选",
            summary="将用户提供的内容保存为记忆候选。",
            target=target,
            payload={
                "content": user_message,
                "source": "suggestion_engine",
                "context_sources": context_pack.get("sources", []),
            },
        ),
        "buttons": ["confirm", "cancel"],
        "reason": "用户表达了偏好、决定、提醒或记忆保存意图。",
    }


def _suggest_create_plan(user_message: str) -> dict[str, Any]:
    return {
        "type": "suggested_action",
        "title": "创建计划候选",
        "message": "这听起来像一个长期方向。要先生成一个计划候选吗？",
        "action": _build_action(
            kind="create_plan_candidate",
            title="创建计划候选",
            summary="根据用户消息生成一个长期计划候选。",
            target="plans.yaml",
            payload={
                "title": _derive_plan_title(user_message),
                "goal": user_message,
                "kind": "side",
                "status": "active",
                "reminder_mode": "passive",
            },
        ),
        "buttons": ["confirm", "cancel"],
        "reason": "用户意图指向长期学习或提升计划，且没有匹配到明显的现有活跃计划。",
    }


def _suggest_today_task(user_message: str, plan: dict[str, Any]) -> dict[str, Any]:
    plan_id = str(plan.get("id") or "").strip()
    task_title = _derive_today_task_title(plan)
    return {
        "type": "suggested_action",
        "title": "生成今日最小任务",
        "message": f"今天还没有任务。要从「{plan.get('title') or plan_id}」生成一个可以完成的小任务吗？",
        "action": _build_action(
            kind="create_today_task_candidate",
            title="生成今日最小任务",
            summary="从长期计划生成一个今天可以执行的小任务。",
            target=plan_id,
            payload={
                "plan_id": plan_id,
                "title": task_title,
                "date": datetime.now().astimezone().date().isoformat(),
                "source": "suggestion_engine",
                "user_message": user_message,
            },
        ),
        "buttons": ["confirm", "cancel"],
        "reason": "今日任务为空，且存在活跃长期计划；建议先生成一个最小可执行任务。",
    }


def _build_action(
    kind: str,
    title: str,
    summary: str,
    target: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": _new_action_id(),
        "kind": kind,
        "title": title,
        "summary": summary,
        "target": target,
        "payload": payload,
        "source": "suggestion_engine",
        "created_at": _now_iso(),
        "risk_level": "medium",
        "requires_confirmation": True,
    }


def _new_action_id() -> str:
    return "act_" + datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _has_matching_active_plan(message: str, context_pack: dict[str, Any], plan_context: dict[str, Any]) -> bool:
    active_plans = _ensure_list(plan_context.get("active_plans")) or _ensure_list(context_pack.get("active_plans"))
    if not active_plans:
        return False

    for plan in active_plans:
        searchable = " ".join(
            str(value)
            for value in (
                plan.get("id"),
                plan.get("title"),
                plan.get("goal"),
                plan.get("current_stage"),
                " ".join(map(str, _ensure_list(plan.get("tags")))),
            )
            if value
        ).lower()
        if searchable and any(term.lower() in message and term.lower() in searchable for term in _important_terms(message)):
            return True
    return False


def _should_suggest_today_task(message: str, today_tasks: list[Any], active_plans: list[Any]) -> bool:
    if today_tasks or not active_plans:
        return False
    return _contains_any(message, TODAY_TASK_REQUEST_TERMS)


def _important_terms(message: str) -> list[str]:
    terms = []
    for candidate in ("english", "英语", "英文", "personal context agent", "ai", "python"):
        if candidate in message:
            terms.append(candidate)
    return terms


def _derive_plan_title(user_message: str) -> str:
    cleaned = " ".join(user_message.split())
    if len(cleaned) <= 48:
        return cleaned
    return cleaned[:45].rstrip() + "..."


def _derive_today_task_title(plan: dict[str, Any]) -> str:
    searchable = " ".join(
        str(value)
        for value in (
            plan.get("id"),
            plan.get("title"),
            plan.get("goal"),
            plan.get("current_stage"),
            " ".join(map(str, _ensure_list(plan.get("tags")))),
        )
        if value
    ).lower()
    title = str(plan.get("title") or plan.get("id") or "长期计划").strip()
    if any(term in searchable for term in ("english", "英语", "英文", "vocabulary", "word")):
        return "背 10 个英语单词，并写 1 句简单例句"
    if any(term in searchable for term in ("personal context agent", "personal agent", "ai product", "mvp", "系统面板")):
        return "整理 1 个成长系统面板的最小改进点"
    if "python" in searchable:
        return "练习 1 个 Python 小例子，并记录卡点"
    return f"推进「{title}」的 15 分钟最小步骤"


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term.lower() in text for term in terms)


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
