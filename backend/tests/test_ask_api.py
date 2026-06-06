from personal_agent import api as debug_api


def request(method, path, **kwargs):
    with debug_api.app.test_client() as client:
        return client.open(path, method=method, **kwargs)


def test_model_config_api_returns_200_and_redacts_api_key(monkeypatch):
    monkeypatch.setenv("PERSONAL_AGENT_API_KEY", "secret-test-key")

    response = request("GET", "/api/model/config")

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["model_config"]["api_key_env"] == "PERSONAL_AGENT_API_KEY"
    assert data["model_config"]["api_key_present"] is True
    assert "secret-test-key" not in response.get_data(as_text=True)


def test_model_test_api_returns_200():
    # Force mock so the test stays offline/deterministic regardless of the
    # committed settings.yaml mode.
    response = request("POST", "/api/model/test", json={"user_message": "测试模型网关", "model_override": {"mode": "mock"}})

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["answer"].startswith("[mock answer]")


def test_ask_api_returns_answer_and_context_pack():
    response = request(
        "POST",
        "/api/ask",
        json={"user_message": "我今天应该做什么？", "max_chars": 6000, "max_memories": 8, "model_override": {"mode": "mock"}},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["answer"]
    assert data["context_pack"]["context_markdown"]
    assert data["model_info"]["mode"] == "mock"


def test_debug_page_model_gateway_tab_is_real():
    response = request("GET", "/debug")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<section class="panel" id="model-gateway">' in html
    assert "Ask / 模型网关" in html
