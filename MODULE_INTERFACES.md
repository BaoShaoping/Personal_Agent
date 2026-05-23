# Module Interfaces

This document records the current module boundaries in `Personal_Agent`.
It is intended for cross-session development, unified orchestration, and future module governance.

## Product Positioning

Personal Agent is currently a local long-term plan / growth system panel.

The user value center is:

- Long-term Plan / System Panel
- today's status and tasks
- growth progress
- context-aware next-step suggestions

Suggestion Engine, Permission Engine, Action Executor, and Audit Log are support capabilities for that loop. They should not pull the project toward a generic agent runtime, a Codex replacement, or an OpenClaw replacement. OpenClaw remains a future adapter option only if it supports the long-term growth workflow.

`GET /app` is the user-facing demo surface. `GET /debug` is the development module console.

## Runtime Rule

- Python executable:
  `C:\Users\STAR\.conda\envs\py39\python.exe`
- Test command:
  `C:\Users\STAR\.conda\envs\py39\python.exe -m pytest`
- Recommended test command to avoid pytest cache residue:
  `C:\Users\STAR\.conda\envs\py39\python.exe -m pytest backend\tests -p no:cacheprovider`
- Debug console command:
  ```powershell
  cd backend
  C:\Users\STAR\.conda\envs\py39\python.exe -m flask --app personal_agent.api run --debug --port 5000
  ```
- Current backend framework: Flask.
- Do not rely on shell default `python`.

## Module Status Table

| Module | Status | Read files | Write files | Public functions | HTTP APIs | Used by |
| --- | --- | --- | --- | --- | --- | --- |
| Memory Store | implemented | `profile.yaml`, `goals.yaml`, `projects.yaml`, `constraints.yaml`, `settings.yaml`, `decisions.jsonl`, `memories.jsonl` | none | `load_memory_data`, `read_jsonl_file`, `read_yaml_file`, `parse_simple_yaml` | `GET /api/memory/summary`, `GET /api/settings` | Context Builder, Plan Store, Model Gateway, Debug API |
| Context Builder | implemented | Memory Store files, Plan Store files | none | `build_context_pack` plus helper functions | `POST /api/context/build` | Ask Service, Suggestion Engine, Debug API |
| Long-term Plan / System Panel | implemented | `plans.yaml`, `plan_tasks.jsonl`, `plan_progress.jsonl`, `reminders.yaml` | `plan_tasks.jsonl`, `plan_progress.jsonl` | `load_plan_data`, `list_active_plans`, `list_today_tasks`, `create_plan_task`, `update_task_status`, `append_plan_progress`, `build_plan_context`, `plan_summary` | `GET /api/plans/summary`, `POST /api/plans/tasks/status`, `POST /api/plans/progress`, `GET /api/plan/context` | Context Builder, Suggestion Engine, Action Executor, Debug API |
| Demo Seed Reset Helper | implemented | `plan_tasks.jsonl` | `plan_tasks.jsonl`, `demo_reset_archive/*.jsonl`, `audit_log.jsonl` | `reset_demo_today_tasks` | none | local demo setup |
| Model Gateway | implemented | `settings.yaml`; environment variable named by `api_key_env` | none | `load_model_config`, `validate_model_config`, `build_model_messages`, `generate_response`, `generate_structured_output`, `model_info` | `GET /api/model/config`, `POST /api/model/test` | Ask Service, Debug API |
| Ask Service | implemented | Context Builder files, Model Gateway config | none | `ask`, `test_model_gateway` | `POST /api/ask` | Suggestion Engine API flow, Debug API, future desktop UI |
| User App / Growth Panel | implemented | static files and `/api/*` responses | via Action/Plan APIs only | static HTML/CSS/JS in `backend/static/app.*` | `GET /app` | User-facing local demo |
| Debug API / Module Debug Console | implemented | all above module files, static files | via Plan, Audit Log, and Action APIs | Flask `app`; response helper functions in `api.py` | all `/api/*` listed below, `GET /debug` | Developer/debug workflow |
| Suggestion Engine | implemented | context/ask/plan data passed in by caller | none | `suggest_next_action` | `POST /api/suggest`, `POST /api/suggest/with-permission` | Debug API, Permission Engine |
| Permission Engine | implemented | `settings.yaml` permission mode; action payload passed in by caller | none | `load_permission_mode`, `evaluate_action` | `POST /api/permission/evaluate`, `POST /api/suggest/with-permission` | Debug API, Suggestion flow, Action Executor |
| Audit Log | implemented | `audit_log.jsonl` | `audit_log.jsonl` | `append_audit_event`, `read_audit_events`, `build_audit_summary`, `redact_sensitive` | `GET /api/audit/events`, `POST /api/audit/events`, `GET /api/audit/summary` | Debug API, Permission flow, Action Executor |
| Action Executor | implemented | action payloads, permission results, `plans.yaml`, `plan_tasks.jsonl`, memory JSONL files | `plans.yaml`, `plan_tasks.jsonl`, `plan_progress.jsonl`, `memories.jsonl`, `decisions.jsonl`, `audit_log.jsonl` | `execute_confirmed_action`, `cancel_action` | `POST /api/actions/confirm`, `POST /api/actions/cancel` | Debug API, Suggestion flow |
| OpenClaw Adapter | future | adapter config only | none by default | draft only | none | future integration only |
| Voice Module | future | none | none | draft only | none | future desktop UI |
| Sync / Account | future | none | none | draft only | none | future sync layer |

## Memory Store

### Purpose

Load transparent local memory files for context construction and debug inspection.

### Public Functions

