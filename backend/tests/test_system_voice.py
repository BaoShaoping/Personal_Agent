from personal_agent import system_voice
from personal_agent.system_voice import narrate_completion, template_ding


def _write_live_settings(tmp_path):
    (tmp_path / "settings.yaml").write_text(
        "model:\n  mode: live\n  base_url: \"https://open.bigmodel.cn/api/paas/v4\"\n  model_name: glm-4.5-air\n  api_key_env: PERSONAL_AGENT_API_KEY\n",
        encoding="utf-8",
    )


def test_template_ding_format():
    text = template_ding("背单词", {"exp": 15, "magic_points": 5}, False, 3, "智识")
    assert text.startswith("叮！")
    assert "背单词" in text and "+15" in text and "智识" in text


def test_template_ding_level_up():
    text = template_ding("慢跑", {"exp": 30, "magic_points": 5}, True, 2, "体魄")
    assert "升级" in text and "Lv.2" in text


def test_narrate_mock_uses_template(tmp_path):
    # No settings.yaml -> mock mode -> deterministic template.
    text = narrate_completion("背单词", {"exp": 10, "magic_points": 5}, False, 1, "智识", str(tmp_path))
    assert "背单词" in text


def test_narrate_live_uses_llm(tmp_path, monkeypatch):
    _write_live_settings(tmp_path)
    monkeypatch.setattr(system_voice, "generate_response", lambda messages, config: {"ok": True, "answer": "叮！宿主真棒，继续保持！"})
    text = narrate_completion("背单词", {"exp": 10, "magic_points": 5}, False, 1, "智识", str(tmp_path))
    assert text == "叮！宿主真棒，继续保持！"


def test_narrate_live_falls_back_on_failure(tmp_path, monkeypatch):
    _write_live_settings(tmp_path)
    monkeypatch.setattr(system_voice, "generate_response", lambda messages, config: {"ok": False})
    text = narrate_completion("背单词", {"exp": 10, "magic_points": 5}, False, 1, "智识", str(tmp_path))
    assert "背单词" in text  # template fallback


def test_narrate_live_takes_first_line_only(tmp_path, monkeypatch):
    _write_live_settings(tmp_path)
    monkeypatch.setattr(system_voice, "generate_response", lambda messages, config: {"ok": True, "answer": "叮！干得漂亮\n（这是多余的解释）"})
    text = narrate_completion("背单词", {"exp": 10, "magic_points": 5}, False, 1, "智识", str(tmp_path))
    assert text == "叮！干得漂亮"
