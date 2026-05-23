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


def test_permission_evaluate_api_returns_200(monkeypatch):
    data_dir = _copy_data("_tmp_permission_api_evaluate")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)

        response = request(
            "POST",
            "/api/permission/evaluate",
            json={
                "permission_mode": "ask_first",
                "action": {"kind": "save_memory_candidate", "risk_level": "low"},
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["decision"]["risk_level"] == "medium"
        assert data["decision"]["requires_confirmation"] is True
        assert data["audit_event"]["event_type"] == "permission_evaluated"
        assert data["audit_event"]["summary"] == "权限评估完成：save_memory_candidate。"
    finally:
        shutil.rmtree(data_dir)


def test_suggest_with_permission_returns_suggestion_and_decision(monkeypatch):
    data_dir = _copy_data("_tmp_permission_api_suggest")
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
        assert data["ok"] is True
        assert data["suggestion"]["type"] == "suggested_action"
        assert data["permission_decision"]["risk_level"] == "medium"
        assert data["permission_decision"]["requires_confirmation"] is False
        assert data["permission_audit_event"]["event_type"] == "permission_evaluated"
        assert data["permission_audit_event"]["summary"] == "权限评估完成：save_memory_candidate。"
    finally:
        shutil.rmtree(data_dir)


def test_debug_page_permission_engine_tab_is_real():
    response = request("GET", "/debug")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<section class="panel" id="permission-engine">' in html
    assert "Permission Engine" in html