- `load_memory_data(data_dir: str | Path = "data") -> MemoryData`
- `read_jsonl_file(path: str | Path) -> list[dict[str, Any]]`
- `read_yaml_file(path: str | Path) -> Any`
- `parse_simple_yaml(text: str) -> Any`

### Inputs

- `data_dir`: directory containing local memory files.
- YAML files are parsed with PyYAML when available, otherwise a small fallback YAML parser.
- JSONL files are read line by line.

### Outputs

`MemoryData` dataclass:

- `data_dir: Path`
- `profile: dict`
- `goals: dict`
- `projects: dict`
- `constraints: dict`
- `settings: dict`
- `decisions: list[dict]`
- `memories: list[dict]`
- `missing_files: list[str]`
- `load_errors: list[dict[str, str]]`

### Data Files

Reads:

- `data/profile.yaml`
- `data/goals.yaml`
- `data/projects.yaml`
- `data/constraints.yaml`
- `data/settings.yaml`
- `data/decisions.jsonl`
- `data/memories.jsonl`

### Side Effects

None. This module is read-only.

### Error Behavior

- Missing files are added to `missing_files`.
- YAML load exceptions are added to `load_errors`; that attribute is set to `{}`.
- JSONL file load exceptions are added to `load_errors`; that attribute is set to `[]`.
- Malformed JSONL lines are converted into records with:
  - `type: load_error`
  - `_load_error: invalid_json`

### Used By

- Context Builder
- Plan Store, for YAML/JSONL helpers
- Model Gateway, for `settings.yaml`
- Debug API

## Context Builder

### Purpose

Build a compact, traceable `ContextPack` for model prompts and downstream modules.

### Public Function

```python
build_context_pack(
    user_message: str,
    data_dir: str = "data",
    max_chars: int = 6000,
    max_memories: int = 8,
) -> ContextPack
```

### Inputs

- `user_message`: current user text.
- `data_dir`: local data directory.
- `max_chars`: hard cap for rendered `context_markdown`.
- `max_memories`: selection limit shared across decisions/memories and plan context max items.

### Outputs

`ContextPack` dataclass fields:

- `user_message`
- `profile_summary`
- `active_goals`
- `active_projects`
- `active_plans`
- `plan_context`
- `constraints`
- `relevant_decisions`
- `relevant_memories`
- `context_markdown`
- `sources`
- `omitted`
- `stats`

### `context_markdown` Sections

Current section order:

1. `User Message`
2. `Profile`
3. `Active Goals`
4. `Active Projects`
5. `Active Long-term Plans`
6. `Constraints`
7. `Relevant Decisions`
8. `Relevant Memories`

Sections/items that exceed `max_chars` are omitted or truncated.

### `sources`

List of traceable source refs. Current source entries can include:

- `profile.yaml`
- `goals.yaml`
- `projects.yaml`
- `constraints.yaml`
- `decisions.jsonl` or record-level `source` values such as `conversation`
- `memories.jsonl` or record-level `source`
- `plans.yaml`
- `plan_tasks.jsonl`
- `plan_progress.jsonl`
- `reminders.yaml`

Each source can include:

- `source`
- `id`
- `path`
- `kind`

### `omitted`

Shape:

```json
{
  "sections": [],
  "items": 0,
  "truncated": false
}
```

Meaning:

- `sections`: sections that could not be included.
- `items`: count of omitted individual lines.
- `truncated`: whether the rendered context had to be truncated.

### `stats`

Includes:

- `max_chars`
- `context_chars`
- `query_terms`
- `loaded`: counts for goals, projects, plans, plan tasks, plan progress, constraints, decisions, memories.
- `selected`: counts for plans, today tasks, recent progress, decisions, memories.
- `missing_files`: merged memory and plan missing files.
- `load_errors`: merged memory and plan load errors.

### Side Effects

None. This module is read-only.

### Used By

- Ask Service
- Debug API
- Future Suggestion Engine

## Long-term Plan / System Panel

### Purpose

Represent long-term plans as first-class personal context and expose a lightweight system-panel view.

This module is the product's main differentiation. It owns the long-term growth continuity that `/app` should make visible: active plans, today status, today tasks when present, recent progress, and passive reminder context.

### Public Functions

```python
load_plan_data(data_dir: str | Path = "data") -> PlanData
list_active_plans(data_dir: str | Path = "data") -> list[dict]
list_today_tasks(plan_id: str | None = None, data_dir: str | Path = "data", today: date | None = None) -> list[dict]
create_plan_task(entry: dict, data_dir: str | Path = "data") -> dict
update_task_status(task_id: str, status: str, note: str | None = None, data_dir: str | Path = "data") -> dict
append_plan_progress(entry: dict, data_dir: str | Path = "data") -> dict
build_plan_context(user_message: str, data_dir: str | Path = "data", max_items: int = 5) -> dict
plan_summary(data_dir: str | Path = "data", today: date | None = None) -> dict
```

### Data Files

Reads:

- `data/plans.yaml`
- `data/plan_tasks.jsonl`
- `data/plan_progress.jsonl`
- `data/reminders.yaml`

Writes:

- `create_plan_task(...)` appends one task to `plan_tasks.jsonl`.
- `update_task_status(...)` rewrites `plan_tasks.jsonl`.
- `update_task_status(...)` also appends a progress entry to `plan_progress.jsonl`.
- `append_plan_progress(...)` appends to `plan_progress.jsonl`.

### `PlanData`

Fields:

- `data_dir`
- `plans`
- `tasks`
- `progress`
- `reminders`
- `missing_files`
- `load_errors`

### Enumerations

