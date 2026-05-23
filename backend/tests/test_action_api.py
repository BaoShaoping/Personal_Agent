import shutil
from pathlib import Path

from personal_agent import api as debug_api
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


def test_actions_confirm_executes_known_confirmed_action(monkeypatch):
    data_dir = _copy_data("_tmp_action_api_confirm")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)
        before = len(read_jsonl_file(data_dir / "memories.jsonl"))

        response = request(
            "POST",
            "/api/actions/confirm",
            json={
                "action": {
                    "id": "act_api_mem_001",
                    "kind": "save_memory_candidate",
                    "target": "memories.jsonl",
                    "payload": {"content": "API confirmed memory.", "source": "test"},
                },
                "permission_mode": "ask_first",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["execution"]["status"] == "executed"
        assert data["permission_decision"]["risk_level"] == "medium"
        assert len(read_jsonl_file(data_dir / "memories.jsonl")) == before + 1
    finally:
        shutil.rmtree(data_dir)


def test_actions_cancel_cancels_without_execution(monkeypatch):
    data_dir = _copy_data("_tmp_action_api_cancel")
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", data_dir)
        before = len(read_jsonl_file(data_dir / "memories.jsonl"))

        response = request(
            "POST",
            "/api/actions/cancel",
            json={
                "action": {
                    "id": "act_api_cancel_001",
                    "kind": "save_memory_candidate",
                    "target": "memories.jsonl",
                    "payload": {"content": "Should not be saved."},
                },
                "reason": "user canceled",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["execution"]["status"] == "canceled"
        assert len(read_jsonl_file(data_dir / "memories.jsonl")) == before
    finally:
        shutil.rmtree(data_dir)


def test_debug_page_has_real_action_executor_tab():
    response = request("GET", "/debug")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<section class="panel" id="action-executor">' in html
    assert "Action Executor" in html
    assert "Confirm Execute" in html
