import json
import shutil
from datetime import date
from pathlib import Path

from personal_agent import api as debug_api
from personal_agent.audit_log import read_audit_events
from personal_agent.memory_store import read_jsonl_file, read_yaml_file


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def request(method, path, **kwargs):
    with debug_api.app.test_client() as client:
        return client.open(path, method=method, **kwargs)


def _copy_data(name):
    data_dir = ROOT / "backend" / "tests" / name
    if data_dir.exists():
        shutil.rmtree(data_dir)
    shutil.copytree(DATA_DIR, data_dir)
    audit_file = data_dir / "audit_log.jsonl"
    if audit_file.exists():
        audit_file.unlink()
    # Hermetic: drop runtime today-dated tasks so local panel usage cannot pollute tests.
    _remove_today_tasks(data_dir)
    return data_dir


def _append_today_task(data_dir):
    task = {
        "id": "task_e2e_today_001",
        "plan_id": "plan_english_001",
        "date": date.today().isoformat(),
        "title": "E2E test task",
        "status": "todo",
        "source": "test",
    }
    with (data_dir / "plan_tasks.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(task, ensure_ascii=False, separators=(",", ":")) + "\n")
    return task


def _remove_today_tasks(data_dir):
    tasks = [task for task in read_jsonl_file(data_dir / "plan_tasks.jsonl") if task.get("date") != date.today().isoformat()]
    with (data_dir / "plan_tasks.jsonl").open("w", encoding="utf-8") as handle:
        for task in tasks:
            handle.write(json.dumps(task, ensure_ascii=False, separators=(",", ":")) + "\n")


def test_e2e_answer_only_and_permission_modes(monkeypatch):
    data_dir = _copy_data("_tmp_e2e_answer_permission")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)

        response = request(
            "POST",
            "/api/suggest/with-permission",
            json={"user_message": "What modules are implemented?", "include_ask": False, "permission_mode": "ask_first"},
        )
        answer_only = response.get_json()

        assert response.status_code == 200
        assert answer_only["suggestion"]["type"] == "answer_only"
        assert answer_only["permission_decision"]["action_kind"] == "answer_only"
        assert answer_only["permission_decision"]["requires_confirmation"] is False

        ask_first_response = request(
            "POST",
            "/api/suggest/with-permission",
            json={
                "user_message": "please remember: I prefer direct answers.",
                "include_ask": False,
                "permission_mode": "ask_first",
            },
        )
        trusted_response = request(
            "POST",
            "/api/suggest/with-permission",
            json={
                "user_message": "please remember: I prefer direct answers.",
                "include_ask": False,
                "permission_mode": "trusted",
            },
        )
        ask_first = ask_first_response.get_json()
        trusted = trusted_response.get_json()
        action = ask_first["suggestion"]["action"]

        assert ask_first["suggestion"]["type"] == "suggested_action"
        assert ask_first["permission_decision"]["requires_confirmation"] is True
        assert trusted["permission_decision"]["requires_confirmation"] is False
        assert action["id"].startswith("act_")
        assert action["source"] == "suggestion_engine"
        assert action["title"] == ask_first["suggestion"]["title"]
        assert action["summary"]
        assert "T" in action["created_at"]
    finally:
        shutil.rmtree(data_dir)


