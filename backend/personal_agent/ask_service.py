"""Ask flow: build context, call the model gateway, return a traceable answer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .context_builder import build_context_pack
from .model_gateway import build_model_messages, generate_response, load_model_config, model_info


def ask(
    user_message: str,
    data_dir: str | Path = "data",
    max_chars: int = 6000,
    max_memories: int = 8,
    model_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    user_message = str(user_message or "").strip()
    if not user_message:
        return {
            "ok": False,
            "answer": "",
            "model_info": {},
            "context_pack": None,
            "messages_preview": [],
            "usage": None,
            "error": {"message": "user_message is required"},
        }

    context_pack = build_context_pack(
        user_message=user_message,
        data_dir=str(data_dir),
        max_chars=max_chars,
        max_memories=max_memories,
    )
    model_config = load_model_config(data_dir)
    if model_override:
        model_config.update(model_override)

    messages = build_model_messages(user_message, context_pack.context_markdown)
    model_response = generate_response(messages, model_config)

    return {
        "ok": bool(model_response.get("ok")),
        "answer": model_response.get("answer", ""),
        "model_info": model_response.get("model_info") or model_info(model_config),
        "context_pack": context_pack.to_dict(),
        "messages_preview": _preview_messages(messages),
        "usage": model_response.get("usage"),
        "error": model_response.get("error"),
    }


def test_model_gateway(
    user_message: str,
    data_dir: str | Path = "data",
    model_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model_config = load_model_config(data_dir)
    if model_override:
        model_config.update(model_override)
    messages = build_model_messages(user_message, "Mock context for model gateway test.")
    response = generate_response(messages, model_config)
    return {
        "ok": bool(response.get("ok")),
        "answer": response.get("answer", ""),
        "model_info": response.get("model_info") or model_info(model_config),
        "messages_preview": _preview_messages(messages),
        "usage": response.get("usage"),
        "error": response.get("error"),
    }


def _preview_messages(messages: list[dict[str, str]], max_chars: int = 1200) -> list[dict[str, str]]:
    preview = []
    for message in messages:
        content = message.get("content", "")
        if len(content) > max_chars:
            content = content[:max_chars].rstrip() + "\n[preview truncated]"
        preview.append({"role": message.get("role", ""), "content": content})
    return preview
