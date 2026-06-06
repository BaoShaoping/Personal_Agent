"""System Edition: the 系统 proposes a daily quest from the user's real plans.

Step 5 of the build. In live mode the System acts as a game master and the LLM
(GLM) returns a structured quest; in mock/offline mode, or when the LLM output
cannot be parsed, it falls back to a deterministic rule-based quest. Generated
quests are *proposals* — accepting one creates the task (audited), keeping the
"系统 proposes, 宿主 decides" safety rail.

The prompt carries lightweight memory (the plan's recent tasks and progress) and
an avoid-list so quests stay personalized and "换一个" actually returns something
different rather than repeating.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .audit_log import append_audit_event
from .model_gateway import boost_max_tokens, generate_response, load_model_config, model_info
from .plan_store import create_plan_task, list_active_plans, load_plan_data
from .system_engine import ATTRIBUTE_KEYS, default_task_rewards, infer_attribute


SYSTEM_QUEST_PROMPT = """你是绑定在宿主身上的专属「系统」——像网络小说里的那种「系统」：温暖、鼓励、带一点游戏仪式感，称用户为「宿主」。
你根据宿主真实的长期计划、最近进展和已有任务，提出 ONE 个今天就能完成的最小任务（quest）。

硬性要求：
- **必须用简体中文**输出 title 和 system_voice（无论计划本身是什么语言，都要翻成中文表达）。
- 任务要小、具体、今天能完成（约 15-30 分钟），并且**要新颖**，不要重复宿主已有/已做过的任务。
- 只输出一个 JSON 对象，不要任何额外文字、解释或多余内容。
- JSON 字段：
  - title: 字符串，简体中文任务标题
  - attribute: 必须是 intellect / constitution / willpower / creativity / spirit 之一
  - exp: 整数，5-30
  - magic_points: 整数，3-15
  - attribute_exp: 整数，10-40
  - system_voice: 一句简体中文的系统口吻台词，温暖鼓励，可用「叮！」开头

语气温暖、鼓励、有「系统」仪式感。绝不惩罚或施压。"""

_RULE_QUEST_TEMPLATES = [
    "推进「{title}」：完成一个 25 分钟专注块",
    "为「{title}」做一件最小但具体的小事",
    "围绕「{title}」复盘 5 分钟，并记下一条心得",
    "在「{title}」上前进一小步，哪怕只用 15 分钟",
    "为「{title}」整理一个清晰的下一步",
]


def generate_quest(
    data_dir: str = "data",
    plan_id: str | None = None,
    avoid_titles: list[str] | None = None,
) -> dict[str, Any]:
    """Propose one daily quest for an active plan (LLM in live mode, else rule-based).

    ``avoid_titles`` (e.g. from "换一个") plus the plan's recent task titles are fed
    to the model so the quest is new and personalized.
    """

    plans = list_active_plans(data_dir)
    if not plans:
        return {"ok": False, "error": {"message": "没有激活中的长期计划。"}}

    plan = _pick_plan(plans, plan_id)
    history = _plan_history(str(plan.get("id") or ""), data_dir)
    avoid = list(dict.fromkeys([t for t in [*(avoid_titles or []), *history["titles"]] if t]))
    config = load_model_config(data_dir)

    if config.get("mode") == "live":
        quest = _llm_quest(plan, config, avoid, history["progress"])
        if quest:
            return {"ok": True, "source": "llm", "quest": quest, "target_plan": _plan_brief(plan), "model_info": model_info(config)}

    return {"ok": True, "source": "mock", "quest": _rule_quest(plan, avoid), "target_plan": _plan_brief(plan), "model_info": model_info(config)}


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
def _plan_history(plan_id: str, data_dir: str, title_limit: int = 10, progress_limit: int = 5) -> dict[str, list[str]]:
    """Recent task titles (for avoid/dedup) and progress notes (for context)."""

    if not plan_id:
        return {"titles": [], "progress": []}
    data = load_plan_data(data_dir)
    titles = [str(t.get("title")) for t in data.tasks if str(t.get("plan_id")) == plan_id and t.get("title")]
    progress = [str(p.get("summary")) for p in data.progress if str(p.get("plan_id")) == plan_id and p.get("summary")]
    return {
        "titles": list(dict.fromkeys(titles))[-title_limit:],
        "progress": progress[-progress_limit:],
    }


def _llm_quest(plan: dict[str, Any], config: dict[str, Any], avoid: list[str], progress: list[str]) -> dict[str, Any] | None:
    messages = [
        {"role": "system", "content": SYSTEM_QUEST_PROMPT},
        {"role": "user", "content": _plan_prompt(plan, avoid, progress)},
    ]
    # Reasoning enabled, generous token budget, and a higher temperature so
    # repeated requests ("换一个") actually vary.
    quest_config = {**boost_max_tokens(config), "temperature": 0.9}
    response = generate_response(messages, quest_config)
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


def _rule_quest(plan: dict[str, Any], avoid: list[str] | None = None) -> dict[str, Any]:
    base = str(plan.get("title") or "计划")
    avoid_set = {a for a in (avoid or []) if a}
    options = [template.format(title=base) for template in _RULE_QUEST_TEMPLATES]
    title = next((option for option in options if option not in avoid_set), options[0])
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


def _plan_prompt(plan: dict[str, Any], avoid: list[str] | None = None, progress: list[str] | None = None) -> str:
    lines = [
        f"长期计划：{plan.get('title', '')}",
        f"目标：{plan.get('goal', '')}",
    ]
    if plan.get("current_stage"):
        lines.append(f"当前阶段：{plan.get('current_stage')}")
    lines.append(f"进度：{plan.get('progress_percent', 0)}%")

    progress = [p for p in (progress or []) if p]
    if progress:
        lines.append("")
        lines.append("宿主最近的进展：")
        lines.extend(f"- {item}" for item in progress[-5:])

    avoid = [a for a in (avoid or []) if a]
    if avoid:
        lines.append("")
        lines.append("宿主最近已经有过下面这些任务，请【不要重复】，换一个不同角度的新任务：")
        lines.extend(f"- {title}" for title in avoid[:12])

    lines.append("")
    lines.append("请提出今天的一个最小任务（quest），要新颖、与上面已有任务不同，按要求只返回 JSON。")
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
