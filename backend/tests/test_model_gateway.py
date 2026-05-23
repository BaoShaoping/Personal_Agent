import shutil
from pathlib import Path

from personal_agent.model_gateway import (
    build_model_messages,
    generate_response,
    load_model_config,
    validate_model_config,
)


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def test_load_model_config_reads_settings_yaml():
    config = load_model_config(DATA_DIR)

    assert config["provider"] == "openai_compatible"
    assert config["api_key_env"] == "PERSONAL_AGENT_API_KEY"
    assert config["mode"] == "mock"
    assert config["temperature"] == 0.4
    assert config["max_tokens"] == 1200


def test_live_mode_missing_api_key_returns_clear_error(monkeypatch):
    monkeypatch.delenv("PERSONAL_AGENT_API_KEY", raising=False)
    config = {
        "provider": "openai_compatible",
        "mode": "live",
        "base_url": "http://localhost:9999/v1",
        "model_name": "test-model",
        "api_key_env": "PERSONAL_AGENT_API_KEY",
    }

    errors = validate_model_config(config)
    response = generate_response([{"role": "user", "content": "hello"}], config)

    assert any("PERSONAL_AGENT_API_KEY" in error for error in errors)
    assert response["ok"] is False
    assert "PERSONAL_AGENT_API_KEY" in response["error"]["message"]


def test_mock_mode_does_not_need_network_and_is_predictable():
    response = generate_response(
        [{"role": "system", "content": "Active Long-term Plans"}, {"role": "user", "content": "我今天做什么？"}],
        {"provider": "openai_compatible", "mode": "mock"},
    )

    assert response["ok"] is True
    assert response["answer"].startswith("[mock answer]")
    assert "我今天做什么？" in response["answer"]
    assert response["usage"]["mock"] is True


def test_build_model_messages_contains_context_and_user_message():
    messages = build_model_messages("hello", "# Personal Context Pack")

    combined = "\n".join(message["content"] for message in messages)
    assert "Personal Context Agent" in combined
    assert "# Personal Context Pack" in combined
    assert "hello" in combined


def test_load_model_config_defaults_when_settings_missing():
    empty_data = ROOT / "backend" / "tests" / "_tmp_model_empty_data"
    if empty_data.exists():
        shutil.rmtree(empty_data)
    empty_data.mkdir()
    try:
        config = load_model_config(empty_data)

        assert config["mode"] == "mock"
        assert config["api_key_env"] == "PERSONAL_AGENT_API_KEY"
    finally:
        if empty_data.exists():
            shutil.rmtree(empty_data)
