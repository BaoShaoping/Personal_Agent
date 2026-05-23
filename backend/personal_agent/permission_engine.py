"""Read-only permission evaluation for suggested actions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .memory_store import read_yaml_file


PERMISSION_MODES = {"ask_first", "default", "trusted", "full_access"}
RISK_LEVELS = {"low", "medium", "high", "critical"}

KNOWN_ACTION_RISKS = {
    "save_memory_candidate": (
        "medium",
        "执行后会写入长期记忆。",
    ),
    "create_plan_candidate": (
        "medium",
        "执行后会创建或更新长期计划。",
    ),
    "update_plan_task_status": (
        "medium",
        "执行后会更新计划任务和进度。",
    ),
    "create_today_task_candidate": (
        "medium",
        "执行后会从长期计划写入一个今日最小任务。",
    ),
}

FORBIDDEN_ACTION_KINDS = {
    "expose_secret",
    "payment",
    "delete_files",
    "system_settings",
}

CRITICAL_ACTION_KINDS = FORBIDDEN_ACTION_KINDS | {
    "send_external_message",
    "run_shell_command",
}


def load_permission_mode(data_dir: str | Path = "data") -> str:
    """Read permission_mode from settings.yaml, falling back to ask_first."""

    path = Path(data_dir) / "settings.yaml"
    if not path.exists():
        return "ask_first"
    try:
        settings = read_yaml_file(path)
    except Exception:  # pragma: no cover - defensive fallback
        return "ask_first"
    mode = settings.get("permission_mode") if isinstance(settings, dict) else None
    return _normalize_permission_mode(mode)


def evaluate_action(
    action: dict[str, Any] | None,
    permission_mode: str = "ask_first",
) -> dict[str, Any]:
    """Evaluate an action candidate without executing it."""

    mode = _normalize_permission_mode(permission_mode)
    action_kind = _action_kind(action)
    risk_level, base_reason, hard_block = _classify_action(action_kind)

    requires_confirmation = _requires_confirmation(action_kind, risk_level, mode, hard_block)
    allowed_without_confirmation = not requires_confirmation and not hard_block
    reason = _mode_reason(action_kind, risk_level, mode, requires_confirmation, base_reason, hard_block)

    return {
        "ok": True,
        "permission_mode": mode,
        "action_kind": action_kind,
        "risk_level": risk_level,
        "requires_confirmation": requires_confirmation,
        "allowed_without_confirmation": allowed_without_confirmation,
        "reason": reason,
        "hard_block": hard_block,
    }


def _action_kind(action: dict[str, Any] | None) -> str:
    if not action:
        return "answer_only"
    kind = str(action.get("kind") or "").strip()
    return kind or "unknown"


def _classify_action(action_kind: str) -> tuple[str, str, bool]:
    if action_kind == "answer_only":
        return "low", "没有请求执行操作。", False
    if action_kind in FORBIDDEN_ACTION_KINDS:
        return "critical", "该 action kind 在 MVP 中被硬阻止。", True
    if action_kind in CRITICAL_ACTION_KINDS:
        return "critical", "关键风险操作需要确认。", False
    if action_kind in KNOWN_ACTION_RISKS:
        risk, reason = KNOWN_ACTION_RISKS[action_kind]
        return risk, reason, False
    return "high", "未知 action kind 按高风险处理。", False


def _requires_confirmation(action_kind: str, risk_level: str, mode: str, hard_block: bool) -> bool:
    if hard_block:
        return True
    if risk_level == "critical":
        return True
    if action_kind == "answer_only" or risk_level == "low":
        return False
    if mode in {"ask_first", "default"}:
        return risk_level in {"medium", "high", "critical"}
    if mode == "trusted":
        if action_kind in KNOWN_ACTION_RISKS and risk_level == "medium":
            return False
        return risk_level in {"high", "critical"}
    if mode == "full_access":
        if action_kind in KNOWN_ACTION_RISKS and risk_level in {"medium", "high"}:
            return False
        return True
    return True


def _mode_reason(
    action_kind: str,
    risk_level: str,
    mode: str,
    requires_confirmation: bool,
    base_reason: str,
    hard_block: bool,
) -> str:
    if hard_block:
        return f"{base_reason} MVP 执行器不得执行。"
    if action_kind == "answer_only":
        return "没有请求执行操作，因此不需要确认。"
    if action_kind == "unknown":
        return base_reason
    if risk_level == "critical":
        return "critical 操作始终需要确认。"
    if requires_confirmation:
        return f"{risk_level} 风险操作在 {mode} 模式下需要确认。{base_reason}"
    return f"已知 {risk_level} 风险操作在 {mode} 模式下可无需确认。{base_reason}"


def _normalize_permission_mode(permission_mode: Any) -> str:
    mode = str(permission_mode or "ask_first").strip()
    return mode if mode in PERMISSION_MODES else "ask_first"
