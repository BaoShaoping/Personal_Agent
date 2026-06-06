import json
import shutil
from pathlib import Path

from personal_agent import model_gateway as mg
from personal_agent.model_gateway import (
    _chat_completions_url,
    boost_max_tokens,
    build_model_messages,
    effective_mode,
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
    # Accept either committed mock or a local live flip so manual live testing
    # does not trip the suite.
    assert config["mode"] in {"mock", "live"}
    assert config["temperature"] == 0.4
    assert config["max_tokens"] == 1200


def test_live_mode_without_key_falls_back_to_mock(monkeypatch):
    monkeypatch.delenv("PERSONAL_AGENT_API_KEY", raising=False)
    config = {
        "provider": "openai_compatible",
        "mode": "live",
        "base_url": "http://localhost:9999/v1",
        "model_name": "test-model",
        "api_key_env": "PERSONAL_AGENT_API_KEY",
    }

    # validate still reports the missing key (useful for /api/model/config diagnostics)
    assert any("PERSONAL_AGENT_API_KEY" in error for error in validate_model_config(config))
    # but the app auto-falls back to mock so the panel still works offline
    assert effective_mode(config) == "mock"
    response = generate_response([{"role": "user", "content": "hello"}], config)
    assert response["ok"] is True
    assert response["answer"].startswith("[mock answer]")


def test_effective_mode_live_only_with_key(monkeypatch):
    monkeypatch.setenv("PERSONAL_AGENT_API_KEY", "k")
    live_cfg = {"mode": "live", "api_key_env": "PERSONAL_AGENT_API_KEY", "model_name": "glm-4.5-air"}
    assert effective_mode(live_cfg) == "live"
    assert effective_mode({"mode": "mock"}) == "mock"


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


def test_chat_completions_url_handles_version_segments():
    base = "https://open.bigmodel.cn/api/paas/v4"
    assert _chat_completions_url(base) == base + "/chat/completions"
    assert _chat_completions_url("http://host/v1") == "http://host/v1/chat/completions"
    assert _chat_completions_url("http://host") == "http://host/v1/chat/completions"
    assert _chat_completions_url(base + "/chat/completions") == base + "/chat/completions"


def test_live_mode_parses_openai_response(monkeypatch):
    monkeypatch.setenv("PERSONAL_AGENT_API_KEY", "test-key")

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(req, timeout=0):
        # Confirms the GLM /v4 endpoint is built correctly end-to-end.
        assert req.full_url == "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        return FakeResponse({"choices": [{"message": {"content": "叮！系统已就绪"}}], "usage": {"total_tokens": 42}})

    monkeypatch.setattr(mg.request, "urlopen", fake_urlopen)
    config = {
        "provider": "openai_compatible",
        "mode": "live",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model_name": "glm-4.5-air",
        "api_key_env": "PERSONAL_AGENT_API_KEY",
    }

    response = generate_response([{"role": "user", "content": "你好"}], config)
    assert response["ok"] is True
    assert "系统已就绪" in response["answer"]
    assert response["usage"]["total_tokens"] == 42


def test_boost_max_tokens_raises_floor_only():
    assert boost_max_tokens({"max_tokens": 500})["max_tokens"] == 2048
    assert boost_max_tokens({"max_tokens": 4000})["max_tokens"] == 4000
    assert boost_max_tokens({})["max_tokens"] == 2048


def test_live_payload_includes_extra_body(monkeypatch):
    monkeypatch.setenv("PERSONAL_AGENT_API_KEY", "test-key")
    captured = {}

    class FakeResponse:
        def read(self):
            return b'{"choices": [{"message": {"content": "ok"}}]}'

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(req, timeout=0):
        captured["body"] = req.data
        return FakeResponse()

    monkeypatch.setattr(mg.request, "urlopen", fake_urlopen)
    config = {
        "provider": "openai_compatible",
        "mode": "live",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model_name": "glm-4.5-air",
        "api_key_env": "PERSONAL_AGENT_API_KEY",
        "extra_body": {"thinking": {"type": "disabled"}},
    }
    generate_response([{"role": "user", "content": "x"}], config)
    body = json.loads(captured["body"].decode("utf-8"))
    assert body["thinking"] == {"type": "disabled"}