- Plan status: `active`, `paused`, `completed`, `archived`
- Plan kind: `main`, `side`
- Task status: `todo`, `done`, `skipped`, `blocked`
- Reminder mode: `off`, `passive`, `daily`

### Function Behavior

- `load_plan_data(...)`: read all plan files, normalize records, collect missing files/load errors.
- `list_active_plans(...)`: return plans with `status == "active"`.
- `list_today_tasks(...)`: return tasks whose `date` equals `today or date.today()`; optionally filter by `plan_id`.
- `create_plan_task(...)`: append one `todo` task for an existing plan; used by `create_today_task_candidate`.
- `update_task_status(...)`: validate status, update one task, set `updated_at`, optional `note`, rewrite JSONL, append progress entry.
- `append_plan_progress(...)`: add `id`, `created_at`, default `source`, append JSONL.
- `build_plan_context(...)`: return active plans, today tasks, recent progress, reminder settings, sources, diagnostics, stats.
- `plan_summary(...)`: return active plans, today tasks, recent progress, reminders, diagnostics, counts.
- Empty today's task list is valid when no task is dated today. UI and demo docs should still show active plans and recent progress instead of treating this as a failure.

### Side Effects

- Read-only: `load_plan_data`, `list_active_plans`, `list_today_tasks`, `build_plan_context`, `plan_summary`.
- Writes files: `create_plan_task`, `update_task_status`, `append_plan_progress`.

### Used By

- Context Builder
- Debug API
- Future Suggestion Engine

## Demo Seed Reset Helper

Status: implemented.

Purpose: make the freeze demo repeatable by starting from an empty task list for the current date.

Public function:

```python
reset_demo_today_tasks(
    data_dir: str | Path = "data",
    today: date | None = None,
    write_audit: bool = True,
) -> dict
```

CLI:

```powershell
cd C:\Users\STAR\Desktop\Personal_Agent
C:\Users\STAR\.conda\envs\py39\python.exe scripts\reset_demo_seed.py
```

Behavior:

- Reads `data/plan_tasks.jsonl`.
- Moves only records whose `date` equals `today or date.today()` into `data/demo_reset_archive/plan_tasks_*.jsonl`.
- Rewrites `data/plan_tasks.jsonl` without those records.
- Leaves `data/plans.yaml` and the action schema unchanged.
- Appends a `demo_seed_reset` audit event only when records are moved.
- No-ops when today's task list is already empty.

Rules:

- Demo-only setup helper, not a general task management API.
- Does not expose an HTTP API.
- Does not delete archived records.
- Keeps malformed JSONL lines in the active task file instead of dropping them.

## Model Gateway

### Purpose

Provide one interface for OpenAI-compatible chat completions and deterministic local mock responses.

### Public Functions

```python
load_model_config(data_dir: str | Path = "data") -> dict
validate_model_config(model_config: dict) -> list[str]
build_model_messages(user_message: str, context_markdown: str) -> list[dict[str, str]]
generate_response(messages: list[dict[str, str]], model_config: dict) -> dict
generate_structured_output(messages: list[dict[str, str]], schema: dict, model_config: dict) -> dict
model_info(model_config: dict) -> dict
```

### Data Files and Secrets

Reads:

- `data/settings.yaml`

Reads environment:

- Environment variable named by `model.api_key_env`, default `PERSONAL_AGENT_API_KEY`.

Never returns the raw API key. Public model config surfaces only:

- `api_key_env`
- `api_key_present`

### Model Config

Current default/expected shape:

```yaml
model:
  provider: openai_compatible
  base_url: ""
  model_name: ""
  api_key_env: PERSONAL_AGENT_API_KEY
  temperature: 0.4
  max_tokens: 1200
  mode: mock
```

### Mock Mode

`mode: mock`:

- No network call.
- Returns deterministic answer beginning with `[mock answer]`.
- Returns `usage.mock: true`.
- Does not require `base_url`, `model_name`, or API key.

### Live Mode

`mode: live`:

- Calls OpenAI-compatible Chat Completions.
- URL normalization:
  - `.../chat/completions` is used as-is.
  - `.../v1` becomes `.../v1/chat/completions`.
  - otherwise appends `/v1/chat/completions`.
- Requires:
  - `provider == "openai_compatible"`
  - `base_url`
  - `model_name`
  - environment variable named by `api_key_env`

### Error Behavior

`validate_model_config(...)` returns a list of strings.

`generate_response(...)` returns:

```json
{
  "ok": false,
  "answer": "",
  "model_info": {},
  "usage": null,
  "error": {
    "message": "...",
    "details": []
  }
}
```

for validation failures. Live network/HTTP failures return `ok: false` with `error.message`.

### Side Effects

- Mock mode: none.
- Live mode: external HTTP request to model provider.
- No local file writes.

### Used By

- Ask Service
- Debug API

## Ask Service

### Purpose

Run the MVP ask flow: user message -> context pack -> model messages -> gateway response -> traceable answer.

### Public Functions

```python
ask(
    user_message: str,
    data_dir: str | Path = "data",
    max_chars: int = 6000,
    max_memories: int = 8,
    model_override: dict | None = None,
) -> dict

test_model_gateway(
    user_message: str,
    data_dir: str | Path = "data",
    model_override: dict | None = None,
) -> dict
```

### Flow

1. Validate/strip `user_message`.
2. Call `build_context_pack(...)`.
3. Load model config from `settings.yaml`.
4. Apply optional `model_override`.
5. Build model messages with system prompt + `context_markdown` + user message.
6. Call `model_gateway.generate_response(...)`.
7. Return answer, context, message preview, model info, usage/error.

### Output Fields

`ask(...)` returns:

