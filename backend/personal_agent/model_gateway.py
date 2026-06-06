"""OpenAI-compatible model gateway with a deterministic mock mode."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib import error, request

from .memory_store import read_yaml_file


DEFAULT_MODEL_CONFIG = {
    "provider": "openai_compatible",
    "base_url": "",
    "model_name": "",
    "api_key_env": "PERSONAL_AGENT_API_KEY",
    "temperature": 0.4,
    "max_tokens": 1200,
    "mode": "mock",
    # Reasoning models (e.g. GLM-4.6) can take well over a minute to respond.
    "timeout": 120,
}


ASK_SYSTEM_PROMPT = """You are Personal Context Agent.

Answer primarily based on the Personal Context Pack provided by the system.
If the context is insufficient, say what is uncertain.
Do not pretend you have executed actions, changed files, updated memories, or contacted external services.
If there is a natural next step, suggest it in plain text only. Do not create action cards in this phase.
Keep the answer practical, concise, and context-aware."""


def load_model_config(data_dir: str | Path = "data") -> dict[str, Any]:
    root = Path(data_dir)
    settings_path = root / "settings.yaml"
    config = dict(DEFAULT_MODEL_CONFIG)

    if settings_path.exists():
        settings = read_yaml_file(settings_path)
        if isinstance(settings, dict) and isinstance(settings.get("model"), dict):
            config.update(settings["model"])

    return _normalize_model_config(config)


def validate_model_config(model_config: dict[str, Any]) -> list[str]:
    config = _normalize_model_config(model_config)
    errors: list[str] = []
    mode = config.get("mode")

    if config.get("provider") != "openai_compatible":
        errors.append("Only provider=openai_compatible is supported in this MVP.")

    if mode not in {"mock", "live"}:
        errors.append("model.mode must be mock or live.")

    if mode == "live":
        if not config.get("base_url"):
            errors.append("model.base_url is required when model.mode=live.")
        if not config.get("model_name"):
            errors.append("model.model_name is required when model.mode=live.")
        if not os.getenv(str(config.get("api_key_env") or "")):
            errors.append(f"API key environment variable is missing: {config.get('api_key_env')}")

    return errors


def build_model_messages(user_message: str, context_markdown: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": ASK_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": "Personal Context Pack:\n\n" + (context_markdown or "(empty context pack)"),
        },
        {"role": "user", "content": user_message},
    ]


def generate_response(messages: list[dict[str, str]], model_config: dict[str, Any]) -> dict[str, Any]:
    config = _normalize_model_config(model_config)

    # Auto-fallback: when live is requested but no API key is available, run mock
    # so the panel still works offline. (Mode mock also lands here.)
    if effective_mode(config) == "mock":
        return _mock_response(messages, dict(config, mode="mock"))

    errors = validate_model_config(config)
    if errors:
        return {
            "ok": False,
            "answer": "",
            "model_info": model_info(config),
            "usage": None,
            "error": {"message": "; ".join(errors), "details": errors},
        }

    return _live_openai_compatible_response(messages, config)


def generate_structured_output(
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    model_config: dict[str, Any],
) -> dict[str, Any]:
    response = generate_response(messages, model_config)
    response["schema"] = schema
    response["structured_output"] = None
    return response


def model_info(model_config: dict[str, Any]) -> dict[str, Any]:
    config = _normalize_model_config(model_config)
    return {
        "provider": config["provider"],
        "mode": config["mode"],
        "base_url": config["base_url"],
        "model_name": config["model_name"],
        "api_key_env": config["api_key_env"],
        "api_key_present": bool(os.getenv(str(config["api_key_env"]))),
        "temperature": config["temperature"],
        "max_tokens": config["max_tokens"],
    }


def effective_mode(model_config: dict[str, Any]) -> str:
    """The mode actually used: live only when requested AND a key is available.

    Live-without-key auto-falls back to ``mock`` so the panel still works (the
    System is the GLM brain when a key is set; without one it degrades to mock).
    """

    config = _normalize_model_config(model_config)
    if config["mode"] == "live" and not os.getenv(str(config["api_key_env"]) or ""):
        return "mock"
    return config["mode"]


def boost_max_tokens(model_config: dict[str, Any], minimum: int = 2048) -> dict[str, Any]:
    """Return a config copy with a generous token budget.

    GLM-4.5 is a reasoning model: its reasoning shares the completion budget, so a
    small ``max_tokens`` can starve the final content. The System's GLM activities
    (quest, narration) use this so reasoning + output never gets truncated.
    """

    config = dict(model_config or {})
    try:
        current = int(config.get("max_tokens") or 0)
    except (TypeError, ValueError):
        current = 0
    config["max_tokens"] = max(current, minimum)
    return config


def _mock_response(messages: list[dict[str, str]], config: dict[str, Any]) -> dict[str, Any]:
    user_message = _last_message_content(messages, "user")
    context = "\n\n".join(message.get("content", "") for message in messages if message.get("role") == "system")
    plan_hint = "Active Long-term Plans" in context
    memory_hint = "Relevant Memories" in context or "Relevant Decisions" in context

    hints = []
    if plan_hint:
        hints.append("长期计划")
    if memory_hint:
        hints.append("个人记忆")
    hint_text = "、".join(hints) if hints else "当前上下文"

    answer = (
        f"[mock answer] 我会优先依据{hint_text}回答：{user_message}\n\n"
        "建议先查看 context_markdown 中的当前目标、长期计划和今日任务，再决定下一步。"
    )
    return {
        "ok": True,
        "answer": answer,
        "model_info": model_info(config),
        "usage": {
            "prompt_chars": sum(len(message.get("content", "")) for message in messages),
            "completion_chars": len(answer),
            "total_chars": sum(len(message.get("content", "")) for message in messages) + len(answer),
            "mock": True,
        },
        "error": None,
    }


def _live_openai_compatible_response(messages: list[dict[str, str]], config: dict[str, Any]) -> dict[str, Any]:
    url = _chat_completions_url(str(config["base_url"]))
    api_key = os.getenv(str(config["api_key_env"]))
    payload = {
        "model": config["model_name"],
        "messages": messages,
        "temperature": config["temperature"],
        "max_tokens": config["max_tokens"],
    }
    extra_body = config.get("extra_body")
    if isinstance(extra_body, dict):
        payload.update(extra_body)
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {api_key}",
    }

    try:
        req = request.Request(url, data=body, headers=headers, method="POST")
        with request.urlopen(req, timeout=config.get("timeout", 120)) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        return _live_error(config, f"Model provider returned HTTP {exc.code}: {message}")
    except Exception as exc:  # pragma: no cover - network failure diagnostics
        return _live_error(config, str(exc))

    answer = _extract_openai_answer(raw)
    return {
        "ok": True,
        "answer": answer,
        "model_info": model_info(config),
        "usage": raw.get("usage"),
        "error": None,
        "raw_response": raw,
    }


def _live_error(config: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "answer": "",
        "model_info": model_info(config),
        "usage": None,
        "error": {"message": message},
    }


def _extract_openai_answer(raw: dict[str, Any]) -> str:
    choices = raw.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(part.get("text") or part) for part in content)
    return ""


def _chat_completions_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    if clean.endswith("/chat/completions"):
        return clean
    # If the base already ends with an API version segment (/v1, /v4 for GLM, ...),
    # append only the path; otherwise default to /v1/chat/completions.
    if re.fullmatch(r"v\d+", clean.rsplit("/", 1)[-1]):
        return clean + "/chat/completions"
    return clean + "/v1/chat/completions"


def _normalize_model_config(model_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(DEFAULT_MODEL_CONFIG)
    config.update(model_config or {})
    config["provider"] = str(config.get("provider") or "openai_compatible")
    config["base_url"] = str(config.get("base_url") or "").strip()
    config["model_name"] = str(config.get("model_name") or "").strip()
    config["api_key_env"] = str(config.get("api_key_env") or "PERSONAL_AGENT_API_KEY").strip()
    config["mode"] = str(config.get("mode") or "mock").strip().lower()
    try:
        config["temperature"] = float(config.get("temperature"))
    except (TypeError, ValueError):
        config["temperature"] = DEFAULT_MODEL_CONFIG["temperature"]
    try:
        config["max_tokens"] = int(config.get("max_tokens"))
    except (TypeError, ValueError):
        config["max_tokens"] = DEFAULT_MODEL_CONFIG["max_tokens"]
    try:
        config["timeout"] = int(config.get("timeout"))
    except (TypeError, ValueError):
        config["timeout"] = DEFAULT_MODEL_CONFIG["timeout"]
    return config


def _last_message_content(messages: list[dict[str, str]], role: str) -> str:
    for message in reversed(messages):
        if message.get("role") == role:
            return message.get("content", "")
    return ""
