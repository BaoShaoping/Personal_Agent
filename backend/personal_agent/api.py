"""Development-only module debug API for Personal Context Agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request

from .action_executor import cancel_action, execute_confirmed_action
from .ask_service import ask, test_model_gateway
from .audit_log import append_audit_event, build_audit_summary, read_audit_events
from .context_builder import build_context_pack
from .memory_store import JSONL_FILES, YAML_FILES, load_memory_data, read_yaml_file
from .model_gateway import load_model_config, model_info
from .permission_engine import evaluate_action, load_permission_mode
from .plan_store import append_plan_progress, build_plan_context, plan_summary, update_task_status
from .suggestion_engine import suggest_next_action
from .system_engine import build_system_summary, complete_and_settle_task
from .system_quest import accept_quest, generate_quest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
STATIC_DIR = BACKEND_DIR / "static"

DEBUG_TITLE = "Personal Context Agent - Module Debug Console"
APP_TITLE = "Personal Agent - 本地系统面板"
SYSTEM_TITLE = "系统 · Personal Agent"

PLACEHOLDER_MODULES = [
    {
        "id": "action-executor",
        "name": "Action Executor",
        "display_name_zh": "动作执行器",
        "status": "not implemented",
        "status_label_zh": "未实现",
        "planned_interface": "execute_confirmed_action(action) -> execution_result with audit log entry",
        "planned_interface_zh": "只执行已经确认的动作，返回执行结果，并写入审计日志。",
    },
    {
        "id": "openclaw-adapter",
        "name": "OpenClaw Adapter",
        "display_name_zh": "OpenClaw 适配器",
        "status": "not implemented",
        "status_label_zh": "未实现",
        "planned_interface": "list_tools(); execute_tool(tool_name, input); check_status(task_id)",
        "planned_interface_zh": "以后用于列出 OpenClaw 工具、执行工具调用、查询任务状态；当前不做深度集成。",
    },
]


def build_context_response(payload: dict[str, Any] | None, data_dir: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    user_message = str(payload.get("user_message") or "").strip()
    if not user_message:
        return 400, {"ok": False, "error": {"message": "user_message is required"}}

    try:
        max_chars = int(payload.get("max_chars", 6000))
        max_memories = int(payload.get("max_memories", 8))
    except (TypeError, ValueError):
        return 400, {"ok": False, "error": {"message": "max_chars and max_memories must be numbers"}}

    max_chars = max(200, min(max_chars, 50000))
    max_memories = max(0, min(max_memories, 100))

    try:
        pack = build_context_pack(
            user_message=user_message,
            data_dir=str(data_dir or DATA_DIR),
            max_chars=max_chars,
            max_memories=max_memories,
        )
    except Exception as exc:  # pragma: no cover - last-resort API diagnostics
        return 500, {"ok": False, "error": {"message": str(exc), "type": exc.__class__.__name__}}

    return 200, {"ok": True, **pack.to_dict()}


def memory_summary_response(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or DATA_DIR)
    data = load_memory_data(root)
    known_files = {**YAML_FILES, **JSONL_FILES}

    files = []
    for filename in sorted(set(known_files.values())):
        path = root / filename
        files.append(
            {
                "name": filename,
                "path": str(path),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
            }
        )

    return {
        "ok": True,
        "data_dir": str(root),
        "files": files,
        "profile": data.profile,
        "goals": data.goals,
        "projects": data.projects,
        "constraints": data.constraints,
        "counts": {
            "decisions": len(data.decisions),
            "memories": len(data.memories),
        },
        "missing_files": data.missing_files,
        "load_errors": data.load_errors,
    }


def settings_response(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or DATA_DIR)
    path = root / "settings.yaml"
    if not path.exists():
        return {
            "ok": True,
            "found": False,
            "path": str(path),
            "settings": {},
            "missing_files": ["settings.yaml"],
            "load_errors": [],
        }

    try:
        settings = read_yaml_file(path)
        if not isinstance(settings, dict):
            settings = {}
        return {
            "ok": True,
            "found": True,
            "path": str(path),
            "settings": settings,
            "model_config": model_info(load_model_config(root)),
            "permission_mode": load_permission_mode(root),
            "missing_files": [],
            "load_errors": [],
        }
    except Exception as exc:  # pragma: no cover - defensive diagnostics
        return {
            "ok": True,
            "found": True,
            "path": str(path),
            "settings": {},
            "missing_files": [],
            "load_errors": [{"file": "settings.yaml", "error": str(exc)}],
        }


def modules_response() -> dict[str, Any]:
    return {
        "ok": True,
        "modules": [
            _module("context-builder", "Context Builder", "上下文构建器", "build_context_pack(...)"),
            _module("memory-store", "Memory Store", "记忆存储", "load_memory_data(...)"),
            _module("settings", "Settings", "设置", "read data/settings.yaml"),
            _module("model-gateway", "Model Gateway", "模型网关", "load_model_config(); generate_response(); /api/ask"),
            _module("suggestion-engine", "Suggestion Engine", "建议引擎", "suggest_next_action(...)"),
            _module("permission-engine", "Permission Engine", "权限引擎", "evaluate_action(action, permission_mode)"),
            _module("system-panel", "Long-term Plan / System Panel", "长期计划 / 系统面板", "load_plan_data(); build_plan_context()"),
            _module("audit-log", "Audit Log", "审计日志", "append_audit_event(); read_audit_events(); build_audit_summary()"),
            _module("action-executor", "Action Executor", "动作执行器", "execute_confirmed_action(); cancel_action()"),
            *(module for module in PLACEHOLDER_MODULES if module["id"] != "action-executor"),
        ],
    }


def _module(module_id: str, name: str, display_name_zh: str, planned_interface: str) -> dict[str, Any]:
    return {
        "id": module_id,
        "name": name,
        "display_name_zh": display_name_zh,
        "status": "implemented",
        "status_label_zh": "已实现",
        "planned_interface": planned_interface,
        "planned_interface_zh": planned_interface,
    }


def plans_summary_response() -> dict[str, Any]:
    return plan_summary(DATA_DIR)


def plan_context_response(message: str) -> dict[str, Any]:
    return {"ok": True, **build_plan_context(message, data_dir=DATA_DIR)}


def plan_task_status_response(payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    task_id = str(payload.get("task_id") or "").strip()
    status = str(payload.get("status") or "").strip()
    note = payload.get("note")
    if not task_id:
        return 400, {"ok": False, "error": {"message": "task_id is required"}}
    if not status:
        return 400, {"ok": False, "error": {"message": "status is required"}}
    try:
        result = update_task_status(task_id, status, note=str(note) if note else None, data_dir=DATA_DIR)
        return 200, result
    except Exception as exc:
        return 400, {"ok": False, "error": {"message": str(exc), "type": exc.__class__.__name__}}


def system_task_complete_response(payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        return 400, {"ok": False, "error": {"message": "task_id is required"}}
    try:
        result = complete_and_settle_task(task_id, DATA_DIR)
    except Exception as exc:
        return 400, {"ok": False, "error": {"message": str(exc), "type": exc.__class__.__name__}}
    return (200 if result.get("ok") else 400), result


def system_quest_generate_response(payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    plan_id = payload.get("plan_id")
    try:
        result = generate_quest(DATA_DIR, plan_id=str(plan_id) if plan_id else None)
    except Exception as exc:
        return 400, {"ok": False, "error": {"message": str(exc), "type": exc.__class__.__name__}}
    return (200 if result.get("ok") else 400), result


def system_quest_accept_response(payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    quest = payload.get("quest") if isinstance(payload.get("quest"), dict) else None
    if not quest:
        return 400, {"ok": False, "error": {"message": "quest is required"}}
    try:
        result = accept_quest(quest, DATA_DIR)
    except Exception as exc:
        return 400, {"ok": False, "error": {"message": str(exc), "type": exc.__class__.__name__}}
    return (200 if result.get("ok") else 400), result


def plan_progress_response(payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    plan_id = str(payload.get("plan_id") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    if not plan_id:
        return 400, {"ok": False, "error": {"message": "plan_id is required"}}
    if not summary:
        return 400, {"ok": False, "error": {"message": "summary is required"}}

    try:
        progress_delta = int(payload.get("progress_delta") or 0)
    except (TypeError, ValueError):
        return 400, {"ok": False, "error": {"message": "progress_delta must be a number"}}

    entry = append_plan_progress(
        {
            "plan_id": plan_id,
            "summary": summary,
            "progress_delta": progress_delta,
            "note": payload.get("note") or "",
            "source": "debug_console",
        },
        data_dir=DATA_DIR,
    )
    return 200, {"ok": True, "progress_entry": entry}


def model_config_response() -> dict[str, Any]:
    return {"ok": True, "model_config": model_info(load_model_config(DATA_DIR))}


def model_test_response(payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    user_message = str(payload.get("user_message") or "测试模型网关").strip()
    model_override = payload.get("model_override") if isinstance(payload.get("model_override"), dict) else None
    return 200, test_model_gateway(user_message, data_dir=DATA_DIR, model_override=model_override)


def ask_response(payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    try:
        max_chars = int(payload.get("max_chars", 6000))
        max_memories = int(payload.get("max_memories", 8))
    except (TypeError, ValueError):
        return 400, {"ok": False, "error": {"message": "max_chars and max_memories must be numbers"}}

    model_override = payload.get("model_override") if isinstance(payload.get("model_override"), dict) else None
    result = ask(
        user_message=str(payload.get("user_message") or ""),
        data_dir=DATA_DIR,
        max_chars=max_chars,
        max_memories=max_memories,
        model_override=model_override,
    )
    return 200, result


def _build_suggestion_payload(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    user_message = str(payload.get("user_message") or "").strip()
    if not user_message:
        return 400, {"ok": False, "error": {"message": "user_message is required"}}

    try:
        max_chars = int(payload.get("max_chars", 6000))
        max_memories = int(payload.get("max_memories", 8))
    except (TypeError, ValueError):
        return 400, {"ok": False, "error": {"message": "max_chars and max_memories must be numbers"}}

    include_ask = bool(payload.get("include_ask", True))
    model_override = payload.get("model_override") if isinstance(payload.get("model_override"), dict) else None
    context_pack = build_context_pack(
        user_message=user_message,
        data_dir=str(DATA_DIR),
        max_chars=max_chars,
        max_memories=max_memories,
    )
    context_dict = context_pack.to_dict()
    ask_result = None
    if include_ask:
        ask_result = ask(
            user_message=user_message,
            data_dir=DATA_DIR,
            max_chars=max_chars,
            max_memories=max_memories,
            model_override=model_override,
        )
    suggestion = suggest_next_action(
        user_message=user_message,
        context_pack=context_dict,
        ask_result=ask_result,
        plan_context=context_dict.get("plan_context"),
    )
    return 200, {
        "ok": True,
        "suggestion": suggestion,
        "context_pack": context_dict,
        "ask_result": ask_result,
    }


def suggest_response(payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    return _build_suggestion_payload(payload or {})


def permission_evaluate_response(payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    action = payload.get("action") if isinstance(payload.get("action"), dict) else None
    mode = payload.get("permission_mode") or load_permission_mode(DATA_DIR)
    decision = evaluate_action(action, permission_mode=str(mode))
    body: dict[str, Any] = {"ok": True, "decision": decision}
    audit_event, audit_error = _append_permission_audit_event(action, decision, source="api")
    if audit_event:
        body["audit_event"] = audit_event
    if audit_error:
        body["audit_error"] = audit_error
    return 200, body


def suggest_with_permission_response(payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    status_code, body = _build_suggestion_payload(payload)
    if status_code != 200:
        return status_code, body

    suggestion = body["suggestion"]
    mode = payload.get("permission_mode") or load_permission_mode(DATA_DIR)
    action = suggestion.get("action") if suggestion.get("type") == "suggested_action" else None
    body["permission_decision"] = evaluate_action(action, permission_mode=str(mode))
    audit_event, audit_error = _append_permission_audit_event(action, body["permission_decision"], source="api_suggest")
    if audit_event:
        body["permission_audit_event"] = audit_event
    if audit_error:
        body["audit_error"] = audit_error
    return 200, body


def audit_events_response(args: Any) -> dict[str, Any]:
    limit = args.get("limit", 50) if args else 50
    event_type = args.get("event_type") if args else None
    action_id = args.get("action_id") if args else None
    events = read_audit_events(
        data_dir=DATA_DIR,
        limit=_coerce_int(limit, default=50),
        event_type=str(event_type) if event_type else None,
        action_id=str(action_id) if action_id else None,
    )
    return {"ok": True, "events": events, "count": len(events)}


def append_audit_event_response(payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    event = append_audit_event({**payload, "source": payload.get("source") or "api"}, data_dir=DATA_DIR)
    return 200, {"ok": True, "event": event}


def audit_summary_response() -> dict[str, Any]:
    return build_audit_summary(data_dir=DATA_DIR, limit=20)


def action_confirm_response(payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    permission_decision = payload.get("permission_decision")
    if not isinstance(permission_decision, dict) or not permission_decision:
        mode = payload.get("permission_mode") or load_permission_mode(DATA_DIR)
        permission_decision = evaluate_action(action, permission_mode=str(mode))
    execution = execute_confirmed_action(
        action=action,
        permission_decision=permission_decision,
        confirmed=True,
        data_dir=DATA_DIR,
    )
    return 200, {"ok": True, "execution": execution, "permission_decision": permission_decision}


def action_cancel_response(payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    permission_decision = payload.get("permission_decision") if isinstance(payload.get("permission_decision"), dict) else None
    execution = cancel_action(action=action, permission_decision=permission_decision, data_dir=DATA_DIR)
    return 200, {"ok": True, "execution": execution}


def _append_permission_audit_event(
    action: dict[str, Any] | None,
    decision: dict[str, Any],
    source: str,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    action = action if isinstance(action, dict) else None
    try:
        event = append_audit_event(
            {
                "event_type": "permission_evaluated",
                "actor": "system",
                "module": "permission_engine",
                "action_id": action.get("id") if action else "",
                "action_kind": decision.get("action_kind", ""),
                "target": action.get("target") if action else "",
                "risk_level": decision.get("risk_level", ""),
                "permission_mode": decision.get("permission_mode", ""),
                "requires_confirmation": decision.get("requires_confirmation", False),
                "status": "success",
                "summary": f"权限评估完成：{decision.get('action_kind', 'unknown')}。",
                "payload": {
                    "action": action or {},
                    "decision": decision,
                },
                "source": source,
            },
            data_dir=DATA_DIR,
        )
        return event, None
    except Exception as exc:  # pragma: no cover - audit logging must not break permission evaluation
        return None, {"message": str(exc), "type": exc.__class__.__name__}


def _coerce_int(value: Any, default: int = 50) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _read_debug_html() -> str:
    path = STATIC_DIR / "debug_console.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"<!doctype html><title>{DEBUG_TITLE}</title><h1>{DEBUG_TITLE}</h1>"


def _read_app_html() -> str:
    path = STATIC_DIR / "app.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"<!doctype html><title>{APP_TITLE}</title><h1>{APP_TITLE}</h1>"


def _read_system_html() -> str:
    path = STATIC_DIR / "system.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"<!doctype html><title>{SYSTEM_TITLE}</title><h1>{SYSTEM_TITLE}</h1>"


app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    static_url_path="/static",
)
app.config["JSON_AS_ASCII"] = False


@app.get("/app")
def app_page() -> Response:
    return Response(_read_app_html(), mimetype="text/html")


@app.get("/debug")
def debug_page() -> Response:
    return Response(_read_debug_html(), mimetype="text/html")


@app.get("/system")
def system_page() -> Response:
    return Response(_read_system_html(), mimetype="text/html")


@app.get("/api/system/summary")
def api_system_summary() -> Response:
    return jsonify(build_system_summary(DATA_DIR))


@app.post("/api/system/tasks/complete")
def api_system_task_complete() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = system_task_complete_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code


@app.post("/api/system/quest/generate")
def api_system_quest_generate() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = system_quest_generate_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code


@app.post("/api/system/quest/accept")
def api_system_quest_accept() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = system_quest_accept_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code


@app.post("/api/context/build")
def api_build_context() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = build_context_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code


@app.get("/api/memory/summary")
def api_memory_summary() -> Response:
    return jsonify(memory_summary_response())


@app.get("/api/settings")
def api_settings() -> Response:
    return jsonify(settings_response())


@app.get("/api/modules")
def api_modules() -> Response:
    return jsonify(modules_response())


@app.get("/api/plans/summary")
def api_plans_summary() -> Response:
    return jsonify(plans_summary_response())


@app.post("/api/plans/tasks/status")
def api_plan_task_status() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = plan_task_status_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code


@app.post("/api/plans/progress")
def api_plan_progress() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = plan_progress_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code


@app.get("/api/plan/context")
def api_plan_context() -> Response:
    message = request.args.get("message", "")
    return jsonify(plan_context_response(message))


@app.get("/api/model/config")
def api_model_config() -> Response:
    return jsonify(model_config_response())


@app.post("/api/model/test")
def api_model_test() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = model_test_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code


@app.post("/api/ask")
def api_ask() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = ask_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code


@app.post("/api/suggest")
def api_suggest() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = suggest_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code


@app.post("/api/permission/evaluate")
def api_permission_evaluate() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = permission_evaluate_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code


@app.post("/api/suggest/with-permission")
def api_suggest_with_permission() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = suggest_with_permission_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code


@app.get("/api/audit/events")
def api_audit_events() -> Response:
    return jsonify(audit_events_response(request.args))


@app.post("/api/audit/events")
def api_append_audit_event() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = append_audit_event_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code


@app.get("/api/audit/summary")
def api_audit_summary() -> Response:
    return jsonify(audit_summary_response())


@app.post("/api/actions/confirm")
def api_actions_confirm() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = action_confirm_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code


@app.post("/api/actions/cancel")
def api_actions_cancel() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    status_code, body = action_cancel_response(payload if isinstance(payload, dict) else {})
    return jsonify(body), status_code