- `ok`
- `answer`
- `model_info`
- `context_pack`
- `messages_preview`
- `usage`
- `error`

If `user_message` is empty:

- `ok: false`
- `context_pack: null`
- `error.message: "user_message is required"`

### Side Effects

- Usually read-only.
- If Model Gateway is `mode: live`, it can make an external HTTP request.
- No local file writes.

### Used By

- Debug API
- Future desktop UI
- Future Suggestion Engine can consume `ask_result`.

## Debug API / Module Debug Console

Current backend is Flask app in `backend/personal_agent/api.py`.

### `GET /app`

- Purpose: serve the user-facing local growth system panel demo.
- Request shape: none.
- Response shape: HTML.
- Side effects: none on page load; user interactions call API endpoints listed below.
- Static files:
  - `backend/static/app.html`
  - `backend/static/app.css`
  - `backend/static/app.js`
- Product role:
  - Primary local demo surface.
  - Shows today's status, active long-term plans, today's tasks or a natural empty state, recent progress, conversation, suggested action card, and recent audit records.
  - When today's tasks are empty, shows `生成今日最小任务`, which sends a normal suggestion request instead of directly writing tasks.
  - Raw JSON is available for traceability but should stay visually secondary.

### `GET /debug`

- Purpose: serve the development-only Module Debug Console HTML.
- Request shape: none.
- Response shape: HTML.
- Side effects: none.
- Notes: static assets are served from `backend/static`.

### `POST /api/context/build`

- Purpose: build and inspect a `ContextPack`.
- Request:
  ```json
  {
    "user_message": "text",
    "max_chars": 6000,
    "max_memories": 8
  }
  ```
- Response: `{ "ok": true, ...ContextPack fields }`
- Side effects: none.
- Error behavior: missing `user_message` returns HTTP 400.

### `GET /api/memory/summary`

- Purpose: inspect memory files and loader diagnostics.
- Request: none.
- Response includes:
  - `ok`
  - `data_dir`
  - `files`
  - `profile`
  - `goals`
  - `projects`
  - `constraints`
  - `counts`
  - `missing_files`
  - `load_errors`
- Side effects: none.

### `GET /api/settings`

- Purpose: inspect `settings.yaml` and sanitized model config.
- Request: none.
- Response includes:
  - `ok`
  - `found`
  - `path`
  - `settings`
  - `model_config` when settings load succeeds
  - `permission_mode`
  - `missing_files`
  - `load_errors`
- Side effects: none.
- Notes: `model_config` must not expose raw API key.

### `GET /api/modules`

- Purpose: list implemented and placeholder module status.
- Request: none.
- Response: `{ "ok": true, "modules": [...] }`
- Side effects: none.

### `GET /api/plans/summary`

- Purpose: inspect active plans, today's tasks, recent progress, reminder settings.
- Request: none.
- Response: `plan_summary(...)`.
- Side effects: none.

### `POST /api/plans/tasks/status`

- Purpose: update one plan task status from the debug UI.
- Request:
  ```json
  {
    "task_id": "task_...",
    "status": "todo|done|skipped|blocked",
    "note": "optional"
  }
  ```
- Response:
  ```json
  {
    "ok": true,
    "task": {},
    "progress_entry": {}
  }
  ```
- Side effects:
  - rewrites `plan_tasks.jsonl`
  - appends `plan_progress.jsonl`
- Error behavior: invalid/missing task or status returns HTTP 400.

### `POST /api/plans/progress`

- Purpose: append a manual plan progress record.
- Request:
  ```json
  {
    "plan_id": "plan_...",
    "summary": "text",
    "progress_delta": 1,
    "note": "optional"
  }
  ```
- Response:
  ```json
  {
    "ok": true,
    "progress_entry": {}
  }
  ```
- Side effects: appends `plan_progress.jsonl`.
- Error behavior: missing `plan_id` or `summary` returns HTTP 400.

### `GET /api/plan/context`

- Purpose: inspect how long-term plan context would be injected.
- Query:
  - `message`: optional user message.
- Response: `{ "ok": true, ...build_plan_context fields }`
- Side effects: none.

### `GET /api/model/config`

- Purpose: inspect current model configuration safely.
- Request: none.
- Response:
  ```json
  {
    "ok": true,
    "model_config": {
      "provider": "openai_compatible",
      "mode": "mock|live",
      "base_url": "",
      "model_name": "",
      "api_key_env": "PERSONAL_AGENT_API_KEY",
      "api_key_present": false,
      "temperature": 0.4,
      "max_tokens": 1200
    }
  }
  ```
- Side effects: none.
- Notes: raw API key is never returned.

### `POST /api/model/test`

- Purpose: test Model Gateway independently of Context Builder.
- Request:
  ```json
  {
    "user_message": "text",
    "model_override": {}
  }
  ```
- Response:
  - `ok`
  - `answer`
  - `model_info`
  - `messages_preview`
  - `usage`
  - `error`
- Side effects:
  - mock mode: none
  - live mode: external HTTP request

### `POST /api/ask`

- Purpose: run full Ask Service flow.
- Request:
  ```json
  {
    "user_message": "text",
    "max_chars": 6000,
    "max_memories": 8,
    "model_override": {}
  }
  ```
- Response:
  - `ok`
  - `answer`
  - `model_info`
  - `context_pack`
  - `messages_preview`
  - `usage`
  - `error`
- Side effects:
  - mock mode: none
  - live mode: external HTTP request
- Notes: this does not create action cards or execute actions.

### `POST /api/suggest`

- Purpose: run the read-only Suggestion Engine over a user message, context pack, optional ask result, and plan context.
- Request:
  ```json
  {
    "user_message": "text",
    "max_chars": 6000,
    "max_memories": 8,
    "include_ask": true
  }
  ```
