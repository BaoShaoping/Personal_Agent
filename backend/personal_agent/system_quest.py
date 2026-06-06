"""System Edition: the 系统 proposes a daily quest from the user's real plans.

Step 5 of the build. In live mode the System acts as a game master and the LLM
(GLM) returns a structured quest; in mock/offline mode, or when the LLM output
cannot be parsed, it falls back to a deterministic rule-based quest. Generated
quests are *proposals* — accepting one creates the task (audited), keeping the
"系统 proposes, 宿主 decides" safety rail.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .audit_log import append_audit_event
from .model_gateway import boost_max_tokens, generate_response, load_model_config, model_info
from .plan_store import create_plan_task, list_active_plans
from .system_engine import ATTRIBUTE_KEYS, default_task_rewards, infer_attribute


SYSTEM_QUEST_PROMPT = """你是宿主的专属「系统」，名为系统。
你基于宿主真实的长期计划，提出 ONE 个今天就能完成的最小任务（quest）。

要求：
- 任务要小、具体、今天能完成（例如 15-30 分钟内）。
- 只输出一个 JSON 对象，不要任何额外文字或解释。
- JSON 字段：
  - title: 字符串，任务标题
  - attribute: 必须是 intellect / constitution / willpower / creativity / spirit 之一
  - exp: 整数，5-30
  - magic_points: 整数，3-15
  - attribute_exp: 整数，10-40
  - system_voice: 一句系统口吻的话，温暖鼓励，可含「叮！」

语气温暖、鼓励、略带系统仪式感。绝不惩罚或施压。"""


def generate_quest(data_dir: str = "data", plan_id: str | None = None) -> dict[str, Any]:
    """Propose one daily quest for an active plan (LLM in live mode, else rule-based)."""

    plans = list_active_plans(data_dir)
    if not plans:
        return {"ok": False, "error": {"message": "没有激活中的长期计划。"}}

    plan = _pick_plan(plans, plan_id)
    config = load_model_config(data_dir)

    if config.get("mode") == "live":
        quest = _llm_quest(plan, config)
        if quest:
            return {"ok": True, "source": "llm", "quest": quest, "target_plan": _plan_brief(plan), "model_info": model_info(config)}

    return {"ok": True, "source": "mock", "quest": _rule_quest(plan), "target_plan": _plan_brief(plan), "model_info": model_info(config)}


def accept_quest(quest: dict[str, Any], data_dir: str = "data") -> dict[str, Any]:
    """Create a today task from an accepted quest proposal and audit it."""

    quest = quest if isinstance(quest, dict) else {}
    plan_id = str(quest.get("plan_id") or "").strip()
    title = str(quest.get("title") or "").strip()
    if not plan_id or not title:
        return {"ok": False, "error": {"message": "quest 需要 plan_id 和 title。"}}

    rewards = quest.get("rewards") if isinstance(quest.get("rewards"), dict) else default_task_rewards(quest)
    try:
        task = create_plan_task(
            {"plan_id": plan_id, "title": title, "rewards": rewards, "source": "system_quest"},
            data_dir=data_dir,
        )
    except Exception as exc:
        return {"ok": False, "error": {"message": str(exc), "type": exc.__class__.__name__}}

    append_audit_event(
        {
            "event_type": "plan_updated",
            "actor": "system",
            "module": "system_quest",
            "action_id": str(task.get("id") or ""),
            "action_kind": "quest_accepted",
            "target": plan_id,
            "status": "success",
            "summary": f"宿主接受系统任务：{title}",
            "payload": {"task": task, "rewards": rewards},
            "source": "system_quest",
        },
        data_dir=data_dir,
    )
    return {"ok": True, "task": task}


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #
def _llm_quest(plan: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
    messages = [
        {"role": "system", "content": SYSTEM_QUEST_PROMPT},
        {"role": "user", "content": _plan_prompt(plan)},
    ]
    response = generate_response(messages, boost_max_tokens(config))
    if not response.get("ok"):
        return None
    return _parse_quest(str(response.get("answer") or ""), plan)


def _parse_quest(answer: str, plan: dict[str, Any]) -> dict[str, Any] | None:
    candidate = _extract_json_object(answer)
    if not candidate:
        return None
    try:
        data = json.loads(candidate)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    title = str(data.get("title") or "").strip()
    if not title:
        return None
    attribute = data.get("attribute")
    if attribute not in ATTRIBUTE_KEYS:
        attribute = infer_attribute({"title": title, "plan_id": plan.get("id")})

    return {
        "plan_id": str(plan.get("id") or ""),
        "title": title,
        "rewards": {
            "exp": _clamp(data.get("exp"), 5, 30, 10),
            "magic_points": _clamp(data.get("magic_points"), 3, 15, 5),
            "attribute": attribute,
            "attribute_exp": _clamp(data.get("attribute_exp"), 10, 40, 15),
        },
        "system_voice": str(data.get("system_voice") or "").strip() or _voice(title),
    }


def _rule_quest(plan: dict[str, Any]) -> dict[str, Any]:
    title = f"推进「{plan.get('title', '计划')}」：完成一个 25 分钟专注块"
    rewards = default_task_rewards({"title": title, "plan_id": plan.get("id")})
    return {"plan_id": str(plan.get("id") or ""), "title": title, "rewards": rewards, "system_voice": _voice(title)}


def _pick_plan(plans: list[dict[str, Any]], plan_id: str | None) -> dict[str, Any]:
    if plan_id:
        for plan in plans:
            if str(plan.get("id")) == str(plan_id):
                return plan
    for plan in plans:
        if plan.get("kind") == "main":
            return plan
    return plans[0]


def _plan_brief(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(plan.get("id") or ""),
        "title": str(plan.get("title") or ""),
        "kind": plan.get("kind") if plan.get("kind") in {"main", "side"} else "side",
        "progress_percent": plan.get("progress_percent", 0),
    }


def _plan_prompt(plan: dict[str, Any]) -> str:
    lines = [
        f"长期计划：{plan.get('title', '')}",
        f"目标：{plan.get('goal', '')}",
    ]
    if plan.get("current_stage"):
        lines.append(f"当前阶段：{plan.get('current_stage')}")
    lines.append(f"进度：{plan.get('progress_percent', 0)}%")
    lines.append("请为这个计划提出今天的一个最小任务（quest），按要求只返回 JSON。")
    return "\n".join(lines)


def _voice(title: str) -> str:
    return f"叮！宿主，今日推荐任务：{title}。完成它，离目标更近一步。"


def _extract_json_object(text: str) -> str | None:
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        return fenced.group(1)
    match = re.search(r"\{.*\}", text, re.S)
    return match.group(0) if match else None


def _clamp(value: Any, low: int, high: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(number, high))
