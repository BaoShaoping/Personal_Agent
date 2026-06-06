import json

from personal_agent import system_quest
from personal_agent.plan_store import load_plan_data
from personal_agent.system_quest import accept_quest, generate_quest


def _write_plans(tmp_path):
    (tmp_path / "plans.yaml").write_text(
        "plans:\n"
        "  - id: plan_eng\n"
        "    title: 英语能力\n"
        "    kind: main\n"
        "    status: active\n"
        "    goal: 读懂 AI 文档\n"
        "    progress_percent: 20\n",
        encoding="utf-8",
    )


def _write_live_settings(tmp_path):
    (tmp_path / "settings.yaml").write_text(
        "model:\n"
        "  provider: openai_compatible\n"
        '  base_url: "https://open.bigmodel.cn/api/paas/v4"\n'
        "  model_name: glm-4.5-air\n"
        "  api_key_env: PERSONAL_AGENT_API_KEY\n"
        "  mode: live\n",
        encoding="utf-8",
    )


def test_generate_quest_no_plans(tmp_path):
    assert generate_quest(str(tmp_path))["ok"] is False


def test_generate_quest_mock_falls_back_to_rule(tmp_path):
    _write_plans(tmp_path)  # no settings.yaml -> mode defaults to mock
    result = generate_quest(str(tmp_path))
    assert result["ok"] is True
    assert result["source"] == "mock"
    quest = result["quest"]
    assert quest["plan_id"] == "plan_eng"
    assert quest["title"]
    assert set(quest["rewards"]).issuperset({"exp", "magic_points", "attribute", "attribute_exp"})


def test_generate_quest_llm_parses_structured(tmp_path, monkeypatch):
    _write_plans(tmp_path)
    _write_live_settings(tmp_path)
    answer = json.dumps(
        {"title": "背 15 个单词", "attribute": "intellect", "exp": 18, "magic_points": 7, "attribute_exp": 22, "system_voice": "叮！宿主，开始吧"},
        ensure_ascii=False,
    )
    monkeypatch.setattr(system_quest, "generate_response", lambda messages, config: {"ok": True, "answer": "好的：\n" + answer})

    result = generate_quest(str(tmp_path))
    assert result["source"] == "llm"
    quest = result["quest"]
    assert quest["title"] == "背 15 个单词"
    assert quest["rewards"]["attribute"] == "intellect"
    assert quest["rewards"]["exp"] == 18
    assert quest["system_voice"]


def test_generate_quest_llm_invalid_falls_back(tmp_path, monkeypatch):
    _write_plans(tmp_path)
    _write_live_settings(tmp_path)
    monkeypatch.setattr(system_quest, "generate_response", lambda messages, config: {"ok": True, "answer": "抱歉我无法生成。"})

    result = generate_quest(str(tmp_path))
    assert result["source"] == "mock"


def test_generate_quest_llm_clamps_out_of_range(tmp_path, monkeypatch):
    _write_plans(tmp_path)
    _write_live_settings(tmp_path)
    answer = json.dumps({"title": "x", "attribute": "intellect", "exp": 999, "magic_points": 0, "attribute_exp": 5})
    monkeypatch.setattr(system_quest, "generate_response", lambda messages, config: {"ok": True, "answer": answer})

    rewards = generate_quest(str(tmp_path))["quest"]["rewards"]
    assert rewards["exp"] == 30  # clamped high
    assert rewards["magic_points"] == 3  # clamped low
    assert rewards["attribute_exp"] == 10  # clamped low


def test_accept_quest_creates_task(tmp_path):
    _write_plans(tmp_path)
    quest = {
        "plan_id": "plan_eng",
        "title": "背单词",
        "rewards": {"exp": 12, "magic_points": 6, "attribute": "intellect", "attribute_exp": 18},
    }
    result = accept_quest(quest, str(tmp_path))
    assert result["ok"] is True
    assert result["task"]["plan_id"] == "plan_eng"
    assert result["task"]["rewards"]["exp"] == 12

    tasks = load_plan_data(tmp_path).tasks
    assert any(t["id"] == result["task"]["id"] and t.get("rewards", {}).get("exp") == 12 for t in tasks)


def test_accept_quest_requires_fields(tmp_path):
    _write_plans(tmp_path)
    assert accept_quest({"title": "x"}, str(tmp_path))["ok"] is False