- Behavior:
  - builds `context_pack`
  - optionally calls Ask Service when `include_ask` is true
  - calls `suggest_next_action(...)`
  - does not execute any suggested action
- Response:
  - `ok`
  - `suggestion`
  - `context_pack`
  - `ask_result`
- Side effects:
  - `include_ask: false`: none
  - `include_ask: true` with model mock mode: none
  - `include_ask: true` with model live mode: external model HTTP request through Ask Service
- Notes:
  - The Suggestion Engine itself is read-only.
  - `suggested_action` output is only a candidate shape for Permission Engine and Action Executor.

### `POST /api/permission/evaluate`

- Purpose: evaluate a suggested action without executing it.
- Request:
  ```json
  {
    "action": {
      "kind": "update_plan_task_status",
      "target": "task_...",
      "payload": {}
    },
    "permission_mode": "ask_first"
  }
  ```
- Behavior:
  - uses request `permission_mode` when provided
  - otherwise reads `permission_mode` from `data/settings.yaml`
  - normalizes invalid modes to `ask_first`
  - recalculates risk from `action.kind` instead of trusting suggestion-provided risk fields
- Response:
  ```json
  {
    "ok": true,
    "decision": {
      "ok": true,
      "permission_mode": "ask_first",
      "action_kind": "update_plan_task_status",
      "risk_level": "medium",
      "requires_confirmation": true,
      "allowed_without_confirmation": false,
      "reason": "...",
      "hard_block": false
    }
  }
  ```
- Side effects: appends a `permission_evaluated` event to `data/audit_log.jsonl`; its display `summary` is Chinese, e.g. `权限评估完成：save_memory_candidate。`.
- Notes: no action is executed.

### `POST /api/suggest/with-permission`

- Purpose: run Suggestion Engine and immediately evaluate any suggested action.
- Request:
  ```json
  {
    "user_message": "text",
    "max_chars": 6000,
    "max_memories": 8,
    "include_ask": true,
    "permission_mode": "ask_first"
  }
  ```
- Behavior:
  - builds `context_pack`
  - optionally calls Ask Service when `include_ask` is true
  - calls `suggest_next_action(...)`
  - when `suggestion.type == "suggested_action"`, evaluates `suggestion.action`
  - when suggestion is `answer_only`, evaluates no action as low risk
  - does not execute any suggested action
- Response:
  - `ok`
  - `suggestion`
  - `permission_decision`
  - `context_pack`
  - `ask_result`
- Side effects:
  - same as `POST /api/suggest`: no local writes; optional live model call only if Ask Service uses live mode.
  - appends a `permission_evaluated` event to `audit_log.jsonl`; its display `summary` is Chinese, e.g. `权限评估完成：save_memory_candidate。`.
  - Permission Engine itself is read-only.

### `GET /api/audit/events`

- Purpose: read recent audit events for debugging and trace inspection.
- Query:
  - `limit`: optional integer, default `50`
  - `event_type`: optional filter
  - `action_id`: optional filter
- Response:
  ```json
  {
    "ok": true,
    "events": [],
    "count": 0
  }
  ```
- Side effects: none.

### `POST /api/audit/events`

- Purpose: append a manual audit event from the debug console.
- Request:
  ```json
  {
    "event_type": "permission_evaluated",
    "module": "permission_engine",
    "action_kind": "update_plan_task_status",
    "summary": "Manual test event.",
    "payload": {}
  }
  ```
- Response:
  ```json
  {
    "ok": true,
    "event": {}
  }
  ```
- Side effects: appends one redacted event to `data/audit_log.jsonl`; creates the file if missing.
- Notes: sensitive keys in payload are redacted before writing.

### `GET /api/audit/summary`

- Purpose: summarize recent audit events for the Debug Console.
- Request: none.
- Response:
  ```json
  {
    "ok": true,
    "recent_events": [],
    "counts_by_type": {},
    "counts_by_status": {}
  }
  ```
- Side effects: none.

### `POST /api/actions/confirm`

- Purpose: confirm and execute one allowlisted action.
- Request:
  ```json
  {
    "action": {},
    "permission_decision": {},
    "permission_mode": "ask_first"
  }
  ```
- Behavior:
  - uses caller-supplied `permission_decision` when present
  - otherwise evaluates the action with Permission Engine using `permission_mode`
  - calls `execute_confirmed_action(..., confirmed=True)`
  - does not execute unsupported, hard-blocked, or invalid actions
- Response:
  ```json
  {
    "ok": true,
    "execution": {},
    "permission_decision": {}
  }
  ```
- Side effects:
  - for every confirmed call, appends `action_confirmed`
  - on success, writes the target local file for the allowlisted action and appends `action_executed`
  - on failure, appends `action_failed`

### `POST /api/actions/cancel`

- Purpose: cancel one proposed action without executing it.
- Request:
  ```json
  {
    "action": {},
    "permission_decision": {},
    "reason": "user canceled"
  }
  ```
- Response:
  ```json
  {
    "ok": true,
    "execution": {
      "status": "canceled"
    }
  }
  ```
- Side effects: appends `action_canceled` to `data/audit_log.jsonl`.

## Downstream Modules

Suggestion Engine, Permission Engine, Audit Log, and Action Executor are implemented. The remaining modules in this section are future placeholders.
Future code should respect the boundaries below and avoid direct file writes unless explicitly stated.

### Suggestion Engine

Status: implemented.

Purpose: decide whether a model answer should remain `answer_only` or become a user-confirmable suggested action.

