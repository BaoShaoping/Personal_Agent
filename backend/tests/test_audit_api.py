import shutil
from pathlib import Path

from personal_agent import api as debug_api


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


def test_get_audit_events_returns_200(monkeypatch):
    data_dir = _copy_data("_tmp_audit_api_events")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)

        response = request("GET", "/api/audit/events")

        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["events"] == []
        assert data["count"] == 0
    finally:
        shutil.rmtree(data_dir)


def test_post_audit_events_appends_and_redacts_secrets(monkeypatch):
    data_dir = _copy_data("_tmp_audit_api_append")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)

        response = request(
            "POST",
            "/api/audit/events",
            json={
                "event_type": "permission_evaluated",
                "module": "permission_engine",
                "action_kind": "update_plan_task_status",
                "summary": "Manual test event.",
                "payload": {
                    "api_key": "do-not-store",
                    "nested": {"token": "do-not-store"},
                },
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["event"]["payload"]["api_key"] == "[redacted]"
        assert data["event"]["payload"]["nested"]["token"] == "[redacted]"
        assert (data_dir / "audit_log.jsonl").exists()
    finally:
        shutil.rmtree(data_dir)


def test_get_audit_summary_returns_counts(monkeypatch):
    data_dir = _copy_data("_tmp_audit_api_summary")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)
        request(
            "POST",
            "/api/audit/events",
            json={"event_type": "permission_evaluated", "status": "success", "summary": "one"},
        )
        request(
            "POST",
            "/api/audit/events",
            json={"event_type": "action_canceled", "status": "canceled", "summary": "two"},
        )

        response = request("GET", "/api/audit/summary")

        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["counts_by_type"]["permission_evaluated"] == 1
        assert data["counts_by_status"]["success"] == 1
        assert data["counts_by_status"]["canceled"] == 1
    finally:
        shutil.rmtree(data_dir)


def test_permission_evaluate_api_logs_audit_event(monkeypatch):
    data_dir = _copy_data("_tmp_audit_api_permission")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)

        response = request(
            "POST",
            "/api/permission/evaluate",
            json={
                "permission_mode": "ask_first",
                "action": {
                    "id": "act_test_001",
                    "kind": "save_memory_candidate",
                    "target": "memories.jsonl",
                },
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["audit_event"]["event_type"] == "permission_evaluated"
        assert data["audit_event"]["action_id"] == "act_test_001"
        assert data["audit_event"]["action_kind"] == "save_memory_candidate"
        assert data["audit_event"]["summary"] == "权限评估完成：save_memory_candidate。"
    finally:
        shutil.rmtree(data_dir)


def test_suggest_with_permission_api_logs_audit_event(monkeypatch):
    data_dir = _copy_data("_tmp_audit_api_suggest_permission")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)

        response = request(
            "POST",
            "/api/suggest/with-permission",
            json={
                "user_message": "please remember: I prefer direct answers.",
                "include_ask": False,
                "permission_mode": "trusted",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["permission_audit_event"]["event_type"] == "permission_evaluated"
        assert data["permission_audit_event"]["action_kind"] == "save_memory_candidate"
        assert data["permission_audit_event"]["summary"] == "权限评估完成：save_memory_candidate。"
    finally:
        shutil.rmtree(data_dir)


def test_debug_page_includes_real_audit_log_tab():
    response = request("GET", "/debug")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<section class="panel" id="audit-log">' in html
    assert "Audit Log" in html