def test_e2e_save_memory_confirm_and_cancel_plan(monkeypatch):
    data_dir = _copy_data("_tmp_e2e_memory_cancel")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)
        before_memories = len(read_jsonl_file(data_dir / "memories.jsonl"))
        before_plans = len(read_yaml_file(data_dir / "plans.yaml")["plans"])

        suggest_response = request(
            "POST",
            "/api/suggest/with-permission",
            json={
                "user_message": "please remember: E2E prefers explicit confirmation.",
                "include_ask": False,
                "permission_mode": "ask_first",
            },
        )
        suggested = suggest_response.get_json()
        confirm_response = request(
            "POST",
            "/api/actions/confirm",
            json={
                "action": suggested["suggestion"]["action"],
                "permission_decision": suggested["permission_decision"],
            },
        )

        assert confirm_response.status_code == 200
        assert confirm_response.get_json()["execution"]["status"] == "executed"
        assert len(read_jsonl_file(data_dir / "memories.jsonl")) == before_memories + 1

        plan_action = {
            "id": "act_e2e_cancel_plan",
            "kind": "create_plan_candidate",
            "title": "创建计划候选",
            "summary": "取消这个计划候选。",
            "target": "plans.yaml",
            "payload": {"title": "Canceled E2E plan", "goal": "Should not be written."},
            "source": "test",
            "created_at": "2026-05-09T00:00:00+08:00",
        }
        cancel_response = request(
            "POST",
            "/api/actions/cancel",
            json={"action": plan_action, "permission_decision": {"action_kind": "create_plan_candidate"}},
        )

        assert cancel_response.status_code == 200
        assert cancel_response.get_json()["execution"]["status"] == "canceled"
        assert len(read_yaml_file(data_dir / "plans.yaml")["plans"]) == before_plans
    finally:
        shutil.rmtree(data_dir)


def test_e2e_create_plan_candidate_confirm(monkeypatch):
    data_dir = _copy_data("_tmp_e2e_create_plan")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)
        before_plans = len(read_yaml_file(data_dir / "plans.yaml")["plans"])

        suggest_response = request(
            "POST",
            "/api/suggest/with-permission",
            json={
                "user_message": "I want a long-term plan to improve Python ability.",
                "include_ask": False,
                "permission_mode": "ask_first",
            },
        )
        suggested = suggest_response.get_json()

        assert suggested["suggestion"]["action"]["kind"] == "create_plan_candidate"

        confirm_response = request(
            "POST",
            "/api/actions/confirm",
            json={
                "action": suggested["suggestion"]["action"],
                "permission_decision": suggested["permission_decision"],
            },
        )

        assert confirm_response.status_code == 200
        assert confirm_response.get_json()["execution"]["status"] == "executed"
        plans = read_yaml_file(data_dir / "plans.yaml")["plans"]
        assert len(plans) == before_plans + 1
        assert "Python" in plans[-1]["goal"]
    finally:
        shutil.rmtree(data_dir)


def test_e2e_update_plan_task_status_confirm(monkeypatch):
    data_dir = _copy_data("_tmp_e2e_update_task")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)
        task = _append_today_task(data_dir)

        suggest_response = request(
            "POST",
            "/api/suggest/with-permission",
            json={
                "user_message": "I finished today's task.",
                "include_ask": False,
                "permission_mode": "trusted",
            },
        )
        suggested = suggest_response.get_json()

        assert suggested["suggestion"]["action"]["kind"] == "update_plan_task_status"
        assert suggested["suggestion"]["action"]["target"] == task["id"]
        assert suggested["permission_decision"]["requires_confirmation"] is False

        confirm_response = request(
            "POST",
            "/api/actions/confirm",
            json={
                "action": suggested["suggestion"]["action"],
                "permission_decision": suggested["permission_decision"],
            },
        )
        tasks = read_jsonl_file(data_dir / "plan_tasks.jsonl")
        updated = next(item for item in tasks if item["id"] == task["id"])

        assert confirm_response.status_code == 200
        assert confirm_response.get_json()["execution"]["status"] == "executed"
        assert updated["status"] == "done"
    finally:
        shutil.rmtree(data_dir)