Product role: support the growth system panel by proposing memory, plan, or progress actions when the user's message naturally maps to the long-term growth loop. It is not a general autonomous planner.

Public function:

```python
suggest_next_action(
    user_message: str,
    context_pack: dict,
    ask_result: dict | None = None,
    plan_context: dict | None = None,
) -> dict
```

Inputs:

- `user_message`: raw user text.
- `context_pack`: current `ContextPack.to_dict()`.
- `ask_result`: optional output from Ask Service.
- `plan_context`: optional plan context; defaults to `context_pack["plan_context"]` when available.

Outputs:

```json
{
  "type": "answer_only",
  "answer": "...",
  "reason": "当前没有需要执行的安全具体操作。"
}
```

or:

```json
{
  "type": "suggested_action",
  "title": "...",
  "message": "...",
  "action": {
    "id": "act_...",
    "kind": "...",
    "title": "...",
    "summary": "...",
    "target": "...",
    "payload": {},
    "source": "suggestion_engine",
    "created_at": "2026-05-09T12:00:00+08:00",
    "risk_level": "medium",
    "requires_confirmation": true
  },
  "buttons": ["confirm", "cancel"],
  "reason": "..."
}
```

### Canonical MVP Action Shape

`suggested_action.action` is the canonical action envelope passed from Suggestion Engine to Permission Engine, Audit Log, Action Executor, and Debug Console.

```json
{
  "id": "act_YYYYMMDD_HHMMSS_ffffff",
  "kind": "save_memory_candidate",
  "title": "保存记忆候选",
  "summary": "将用户提供的内容保存为记忆候选。",
  "target": "memories.jsonl",
  "payload": {},
  "source": "suggestion_engine",
  "created_at": "2026-05-09T12:00:00+08:00",
  "risk_level": "medium",
  "requires_confirmation": true
}
```

Required for actions produced by Suggestion Engine:

- `id`
- `kind`
- `title`
- `summary`
- `target`
- `payload`
- `source`
- `created_at`
- `risk_level`
- `requires_confirmation`

Minimum accepted by Action Executor APIs:

- `kind`
- `target`, when the action kind needs a file or task target
- `payload`

Field ownership:

- Suggestion Engine sets `id`, Chinese display metadata (`title`, `summary`, top-level `message`, `reason`), `target`, `payload`, `source`, `created_at`, and initial `risk_level` / `requires_confirmation`.
- Permission Engine reads `kind` and recalculates risk; it does not trust action-provided `risk_level` or `requires_confirmation`.
- Action Executor reads `id`, `kind`, `target`, and `payload`; missing `id` is allowed but audit trace quality is worse.
- Audit Log records the action and recursively redacts sensitive payload keys.

Implemented action kinds:

- `save_memory_candidate`
  - target: `memories.jsonl` or `decisions.jsonl`
  - trigger: user asks to remember/save or expresses a decision/reminder
- `create_plan_candidate`
  - target: `plans.yaml`
  - trigger: user expresses a long-term learning/improvement/preparation plan and no obvious active plan match is found
- `create_today_task_candidate`
  - target: active plan id
  - payload: `plan_id`, `title`, `date`, `source`
  - trigger: user asks what to do today / asks for a next step / asks to generate today's task while `plan_context.today_tasks` is empty and active plans exist
- `update_plan_task_status`
  - target: today's task id
  - payload status: `done`, `skipped`, or `blocked`
  - trigger: user says today's task is completed/skipped/blocked and `plan_context.today_tasks` is non-empty

Rules:

- Must not execute actions.
- Must not write files.
- Does not call external models.
- Rule-based in the first version for deterministic tests.
- Should hand `suggested_action` to Permission Engine before Action Executor execution.

### Permission Engine

Status: implemented.

Purpose: evaluate suggested action shapes and decide whether user confirmation is required.

Product role: keep memory/plan/progress actions safe and explainable before the Action Executor can mutate local files.

Public functions:

```python
load_permission_mode(data_dir: str | Path = "data") -> str
evaluate_action(
    action: dict | None,
    permission_mode: str = "ask_first",
) -> dict
```

Inputs:

- `action`: suggested action dict, or `None` for answer-only/no action.
- `permission_mode`: one of `ask_first`, `default`, `trusted`, `full_access`.
- `data_dir`: used only by `load_permission_mode()` to read `settings.yaml`.

Outputs:

```json
{
  "ok": true,
  "permission_mode": "ask_first",
  "action_kind": "update_plan_task_status",
  "risk_level": "medium",
  "requires_confirmation": true,
  "allowed_without_confirmation": false,
  "reason": "...",
  "hard_block": false
}
```

Known action risk rules:

- `save_memory_candidate`: `medium`, reason text says it would write long-term memory if executed later.
- `create_plan_candidate`: `medium`, reason text says it would create or update a long-term plan if executed later.
- `create_today_task_candidate`: `medium`, reason text says it would write one today's minimal task from a long-term plan if executed later.
- `update_plan_task_status`: `medium`, reason text says it would update plan task/progress if executed later.
- no action / `answer_only`: `low`, no confirmation required.
- unknown action kind: `high`, confirmation required.
- critical future actions: `critical`, confirmation required.

Critical future action kinds:

- `delete_files`
- `expose_secret`
- `payment`
- `system_settings`
- `send_external_message`
- `run_shell_command`

Hard-blocked in MVP:

- `delete_files`
- `expose_secret`
- `payment`
- `system_settings`

Permission mode behavior:

- `ask_first`: medium/high/critical actions require confirmation; low actions do not.
- `default`: low actions can run without confirmation; medium/high/critical require confirmation.
- `trusted`: known medium MVP actions can run without confirmation; high/critical require confirmation.
- `full_access`: known low/medium/high actions can run without confirmation; critical and unknown actions still require confirmation.
- invalid mode: falls back to `ask_first`.

