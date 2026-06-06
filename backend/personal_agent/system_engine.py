"""System Edition state: file-backed level / exp / attributes / magic / forest.

Step 2 of the System Edition build: the data layer behind the `/api/system/summary`
contract that the panel UI renders. Storage stays local-first and transparent
(`data/system_state.yaml`), written atomically (temp file + os.replace). The YAML
writer emits a small block-style subset readable by both PyYAML and the project's
fallback parser in ``memory_store.read_yaml_file``.

Reward settlement on task completion (writes) is step 3; this module is read +
load/save only.
"""

from __future__ import annotations

import copy
import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .audit_log import append_audit_event, read_audit_events
from .memory_store import read_yaml_file
from .plan_store import list_active_plans, list_today_tasks, load_plan_data, update_task_status
from .system_voice import narrate_completion


SYSTEM_STATE_FILE = "system_state.yaml"

# Five RPG attributes mapped to real growth domains, in radar order.
ATTRIBUTES: list[tuple[str, str]] = [
    ("intellect", "智识"),
    ("constitution", "体魄"),
    ("willpower", "自律"),
    ("creativity", "创造"),
    ("spirit", "心境"),
]
ATTRIBUTE_KEYS = [key for key, _ in ATTRIBUTES]
ATTRIBUTE_LABELS = {key: label for key, label in ATTRIBUTES}

# Keyword heuristic so default task rewards land on a sensible attribute.
_ATTRIBUTE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("constitution", ("跑", "运动", "健身", "锻炼", "步", "睡", "健康")),
    ("creativity", ("写", "项目", "建造", "代码", "设计", "创作", "渲染", "面板", "做")),
    ("spirit", ("反思", "冥想", "休息", "复盘", "日记", "放松", "整理")),
    ("intellect", ("英语", "单词", "学习", "阅读", "读", "复习", "句子", "知识", "课")),
]

DEFAULT_REWARD = {"exp": 10, "magic_points": 5, "attribute_exp": 15}

DEFAULT_STATE: dict[str, Any] = {
    "version": 1,
    "character": {"name": "系统", "theme": "default"},
    "total_exp": 0,
    "magic_points": 0,
    "attributes": {key: {"exp": 0} for key in ATTRIBUTE_KEYS},
    "forest": {"growth": 0, "decorations": []},
    "unlocked_cosmetics": [],
}


# --------------------------------------------------------------------------- #
# Derivations (mirror the panel's client-side stub so values stay consistent)
# --------------------------------------------------------------------------- #
def level_threshold(level: int) -> int:
    """Exp needed to advance from ``level`` to ``level + 1``."""

    return 100 + (max(1, level) - 1) * 50


def level_info(total_exp: int) -> dict[str, Any]:
    total = max(0, int(total_exp))
    level = 1
    remaining = total
    while remaining >= level_threshold(level):
        remaining -= level_threshold(level)
        level += 1
    for_next = level_threshold(level)
    return {
        "level": level,
        "total_exp": total,
        "exp_into_level": remaining,
        "exp_for_next": for_next,
        "progress_percent": round(remaining / for_next * 100) if for_next else 0,
    }


def attribute_value(exp: int) -> int:
    """Displayed stat derived from accumulated attribute exp."""

    return int(math.floor(math.sqrt(max(0, int(exp)))))


def forest_stage(growth: int) -> str:
    growth = max(0, int(growth))
    if growth <= 0:
        return "种子"
    if growth < 4:
        return "萌芽"
    if growth < 10:
        return "树苗"
    if growth < 20:
        return "小林"
    return "森林"


def infer_attribute(task: dict[str, Any]) -> str:
    text = f"{task.get('title', '')} {task.get('plan_id', '')}"
    for attribute, keywords in _ATTRIBUTE_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return attribute
    return "willpower"


def default_task_rewards(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "exp": DEFAULT_REWARD["exp"],
        "magic_points": DEFAULT_REWARD["magic_points"],
        "attribute": infer_attribute(task),
        "attribute_exp": DEFAULT_REWARD["attribute_exp"],
    }


# --------------------------------------------------------------------------- #
# Load / save (local-first, atomic)
# --------------------------------------------------------------------------- #
def load_system_state(data_dir: str | Path = "data") -> dict[str, Any]:
    """Load system state, filling defaults for missing/partial files."""

    path = Path(data_dir) / SYSTEM_STATE_FILE
    raw: Any = {}
    if path.exists():
        try:
            raw = read_yaml_file(path)
        except Exception:  # pragma: no cover - defensive; treat as empty state
            raw = {}
    return _normalize_state(raw if isinstance(raw, dict) else {})