def test_e2e_create_today_task_from_suggestion_confirm(monkeypatch):
    data_dir = _copy_data("_tmp_e2e_create_today_task")
    try:
        _remove_today_tasks(data_dir)
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)

        before_summary = request("GET", "/api/plans/summary").get_json()
        assert before_summary["today_tasks"] == []

        suggest_response = request(
            "POST",
            "/api/suggest/with-permission",
            json={
                "user_message": "根据我的长期计划，生成一个今天可以完成的最小任务。",
                "include_ask": False,
                "permission_mode": "ask_first",
            },
        )
        suggested = suggest_response.get_json()

        assert suggest_response.status_code == 200
        assert suggested["suggestion"]["action"]["kind"] == "create_today_task_candidate"
        assert suggested["permission_decision"]["risk_level"] == "medium"
        assert suggested["permission_decision"]["requires_confirmation"] is True

        confirm_response = request(
            "POST",
            "/api/actions/confirm",
            json={
                "action": suggested["suggestion"]["action"],
                "permission_decision": suggested["permission_decision"],
            },
        )
        after_summary = request("GET", "/api/plans/summary").get_json()

        assert confirm_response.status_code == 200
        assert confirm_response.get_json()["execution"]["status"] == "executed"
        assert len(after_summary["today_tasks"]) == 1
        assert after_summary["today_tasks"][0]["status"] == "todo"
        assert after_summary["today_tasks"][0]["date"] == date.today().isoformat()
        assert after_summary["today_tasks"][0]["source"] == "suggestion_engine"
        executed_events = read_audit_events(data_dir=data_dir, event_type="action_executed")
        assert executed_events[0]["action_kind"] == "create_today_task_candidate"
    finally:
        shutil.rmtree(data_dir)


def test_e2e_hard_block_and_unsupported_actions_fail_with_audit(monkeypatch):
    data_dir = _copy_data("_tmp_e2e_failed_actions")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)

        hard_block_response = request(
            "POST",
            "/api/actions/confirm",
            json={"action": {"id": "act_e2e_delete", "kind": "delete_files", "target": "data"}, "permission_mode": "full_access"},
        )
        unsupported_response = request(
            "POST",
            "/api/actions/confirm",
            json={
                "action": {"id": "act_e2e_shell", "kind": "run_shell_command", "target": "pwsh"},
                "permission_decision": {
                    "permission_mode": "full_access",
                    "action_kind": "run_shell_command",
                    "risk_level": "critical",
                    "requires_confirmation": True,
                    "hard_block": False,
                },
            },
        )

        assert hard_block_response.status_code == 200
        assert hard_block_response.get_json()["execution"]["status"] == "failed"
        assert unsupported_response.status_code == 200
        assert unsupported_response.get_json()["execution"]["status"] == "failed"

        failed_events = read_audit_events(data_dir=data_dir, event_type="action_failed")
        failed_kinds = {event["action_kind"] for event in failed_events}
        assert {"delete_files", "run_shell_command"}.issubset(failed_kinds)
    finally:
        shutil.rmtree(data_dir)


def test_e2e_audit_trace_contains_expected_event_types(monkeypatch):
    data_dir = _copy_data("_tmp_e2e_audit_trace")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)

        action = {
            "id": "act_e2e_trace_memory",
            "kind": "save_memory_candidate",
            "target": "memories.jsonl",
            "payload": {"content": "Trace audit memory."},
        }
        permission = request(
            "POST",
            "/api/permission/evaluate",
            json={"action": action, "permission_mode": "ask_first"},
        ).get_json()["decision"]
        request("POST", "/api/actions/confirm", json={"action": action, "permission_decision": permission})
        request("POST", "/api/actions/cancel", json={"action": {**action, "id": "act_e2e_trace_cancel"}})
        request(
            "POST",
            "/api/actions/confirm",
            json={"action": {"id": "act_e2e_trace_bad", "kind": "unknown_action"}, "permission_mode": "ask_first"},
        )

        event_types = {event["event_type"] for event in read_audit_events(data_dir=data_dir, limit=20)}
        assert {
            "permission_evaluated",
            "action_confirmed",
            "action_canceled",
            "action_executed",
            "action_failed",
        }.issubset(event_types)
    finally:
        shutil.rmtree(data_dir)


def test_debug_console_has_closed_loop_controls():
    response = request("GET", "/debug")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="suggest-permission-mode"' in html
    assert 'id="confirm-action"' in html
    assert 'id="cancel-action"' in html
    assert 'id="audit-log"' in html
