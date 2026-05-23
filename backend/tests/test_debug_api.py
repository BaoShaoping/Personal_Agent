import shutil
from pathlib import Path

from personal_agent import api as debug_api


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def request(method, path, **kwargs):
    with debug_api.app.test_client() as client:
        return client.open(path, method=method, **kwargs)


def test_debug_page_returns_200():
    response = request("GET", "/debug")

    assert response.status_code == 200
    assert "Personal Context Agent - Module Debug Console" in response.text
    assert '<section class="panel" id="system-panel">' in response.text
    assert "长期计划 / 系统面板" in response.text


def test_app_page_returns_200_and_references_assets():
    response = request("GET", "/app")

    assert response.status_code == 200
    assert "Personal Agent" in response.text
    assert "本地成长系统" in response.text
    assert "成长闭环" in response.text
    assert 'href="/static/app.css"' in response.text
    assert 'src="/static/app.js"' in response.text


def test_app_page_does_not_replace_debug_console():
    app_response = request("GET", "/app")
    debug_response = request("GET", "/debug")

    assert app_response.status_code == 200
    assert debug_response.status_code == 200
    assert '<main class="app-shell">' in app_response.text
    assert "Personal Context Agent - Module Debug Console" in debug_response.text


def test_app_static_script_contains_generate_today_task_entry():
    response = request("GET", "/static/app.js")

    assert response.status_code == 200
    assert "生成今日最小任务" in response.text
    assert "GENERATE_TODAY_TASK_PROMPT" in response.text


def test_context_build_returns_markdown_and_stats():
    response = request(
        "POST",
        "/api/context/build",
        json={
            "user_message": "我们下一步怎么开发 Personal Context Agent？",
            "max_chars": 6000,
            "max_memories": 8,
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["context_markdown"]
    assert "stats" in data
    assert "context_chars" in data["stats"]


def test_memory_summary_handles_missing_data_files(monkeypatch):
    partial_data = ROOT / "backend" / "tests" / "_tmp_debug_missing_data"
    if partial_data.exists():
        shutil.rmtree(partial_data)
    shutil.copytree(DATA_DIR, partial_data)
    try:
        (partial_data / "memories.jsonl").unlink()
        (partial_data / "constraints.yaml").unlink()
        monkeypatch.setattr(debug_api, "DATA_DIR", partial_data)

        response = request("GET", "/api/memory/summary")

        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert "memories.jsonl" in data["missing_files"]
        assert "constraints.yaml" in data["missing_files"]
        assert isinstance(data["load_errors"], list)
    finally:
        if partial_data.exists():
            shutil.rmtree(partial_data)


def test_settings_missing_returns_found_false(monkeypatch):
    empty_data = ROOT / "backend" / "tests" / "_tmp_debug_empty_data"
    if empty_data.exists():
        shutil.rmtree(empty_data)
    empty_data.mkdir()
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", empty_data)

        response = request("GET", "/api/settings")

        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["found"] is False
        assert data["settings"] == {}
    finally:
        if empty_data.exists():
            shutil.rmtree(empty_data)


def test_modules_returns_placeholder_modules():
    response = request("GET", "/api/modules")

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    module_names = {module["name"] for module in data["modules"]}
    assert "Model Gateway" in module_names
    assert "Long-term Plan / System Panel" in module_names
    assert any(module["status"] == "not implemented" for module in data["modules"])
    assert any(
        module["name"] == "Long-term Plan / System Panel" and module["status"] == "implemented"
        for module in data["modules"]
    )


def test_plans_summary_returns_active_plans():
    response = request("GET", "/api/plans/summary")

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["active_plans"]


def test_plan_task_status_updates_task(monkeypatch):
    partial_data = ROOT / "backend" / "tests" / "_tmp_debug_plan_status"
    if partial_data.exists():
        shutil.rmtree(partial_data)
    shutil.copytree(DATA_DIR, partial_data)
    try:
        monkeypatch.setattr(debug_api, "DATA_DIR", partial_data)

        response = request(
            "POST",
            "/api/plans/tasks/status",
            json={"task_id": "task_20260502_001", "status": "done", "note": "tested from API"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["task"]["status"] == "done"
        assert data["progress_entry"]["task_id"] == "task_20260502_001"
    finally:
        if partial_data.exists():
            shutil.rmtree(partial_data)
