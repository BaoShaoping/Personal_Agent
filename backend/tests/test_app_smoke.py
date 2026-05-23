import json
import shutil
from datetime import date
from pathlib import Path

from personal_agent import api as debug_api
from personal_agent.demo_seed_reset import reset_demo_today_tasks
from personal_agent.memory_store import read_jsonl_file


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
    return data_dir


def _append_today_task(data_dir):
    task = {
        "id": "task_app_smoke_seed_today",
        "plan_id": "plan_english_001",
        "date": date.today().isoformat(),
        "title": "Temporary smoke seed task",
        "status": "todo",
        "source": "test",
    }
    with (data_dir / "plan_tasks.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(task, ensure_ascii=False, separators=(",", ":")) + "\n")
    return task


def test_app_growth_loop_freeze_path_smoke(monkeypatch):
    data_dir = _copy_data("_tmp_app_growth_loop_smoke")
    try:
        _append_today_task(data_dir)
        reset_result = reset_demo_today_tasks(data_dir=data_dir)
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)

        assert reset_result["ok"] is True
        assert reset_result["removed_count"] == 1
        assert Path(reset_result["archive_path"]).exists()

        app_response = request("GET", "/app")
        js_response = request("GET", "/static/app.js")
        css_response = request("GET", "/static/app.css")

        assert app_response.status_code == 200
        assert js_response.status_code == 200
        assert css_response.status_code == 200
        assert '<main class="app-shell">' in app_response.text
        assert 'id="action-card"' in app_response.text
        assert 'id="action-json"' in app_response.text
        assert "GENERATE_TODAY_TASK_PROMPT" in js_response.text
        assert "/api/suggest/with-permission" in js_response.text
        assert "/api/actions/confirm" in js_response.text
        assert "json-details" in js_response.text
        assert "pretty({" in js_response.text

        before_summary = request("GET", "/api/plans/summary").get_json()
        assert before_summary["ok"] is True
        assert before_summary["active_plans"]
        assert before_summary["today_tasks"] == []

        suggest_response = request(
            "POST",
            "/api/suggest/with-permission",
            json={
                "user_message": "what should i do today? suggest one next step",
                "include_ask": False,
                "permission_mode": "ask_first",
            },
        )
        suggested = suggest_response.get_json()
        suggestion = suggested["suggestion"]
        permission = suggested["permission_decision"]
        action = suggestion["action"]

        assert suggest_response.status_code == 200
        assert suggested["ok"] is True
        assert suggestion["type"] == "suggested_action"
        assert suggestion["buttons"] == ["confirm", "cancel"]
        assert action["kind"] == "create_today_task_candidate"
        assert action["requires_confirmation"] is True
        assert permission["action_kind"] == "create_today_task_candidate"
        assert permission["requires_confirmation"] is True
        assert permission["risk_level"] == "medium"

        confirm_response = request(
            "POST",
            "/api/actions/confirm",
            json={
                "action": action,
                "permission_decision": permission,
            },
        )
        confirmed = confirm_response.get_json()

        assert confirm_response.status_code == 200
        assert confirmed["ok"] is True
        assert confirmed["execution"]["status"] == "executed"
        assert confirmed["execution"]["action_kind"] == "create_today_task_candidate"
        assert confirmed["execution"]["execution_result"]["created_task"]["date"] == date.today().isoformat()

        after_summary = request("GET", "/api/plans/summary").get_json()
        assert len(after_summary["today_tasks"]) == 1
        created_task = after_summary["today_tasks"][0]
        assert created_task["status"] == "todo"
        assert created_task["source"] == "suggestion_engine"

        audit_response = request("GET", "/api/audit/events?event_type=action_executed&limit=5")
        audit = audit_response.get_json()

        assert audit_response.status_code == 200
        assert audit["ok"] is True
        assert any(event["action_kind"] == "create_today_task_candidate" for event in audit["events"])

        task_records = read_jsonl_file(data_dir / "plan_tasks.jsonl")
        assert any(task.get("id") == created_task["id"] for task in task_records)
        assert not any(task.get("id") == "task_app_smoke_seed_today" for task in task_records)
    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)