def save_system_state(state: dict[str, Any], data_dir: str | Path = "data") -> dict[str, Any]:
    """Atomically persist normalized system state to ``system_state.yaml``."""

    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_state(state if isinstance(state, dict) else {})
    normalized.setdefault("created_at", _now_iso())
    normalized["updated_at"] = _now_iso()

    path = root / SYSTEM_STATE_FILE
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(_dump_yaml(normalized), encoding="utf-8")
    os.replace(tmp, path)
    return normalized


# --------------------------------------------------------------------------- #
# Summary contract (GET /api/system/summary)
# --------------------------------------------------------------------------- #
def build_system_summary(data_dir: str | Path = "data") -> dict[str, Any]:
    state = load_system_state(data_dir)

    attributes = [
        {
            "key": key,
            "label": ATTRIBUTE_LABELS[key],
            "exp": state["attributes"][key]["exp"],
            "value": attribute_value(state["attributes"][key]["exp"]),
        }
        for key in ATTRIBUTE_KEYS
    ]

    growth = state["forest"]["growth"]
    forest = {
        "growth": growth,
        "stage": forest_stage(growth),
        "decorations": state["forest"]["decorations"],
    }

    quest_lines = [
        {
            "plan_id": str(plan.get("id") or ""),
            "title": str(plan.get("title") or "未命名计划"),
            "kind": plan.get("kind") if plan.get("kind") in {"main", "side"} else "side",
            "progress_percent": _coerce_int(plan.get("progress_percent"), 0),
        }
        for plan in list_active_plans(data_dir)
    ]

    today_tasks = []
    for task in list_today_tasks(data_dir=data_dir):
        rewards = task.get("rewards") if isinstance(task.get("rewards"), dict) else default_task_rewards(task)
        today_tasks.append(
            {
                "id": str(task.get("id") or ""),
                "plan_id": str(task.get("plan_id") or ""),
                "title": str(task.get("title") or ""),
                "status": str(task.get("status") or "todo"),
                "rewards": rewards,
            }
        )

    return {
        "ok": True,
        "character": dict(state["character"]),
        "level": level_info(state["total_exp"]),
        "magic_points": state["magic_points"],
        "attributes": attributes,
        "forest": forest,
        "quest_lines": quest_lines,
        "today_tasks": today_tasks,
        "recent_dings": _recent_dings(data_dir),
        "meta": {"data_dir": str(Path(data_dir)), "updated_at": state.get("updated_at", "")},
    }


def _recent_dings(data_dir: str | Path, limit: int = 8) -> list[dict[str, Any]]:
    """Surface recent reward-grant audit events as 「叮！」 feed entries.

    Populated by step 3 (reward settlement); empty until then.
    """

    events = read_audit_events(data_dir=data_dir, limit=limit, event_type="reward_granted")
    dings = []
    for event in events:
        dings.append({"at": _short_time(event.get("created_at", "")), "text": str(event.get("summary") or "")})
    return dings


# --------------------------------------------------------------------------- #
# Reward settlement (step 3) — completing a task grants exp/magic/attr/growth
# --------------------------------------------------------------------------- #
def complete_and_settle_task(task_id: str, data_dir: str | Path = "data") -> dict[str, Any]:
    """Mark a plan task done and settle its rewards into system state.

    Idempotent: a task already ``done`` is not settled again. All writes are
    persisted (atomic state write + audit event), so the loop is real and
    traceable rather than a client-side illusion.
    """

    root = Path(data_dir)
    task_id = str(task_id or "").strip()
    if not task_id:
        return {"ok": False, "error": {"message": "task_id is required"}}

    task = next((t for t in load_plan_data(root).tasks if str(t.get("id")) == task_id), None)
    if task is None:
        return {"ok": False, "error": {"message": f"task not found: {task_id}"}}
    if str(task.get("status")) == "done":
        return {"ok": True, "already_done": True, "task": task}

    update_result = update_task_status(task_id, "done", data_dir=root)
    updated_task = update_result.get("task", task)
    rewards = task.get("rewards") if isinstance(task.get("rewards"), dict) else default_task_rewards(task)
    settlement = _apply_rewards(rewards, updated_task, root)
    return {"ok": True, "already_done": False, "task": updated_task, "settlement": settlement}