Rules:

- Read-only.
- Does not execute actions.
- Does not write memory, plan, audit log, or project files.
- Does not trust `risk_level` or `requires_confirmation` supplied by Suggestion Engine; it recalculates risk from `action.kind`.
- Critical actions always require confirmation.
- Unknown actions default to high risk and require confirmation.

HTTP APIs:

- `POST /api/permission/evaluate`
- `POST /api/suggest/with-permission`

Used by:

- Debug API / Module Debug Console
- Suggestion flow
- Action Executor

### Audit Log

Status: implemented.

Purpose: provide one append-only trace for proposed, evaluated, confirmed, canceled, executed, and failed actions.

Product role: make the local demo trustworthy and inspectable while keeping raw JSON secondary to the user workflow.

Public functions:

```python
append_audit_event(
    event: dict,
    data_dir: str | Path = "data",
) -> dict

read_audit_events(
    data_dir: str | Path = "data",
    limit: int = 50,
    event_type: str | None = None,
    action_id: str | None = None,
) -> list[dict]

build_audit_summary(
    data_dir: str | Path = "data",
    limit: int = 20,
) -> dict

redact_sensitive(value: Any) -> Any
```

Data file:

- `data/audit_log.jsonl`

Event types:

- `suggestion_generated`
- `permission_evaluated`
- `action_confirmed`
- `action_canceled`
- `action_executed`
- `action_failed`
- `memory_written`
- `plan_updated`
- `settings_updated`
- `demo_seed_reset`

Statuses:

- `success`
- `failed`
- `canceled`
- `pending`

Behavior:

- `append_audit_event(...)` creates `audit_log.jsonl` if missing.
- `append_audit_event(...)` adds `id` and `created_at` when missing.
- `read_audit_events(...)` returns newest events first and returns `[]` when the audit file is missing.
- `read_audit_events(...)` can filter by `event_type` and `action_id`.
- malformed JSONL lines do not crash reading; the loader reuses Memory Store JSONL behavior.
- payloads are converted to JSON-safe values before writing.

Redaction:

- recursively handles dicts, lists, and tuples.
- redacts values whose key contains:
  - `api_key`
  - `token`
  - `password`
  - `secret`
  - `authorization`
- replacement value: `[redacted]`.

Side effects:

- Writes only `data/audit_log.jsonl`.
- Does not execute actions.
- Does not write memory, plan, settings, project, or OpenClaw files.

HTTP APIs:

- `GET /api/audit/events`
- `POST /api/audit/events`
- `GET /api/audit/summary`

Current integrations:

- `POST /api/permission/evaluate` appends `permission_evaluated`.
- `POST /api/suggest/with-permission` appends `permission_evaluated`.
- Ask/model requests are not logged by default to avoid noisy logs.

Used by:

- Debug API / Module Debug Console
- Permission flow
- Action Executor

### Action Executor

Status: implemented.

Purpose: execute a very small allowlist of confirmed local actions and audit every outcome.

Product role: mutate only local memory, plan, and progress artifacts that support the growth panel loop.

Public functions:

```python
execute_confirmed_action(
    action: dict,
    permission_decision: dict,
    confirmed: bool,
    data_dir: str | Path = "data",
) -> dict

cancel_action(
    action: dict,
    permission_decision: dict | None = None,
    data_dir: str | Path = "data",
) -> dict
```

Supported action kinds:

- `update_plan_task_status`
- `create_plan_candidate`
- `create_today_task_candidate`
- `save_memory_candidate`

Unsupported action kinds:

- fail without execution
- append `action_failed`

Rules:

- Only executes actions that have passed confirmation.
- Does not call OpenClaw.
- Does not run shell commands.
- Does not delete files.
- Does not send external messages.
- Does not modify system settings.
- All execution outcomes append audit log entries.
- Must not bypass Permission Engine.
- `POST /api/actions/confirm` evaluates permission when no decision is supplied.
- `update_plan_task_status` uses Plan Store `update_task_status(...)`.

Execution behavior:

- `confirmed=False`: no target mutation; appends `action_canceled`; returns status `canceled`.
- `permission_decision.hard_block=True`: no target mutation; appends `action_failed`; returns status `failed`.
- unknown/unsupported kind: no target mutation; appends `action_failed`; returns status `failed`.
- success: appends `action_confirmed` before execution and `action_executed` after execution.
- failure after confirmation: appends `action_confirmed` then `action_failed`.

Action details:

- `update_plan_task_status`
  - target: task id
  - payload: `status`, optional `note`
  - writes via Plan Store to `plan_tasks.jsonl` and `plan_progress.jsonl`
- `create_plan_candidate`
  - target: `plans.yaml`
  - payload: `title`, `goal`, `kind`, `status`, `reminder_mode`, optional tags/stage/cadence
  - appends a new plan and does not overwrite existing plans
- `create_today_task_candidate`
  - target: active plan id, or `payload.plan_id`
  - payload: `plan_id`, `title`, optional `date`, optional `source`
  - appends one `todo` task to `plan_tasks.jsonl`
  - requires non-empty `plan_id` and `title`
- `save_memory_candidate`
  - target: `memories.jsonl` or `decisions.jsonl`
  - payload: `content`, optional `source`, `tags`, `confidence`
  - appends one JSONL record
  - creates `mem_...` or `dec_...` id when missing

Write targets:

- `data/audit_log.jsonl`
- `data/memories.jsonl`
- `data/decisions.jsonl`
- `data/plans.yaml`
- `data/plan_tasks.jsonl`, via Plan Store
- `data/plan_progress.jsonl`, via Plan Store

