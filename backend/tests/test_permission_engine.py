import shutil
from pathlib import Path

from personal_agent.permission_engine import evaluate_action, load_permission_mode


ROOT = Path(__file__).resolve().parents[2]


def _action(kind):
    return {"kind": kind, "risk_level": "low", "requires_confirmation": False}


def test_answer_only_no_action_is_low_risk_without_confirmation():
    decision = evaluate_action(None, "ask_first")

    assert decision["risk_level"] == "low"
    assert decision["requires_confirmation"] is False
    assert decision["allowed_without_confirmation"] is True
    assert "不需要确认" in decision["reason"]


def test_save_memory_candidate_is_medium_risk():
    decision = evaluate_action(_action("save_memory_candidate"), "default")

    assert decision["risk_level"] == "medium"
    assert decision["requires_confirmation"] is True
    assert "长期记忆" in decision["reason"]


def test_create_plan_candidate_is_medium_risk():
    decision = evaluate_action(_action("create_plan_candidate"), "default")

    assert decision["risk_level"] == "medium"
    assert decision["requires_confirmation"] is True


def test_update_plan_task_status_is_medium_risk():
    decision = evaluate_action(_action("update_plan_task_status"), "default")

    assert decision["risk_level"] == "medium"
    assert decision["requires_confirmation"] is True


def test_create_today_task_candidate_is_medium_risk():
    decision = evaluate_action(_action("create_today_task_candidate"), "default")

    assert decision["risk_level"] == "medium"
    assert decision["requires_confirmation"] is True
    assert "今日最小任务" in decision["reason"]


def test_unknown_action_kind_is_high_risk_and_requires_confirmation():
    decision = evaluate_action(_action("unknown_tool_call"), "full_access")

    assert decision["action_kind"] == "unknown_tool_call"
    assert decision["risk_level"] == "high"
    assert decision["requires_confirmation"] is True
    assert "未知 action kind" in decision["reason"]


def test_critical_action_always_requires_confirmation_in_full_access():
    decision = evaluate_action(_action("delete_files"), "full_access")

    assert decision["risk_level"] == "critical"
    assert decision["requires_confirmation"] is True
    assert decision["hard_block"] is True
    assert "硬阻止" in decision["reason"]


def test_ask_first_requires_confirmation_for_medium_actions():
    decision = evaluate_action(_action("save_memory_candidate"), "ask_first")

    assert decision["requires_confirmation"] is True
    assert decision["allowed_without_confirmation"] is False


def test_trusted_allows_known_medium_action_without_confirmation():
    decision = evaluate_action(_action("update_plan_task_status"), "trusted")

    assert decision["risk_level"] == "medium"
    assert decision["requires_confirmation"] is False
    assert decision["allowed_without_confirmation"] is True


def test_invalid_permission_mode_falls_back_to_ask_first():
    decision = evaluate_action(_action("save_memory_candidate"), "wild_mode")

    assert decision["permission_mode"] == "ask_first"
    assert decision["requires_confirmation"] is True


def test_load_permission_mode_falls_back_for_invalid_settings():
    data_dir = ROOT / "backend" / "tests" / "_tmp_permission_settings"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    try:
        (data_dir / "settings.yaml").write_text("permission_mode: invalid\n", encoding="utf-8")

        assert load_permission_mode(data_dir) == "ask_first"
    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)