def _apply_rewards(rewards: dict[str, Any], task: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    state = load_system_state(data_dir)
    before_level = level_info(state["total_exp"])["level"]

    exp = _coerce_int(rewards.get("exp"), 0)
    magic = _coerce_int(rewards.get("magic_points"), 0)
    attribute = rewards.get("attribute")
    attribute_exp = _coerce_int(rewards.get("attribute_exp"), 0)

    state["total_exp"] += exp
    state["magic_points"] += magic
    if attribute in state["attributes"]:
        state["attributes"][attribute]["exp"] += attribute_exp
    state["forest"]["growth"] += 1
    saved = save_system_state(state, data_dir)

    after = level_info(saved["total_exp"])
    leveled_up = after["level"] > before_level
    attribute_label = ATTRIBUTE_LABELS.get(attribute, "")

    ding_text = narrate_completion(
        str(task.get("title", "")), rewards, leveled_up, after["level"], attribute_label, str(data_dir)
    )

    deltas = {
        "exp": exp,
        "magic_points": magic,
        "attribute": attribute,
        "attribute_exp": attribute_exp,
        "forest_growth": 1,
    }
    _append_reward_audit(task, rewards, deltas, leveled_up, after["level"], ding_text, data_dir)

    return {
        "rewards": rewards,
        "deltas": deltas,
        "leveled_up": leveled_up,
        "level": after["level"],
        "total_exp": saved["total_exp"],
        "magic_points": saved["magic_points"],
        "forest_growth": saved["forest"]["growth"],
        "ding_text": ding_text,
    }


def _append_reward_audit(
    task: dict[str, Any],
    rewards: dict[str, Any],
    deltas: dict[str, Any],
    leveled_up: bool,
    level: int,
    ding_text: str,
    data_dir: Path,
) -> None:
    append_audit_event(
        {
            "event_type": "reward_granted",
            "actor": "system",
            "module": "system_engine",
            "action_id": str(task.get("id") or ""),
            "action_kind": "task_completed",
            "target": str(task.get("id") or ""),
            "status": "success",
            "summary": ding_text,
            "payload": {
                "task": {"id": task.get("id"), "title": task.get("title"), "plan_id": task.get("plan_id")},
                "rewards": rewards,
                "deltas": deltas,
                "leveled_up": leveled_up,
                "level": level,
            },
            "source": "system_engine",
        },
        data_dir=data_dir,
    )


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #
def _normalize_state(raw: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(DEFAULT_STATE)
    out["version"] = _coerce_int(raw.get("version"), 1) or 1

    character = raw.get("character") if isinstance(raw.get("character"), dict) else {}
    out["character"]["name"] = str(character.get("name") or "系统")
    out["character"]["theme"] = str(character.get("theme") or "default")

    out["total_exp"] = _coerce_int(raw.get("total_exp"), 0)
    out["magic_points"] = _coerce_int(raw.get("magic_points"), 0)

    attributes = raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {}
    for key in ATTRIBUTE_KEYS:
        entry = attributes.get(key) if isinstance(attributes.get(key), dict) else {}
        out["attributes"][key] = {"exp": _coerce_int(entry.get("exp"), 0)}

    forest = raw.get("forest") if isinstance(raw.get("forest"), dict) else {}
    out["forest"]["growth"] = _coerce_int(forest.get("growth"), 0)
    decorations = forest.get("decorations")
    out["forest"]["decorations"] = [d for d in decorations if isinstance(d, dict)] if isinstance(decorations, list) else []

    unlocked = raw.get("unlocked_cosmetics")
    out["unlocked_cosmetics"] = list(unlocked) if isinstance(unlocked, list) else []

    for stamp in ("created_at", "updated_at"):
        if raw.get(stamp):
            out[stamp] = str(raw[stamp])
    return out


def _dump_yaml(state: dict[str, Any]) -> str:
    """Serialize state to a block-style YAML subset both YAML readers accept."""

    return "\n".join(_dump_block(state, 0)) + "\n"


def _dump_block(value: Any, indent: int) -> list[str]:
    pad = " " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, dict):
                if item:
                    lines.append(f"{pad}{key}:")
                    lines.extend(_dump_block(item, indent + 2))
                else:
                    lines.append(f"{pad}{key}:")
            elif isinstance(item, list):
                if item:
                    lines.append(f"{pad}{key}:")
                    lines.extend(_dump_list(item, indent + 2))
                else:
                    lines.append(f"{pad}{key}: []")
            else:
                lines.append(f"{pad}{key}: {_scalar(item)}")
    else:  # pragma: no cover - top level is always a dict here
        lines.append(f"{pad}{_scalar(value)}")
    return lines


def _dump_list(items: list[Any], indent: int) -> list[str]:
    pad = " " * indent
    lines: list[str] = []
    for item in items:
        if isinstance(item, dict) and item:
            pairs = list(item.items())
            first_key, first_value = pairs[0]
            lines.append(f"{pad}- {first_key}: {_scalar(first_value)}")
            for key, value in pairs[1:]:
                lines.append(f"{pad}  {key}: {_scalar(value)}")
        else:
            lines.append(f"{pad}- {_scalar(item)}")
    return lines


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "null"
    text = str(value)
    if text == "" or text.strip() != text or any(ch in text for ch in ":#[]{}&*!|>'\"%@`,"):
        return json.dumps(text, ensure_ascii=False)
    return text


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _short_time(created_at: str) -> str:
    text = str(created_at or "")
    if "T" in text:
        clock = text.split("T", 1)[1]
        return clock[:5]
    return text[:5]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