Audit behavior:

- `action_confirmed` for confirmed calls before execution
- `action_canceled` for canceled calls
- `action_failed` for blocked, unsupported, or failed execution
- `action_executed` for success
- audit payloads are redacted by Audit Log before writing

HTTP APIs:

- `POST /api/actions/confirm`
- `POST /api/actions/cancel`

### OpenClaw Adapter

Status: future.

Draft interface:

```python
list_tools() -> list[dict]
execute_tool(tool_name: str, input: dict) -> dict
check_status(task_id: str) -> dict
```

Rules:

- No deep OpenClaw integration in current MVP.
- Should remain adapter-based.

### Voice Module

Status: future.

Draft responsibilities:

- Push-to-talk input
- STT
- optional TTS

Rules:

- Should call Ask/Suggestion APIs rather than bypassing backend modules.
- No always-listening behavior in MVP.

### Sync / Account

Status: future.

Draft modes:

- `local_only`
- `local_first_encrypted_sync`
- `cloud_sync`
- `self_hosted_sync`

Rules:

- Current MVP is local-only.
- No cloud sync/account system is implemented.

## Data File Ownership

| File | Owner module | Read by | Written by |
| --- | --- | --- | --- |
| `data/profile.yaml` | Memory Store | Memory Store, Context Builder via Memory Store | none |
| `data/goals.yaml` | Memory Store | Memory Store, Context Builder via Memory Store | none |
| `data/projects.yaml` | Memory Store | Memory Store, Context Builder via Memory Store | none |
| `data/constraints.yaml` | Memory Store | Memory Store, Context Builder via Memory Store | none |
| `data/settings.yaml` | Memory Store / Model Gateway / Permission config | Memory Store, Model Gateway, Permission Engine, Debug API | none |
| `data/decisions.jsonl` | Memory Store | Memory Store, Context Builder via Memory Store | Action Executor for `save_memory_candidate` |
| `data/memories.jsonl` | Memory Store | Memory Store, Context Builder via Memory Store | Action Executor for `save_memory_candidate` |
| `data/plans.yaml` | Plan Store | Plan Store, Context Builder via Plan Store | Action Executor for `create_plan_candidate` |
| `data/plan_tasks.jsonl` | Plan Store | Plan Store, Context Builder via Plan Store, Demo Seed Reset Helper | `create_plan_task`, `update_task_status`; Action Executor via Plan Store; Demo Seed Reset Helper for demo-only today-task reset |
| `data/plan_progress.jsonl` | Plan Store | Plan Store, Context Builder via Plan Store | `update_task_status`, `append_plan_progress`; Action Executor via Plan Store |
| `data/reminders.yaml` | Plan Store | Plan Store | none currently |
| `data/demo_reset_archive/*.jsonl` | Demo Seed Reset Helper | manual inspection only | Demo Seed Reset Helper |
| `data/audit_log.jsonl` | Audit Log | Audit Log, Debug API, Action Executor | `append_audit_event`; Demo Seed Reset Helper via Audit Log |

## Current Test Coverage

Current tests cover:

- Context Builder loading, relevance, markdown cap, sources, JSON serialization.
- Plan Store loading, today's tasks, missing files, plan context, Context Builder plan section.
- Model Gateway config loading, live-mode missing API key error, mock response, message construction.
- Ask API model config redaction, model test endpoint, ask endpoint, real Model Gateway debug tab.
- Suggestion Engine answer_only, memory candidate, plan candidate, today task candidate, task status candidates, read-only behavior.
- Suggestion API endpoint and real Suggestion Engine debug tab.
- Permission Engine low/medium/high/critical risk classification, permission modes, settings fallback.
- Permission API endpoint, suggest-with-permission endpoint, and real Permission Engine debug tab.
- Audit Log append/read/filter behavior, recursive redaction, API endpoints, permission-flow logging, and real Audit Log debug tab.
- Action Executor cancel/fail/success paths, today task creation, plan task updates, plan creation, memory/decision writes, audit redaction, action APIs, and real Action Executor debug tab.
- Demo Seed Reset Helper archiving today's tasks only, preserving older tasks and `plans.yaml`, writing audit events, and no-op behavior when today's task list is already empty.
- App smoke coverage for `/app`, `app.js`, `app.css`, reset-to-empty demo state, suggest-with-permission, confirm execution, refreshed today task list, `action_executed` audit events, and JSON traceability markers. This is Flask/API-level coverage rather than real browser automation.
- Debug API debug page, context build, memory missing files, settings missing, modules list, plan summary, task status update.

## Open Questions / Inconsistencies

- `MVP_PLAN.md` settings example omits current model fields `temperature`, `max_tokens`, and `mode`; `data/settings.yaml` includes them.
- Some test/UI Chinese strings appear as mojibake in PowerShell output. The files are still executable and tests pass, but future UI cleanup should normalize visible Chinese text carefully.
- `plan_tasks.jsonl` seed tasks are dated `2026-05-02`. `list_today_tasks()` uses `date.today()` when no explicit date is passed, so `/app` may show no today's tasks on later dates. This is acceptable for the first demo because the empty state can now request a `create_today_task_candidate` through the normal suggestion/confirmation flow.
- Memory Store currently has no public write API; the Action Executor owns the narrow `save_memory_candidate` append path for now.
- Plan Store currently supports updating task status and appending progress, but not creating/updating plans; the Action Executor owns the narrow `create_plan_candidate` append path for now.
- Action Executor is implemented only for three allowlisted local actions; project file creation/editing is still future.
