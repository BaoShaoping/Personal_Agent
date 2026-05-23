from personal_agent import api as debug_api


def request(method, path, **kwargs):
    with debug_api.app.test_client() as client:
        return client.open(path, method=method, **kwargs)


def test_suggest_api_returns_200():
    response = request(
        "POST",
        "/api/suggest",
        json={"user_message": "请帮我记住：我喜欢直接回答。", "include_ask": False},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["suggestion"]["type"] == "suggested_action"
    assert data["suggestion"]["title"] == "保存记忆候选"
    assert data["suggestion"]["action"]["kind"] == "save_memory_candidate"
    assert data["ask_result"] is None


def test_suggest_api_can_include_ask_result():
    response = request(
        "POST",
        "/api/suggest",
        json={"user_message": "这个项目现在下一步是什么？", "include_ask": True},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["context_pack"]["context_markdown"]
    assert data["ask_result"] is not None


def test_debug_page_suggestion_engine_tab_is_real():
    response = request("GET", "/debug")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<section class="panel" id="suggestion-engine">' in html
    assert "Suggestion Engine" in html
