# Personal Agent MVP Plan

## 1. Product Goal

Build a local-first personal growth system panel centered on long-term plans, daily status, growth progress, and confirmable next-step suggestions.

The MVP should prove one core idea:

> A personal AI becomes meaningfully useful when it helps the user keep long-term plans visible, continue growth work across days, and turn context-aware suggestions into safe local actions only after confirmation.

This project is not trying to replace Doubao, ChatGPT, Claude, Codex, or OpenClaw. Codex and OpenClaw are closer to general agent/runtime tools. Personal Agent should stay focused on long-term self-progression, growth management, local memory, and transparent user-confirmed actions.

The user value center is:

- Long-term Plan / Growth System Panel
- Today's status and tasks
- Growth progress and recent records
- Context-aware conversation and next-step suggestions

Suggestion, Permission, Action Executor, and Audit Log are support capabilities. They are important because they make the growth loop safe and traceable, but they are not the product's primary identity.

## 2. T-Shaped Workflow

### Horizontal View

The full product may eventually include:

- Desktop floating window
- Voice interaction
- Personal context memory
- Long-term plans / growth system panel
- Proactive suggestions
- Confirm/cancel action cards
- Permission modes
- Model provider switching
- OpenClaw adapter, if it clearly supports the growth loop later
- Local deployment
- Mobile app
- Account sync
- End-to-end encrypted sync

### Vertical MVP Path

The first usable version should only deeply implement this path:

```text
User opens /app
  -> sees today's status, active long-term plans, and recent progress
  -> asks a question or requests help
  -> system loads personal context and active long-term plans
  -> model/suggestion flow returns a personalized answer or suggested action
  -> UI shows an answer-only response or a confirm/cancel suggestion card
  -> user confirms or cancels
  -> system executes or skips the allowlisted local action
  -> system writes an audit record, and when confirmed may write memory/plan/task/progress
```

If this flow works well, the product direction is validated.

## 3. MVP Non-Goals

The MVP will not include:

- Full mobile app
- Cloud account system
- Cloud sync
- Wake word / always-listening voice assistant
- Deep OpenClaw source-code fork
- Complex autonomous task planning
- Strong habit-app style supervision
- Full plugin marketplace
- Enterprise admin console
- Payment or monetization system
- Large-scale vector database

These can be considered only after the local growth-panel demo is clearly useful.

## 4. Module-Level Architecture

```text
User App (`/app`)
  -> Backend API
    -> Context Layer
    -> Memory Store
    -> Long-term Plan Module
    -> Model Gateway
    -> Suggestion Engine
    -> Permission Engine
    -> Action Executor
    -> OpenClaw Adapter
    -> Audit Log
```

## 5. Core Modules

### 5.1 User App / Growth Panel UI Module

Purpose:

- Provide the user-facing local growth system panel.
- Make today's state, long-term plans, progress, conversation, suggestions, and audit records understandable in one place.
- Keep `/debug` as a developer console, not the user main interface.

Current demo features:

- `/app` local web app
- Today's status summary
- Active long-term plan cards
- Empty today's task state with `生成今日最小任务`
- Recent progress cards
- Recent audit records
- Text input
- Agent response area
- Suggested action card
- Confirm/cancel buttons
- Expandable raw JSON for traceability

MVP/future UI features:

- Floating desktop button
- Expandable compact chat panel
- Reminder on/off control
- Basic settings entry

Future features:

- Voice input
- TTS response
- Screenshot/context capture
- Quiet mode / proactive mode
- Mobile companion

Recommended stack:

- Current local demo: Flask static HTML/CSS/JS served at `/app`
- Future desktop packaging: Electron + React or Tauri after the local product loop is validated
- Later evaluate Tauri if app size and performance become important

### 5.2 Backend API Module

Purpose:

- Serve as the local control center for context, model calls, memory, permissions, and actions.

Current/demo features:

- Local HTTP API
- `GET /app`
- `GET /debug`
- `POST /api/ask`
- `POST /api/suggest`
- `POST /api/suggest/with-permission`
- `GET /api/plans/summary`
- `POST /api/plans/tasks/status`
- `POST /api/plans/progress`
- `POST /api/actions/confirm`
- `POST /api/actions/cancel`
- `GET /api/audit/summary`
- `GET /api/settings`

Recommended stack:

- Current backend: Python Flask
- Local file-based storage
- Use the `py39` virtual environment for Python commands:
  - Python executable: `C:\Users\STAR\.conda\envs\py39\python.exe`
  - Prefer explicit invocation, for example:
    - `C:\Users\STAR\.conda\envs\py39\python.exe -m pytest`
    - `cd C:\Users\STAR\Desktop\Personal_Agent\backend`
    - `C:\Users\STAR\.conda\envs\py39\python.exe -m flask --app personal_agent.api run --debug --port 5000`

### 5.3 Personal Context Layer

Purpose:

- Build the context pack injected into model calls.
- Make the agent answer based on the user's actual background.

MVP context sources:

- `data/profile.yaml`
- `data/goals.yaml`
- `data/projects.yaml`
- `data/plans.yaml`
- `data/plan_tasks.jsonl`
- `data/plan_progress.jsonl`
- `data/constraints.yaml`
- `data/decisions.jsonl`
- `data/memories.jsonl`
- Current user message

MVP responsibilities:

- Load structured user context
- Load active long-term plans and recent progress
- Select relevant memories
- Compress context into a prompt-ready context pack
- Keep context short enough for model calls

Example known context:

- User is exploring Personal Context Agent.
- User is interested in AI + technical project practice.
- User is currently not suited to directly enter generic AI training.
- User wants desktop floating window, voice, proactive suggestion, confirm/cancel interaction, OpenClaw integration, model switching, local deployment, and future mobile sync.
- User is concerned about privacy, execution permissions, and being marginalized in big-company collaboration.
- User wants long-term plans to feel like a practical "system panel": main quests, side quests, progress bars, daily tasks, and optional reminders.

### 5.4 Memory Store Module

Purpose:

- Store long-term user context in transparent local files.

MVP files:

```text
data/
  profile.yaml
  goals.yaml
  projects.yaml
  plans.yaml
  plan_tasks.jsonl
  plan_progress.jsonl
  reminders.yaml
  constraints.yaml
  decisions.jsonl
  memories.jsonl
  settings.yaml
  audit_log.jsonl
```

Memory types:

- `profile`
- `goal`
- `project`
- `constraint`
- `decision`
- `preference`
- `risk`
- `task`
- `plan`
- `plan_task`
- `plan_progress`

Example memory:

```json
{
  "id": "mem_20260430_001",
  "created_at": "2026-04-30T00:00:00+08:00",
  "type": "decision",
  "content": "The user is currently not suited to directly enter generic AI training, but can explore AI + technical project practice.",
  "source": "conversation",
  "confidence": 0.86,
  "tags": ["AI training", "career direction", "technical projects"]
}
```

MVP rule:

- The system may propose new memories automatically.
- The user should confirm before important memories are written.

### 5.5 Long-term Plan / System Panel Module

Purpose:

- Track long-term personal plans as a first-class context type.
- Make long-term goals visible through a "system panel" style view: main plans, side plans, progress bars, daily tasks, and optional reminders.
- Help the user continue a plan without turning the product into a strict habit-tracking app.
- Serve as the primary user value center of the product. Other modules should support this loop instead of pulling the product toward a generic agent runtime.

Product principle:

- The module should feel like a practical version of the "system" in online novels: it shows current status, quests, progress, and next actions.
- It should not pressure the user with strong supervision by default.
- Reminders must be configurable and easy to turn off.

MVP features:

- Create and edit one or more long-term plans.
- Mark a plan as `main` or `side`.
- Show plan progress as a percentage and progress bar.
- Show expandable daily/weekly task lists.
- Record task status: `todo`, `done`, `skipped`, `blocked`.
- Record progress notes and lightweight reflections.
- Generate one small today's task from an active long-term plan through a confirmable suggestion card.
- Support reminder modes:
  - `off`: no reminders
  - `passive`: only mention relevant plans during chat/context responses
  - `daily`: one daily reminder at a user-selected time
- Include active plans and recent progress in the context pack.

MVP non-goals:

- No complex autonomous scheduling.
- No gamified economy, points store, or achievement system.
- No strict punishment or pressure-based accountability.
- No calendar sync in the first version.

MVP files:

```text
data/
  plans.yaml
  plan_tasks.jsonl
  plan_progress.jsonl
  reminders.yaml
```

Example plan:

```yaml
plans:
  - id: plan_english_001
    title: Improve English ability
    kind: main
    status: active
    goal: Build enough English ability to read AI documents and express project ideas.
    progress_percent: 12
    reminder_mode: passive
    cadence: daily
    current_stage: Build vocabulary and short expression habit.
    tags: ["English", "career growth", "knowledge work"]
```

Example daily task:

```json
{
  "id": "task_20260502_001",
  "plan_id": "plan_english_001",
  "date": "2026-05-02",
  "title": "Review 10 English words and write 3 short sentences",
  "status": "todo",
  "source": "plan"
}
```

Suggested UI shape:

- A plan card in the desktop panel.
- A progress bar near the plan title.
- A collapsible "today's tasks" list.
- A reminder toggle on the plan card.
- A compact history area showing recent progress and skipped/blocked reasons.
- A natural empty state when no seed task is dated today; active plans and progress should still show the user what can be advanced next.

Interfaces:

```text
list_plans()
get_plan(plan_id)
create_or_update_plan(plan)
list_today_tasks(plan_id)
create_plan_task(task)
update_task_status(task_id, status, note)
append_plan_progress(progress_entry)
build_plan_context(user_message)
```

### 5.6 Model Gateway Module

Purpose:

- Allow the app to call different LLM providers through one interface.

MVP features:

- OpenAI-compatible API interface
- Configurable base URL
- Configurable API key
- Configurable model name
- One default cloud model
- One local model endpoint option

Future providers:

- OpenAI / GPT
- Anthropic / Claude
- Google / Gemini
- DeepSeek
- Kimi
- Doubao / Volcano Engine
- Ollama
- LM Studio
- vLLM
- Self-hosted OpenAI-compatible APIs

Interface:

```text
generate_response(messages, model_config)
generate_structured_output(messages, schema, model_config)
```

### 5.7 Suggestion Engine Module

Purpose:

- Decide when to respond normally and when to propose a concrete next action.
- Support the growth panel by turning long-term-plan, memory, and progress context into a clear next-step suggestion when appropriate.

MVP behavior:

- Given user input and context, generate either:
  - `answer_only`
  - `suggested_action`

Suggested action shape:

```json
{
  "type": "suggested_action",
  "title": "Create plan candidate",
  "message": "This sounds like a long-term direction. Do you want me to draft a plan candidate for it?",
  "action": {
    "id": "act_20260509_120000_000000",
    "kind": "create_plan_candidate",
    "title": "Create plan candidate",
    "summary": "Draft a long-term plan candidate from the user message.",
    "target": "plans.yaml",
    "payload": {},
    "source": "suggestion_engine",
    "created_at": "2026-05-09T12:00:00+08:00",
    "risk_level": "medium",
    "requires_confirmation": true
  },
  "buttons": ["confirm", "cancel"]
}
```

MVP triggers:

- User explicitly asks for help.
- User discusses a project and a natural next document/action exists.
- User forms a decision that should be saved to memory.
- User asks what to do next and an active long-term plan has pending tasks.
- User asks what to do today, today's tasks are empty, and active long-term plans exist.
- User has skipped or blocked plan tasks and a lightweight adjustment is useful.

Future triggers:

- File activity
- Calendar events
- Repeated topics
- Inactive tasks
- Open app/window context
- Voice command

### 5.8 Permission Engine Module

Purpose:

- Control whether an action needs confirmation.
- Keep the growth loop safe; it is a support layer, not a general automation permission system for arbitrary runtime actions.

Permission modes:

```text
ask_first
default
trusted
full_access
```

MVP modes:

- `ask_first`: all actions require confirmation
- `default`: low-risk actions can run automatically; medium/high/critical actions require confirmation

Risk levels:

```text
low       read local context, summarize memory
medium    write memory, create file, edit project docs
high      run command, call external service, send message
critical  delete files, expose secrets, payment, system settings
```

Hard rule:

- Critical actions always require confirmation, even in `full_access`.

Current MVP implementation note:

- Permission Engine evaluates suggested actions but does not execute them.
- Permission evaluation can append a `permission_evaluated` audit event.

### 5.8.1 Audit Log Foundation

Purpose:

- Keep a transparent append-only record of proposed, evaluated, confirmed, canceled, executed, and failed actions.
- Give the Action Executor one required logging path before any file write happens.
- Make the demo inspectable without making raw JSON the main product surface.

MVP features:

- Append audit events to `data/audit_log.jsonl`.
- Read recent audit events.
- Filter by `event_type` and `action_id`.
- Summarize counts by event type and status.
- Redact sensitive payload keys before writing.

MVP rule:

- Audit Log may write only `data/audit_log.jsonl`.
- It must not execute actions or write memory/plan/project files.

### 5.9 Action Executor Module

Purpose:

- Execute confirmed actions in a controlled way.
- Execute only narrow, allowlisted local actions that support memory, plans, progress, and auditability.

MVP actions:

- Create a markdown file
- Append to memory
- Append to audit log
- Create or update a long-term plan
- Create one today's task from a long-term plan
- Update a plan task status
- Append a plan progress entry
- Generate a project summary

MVP rule:

- All future write operations must append audit events through the Audit Log module before/after execution.

Future actions:

- Edit files
- Run commands
- Open browser
- Send messages
- Create calendar events
- Trigger OpenClaw skills

Action format:

```json
{
  "id": "act_001",
  "kind": "save_memory_candidate",
  "title": "Save memory candidate",
  "summary": "Save user-provided context as a memory candidate.",
  "target": "memories.jsonl",
  "payload": {
    "content": "..."
  },
  "source": "suggestion_engine",
  "created_at": "2026-05-09T12:00:00+08:00",
  "risk_level": "medium",
  "requires_confirmation": true
}
```

### 5.10 OpenClaw Adapter Module

Purpose:

- Connect this project to OpenClaw without tightly coupling to OpenClaw internals.

MVP approach:

- Do not fork OpenClaw at first.
- Create an adapter interface that can later call OpenClaw CLI, API, skill, or file queue.

Interface:

```text
list_tools()
execute_tool(tool_name, input)
check_status(task_id)
```

Future integration options:

- Local HTTP bridge
- OpenClaw skill wrapper
- CLI invocation
- Source-level integration after product validation

### 5.11 Voice Module

Purpose:

- Let the user speak to the assistant.

MVP status:

- Not required in the first coding pass.
- Add after text-based loop works.

Phase 2 features:

- Push-to-talk voice input
- STT to text
- Optional TTS response

Future features:

- Wake word
- Continuous listening
- Voice interruption
- Mobile voice control

### 5.12 Sync and Account Module

Purpose:

- Support PC and mobile continuity later.

MVP status:

- Not included.
- Store everything locally.

Future modes:

```text
local_only
local_first_encrypted_sync
cloud_sync
self_hosted_sync
```

Recommended future default:

- Local-first with end-to-end encrypted sync.

### 5.13 Privacy and Security Module

Purpose:

- Make the product trustworthy from day one.

MVP rules:

- Local files are transparent and user-editable.
- No memory is sent to a model unless included in context pack.
- Secrets are not stored in memories.
- All confirmed actions are logged.
- User can inspect and delete memories.

Future rules:

- Memory redaction
- Secret detection
- End-to-end encrypted sync
- Per-provider data policy display
- Per-tool permission allowlist

## 6. Data Schema Draft

### `data/profile.yaml`

```yaml
identity:
  role_candidates:
    - technical learner
    - AI product explorer
  current_focus: Personal Context Agent

preferences:
  language: zh-CN
  answer_style:
    - direct
    - practical
    - context-aware
```

### `data/goals.yaml`

```yaml
long_term:
  - Build useful AI technical projects.
  - Explore a Personal Context Agent product direction.

near_term:
  - Create an MVP plan.
  - Build a desktop-first prototype.
```

### `data/projects.yaml`

```yaml
projects:
  - id: personal_context_agent
    name: Personal Context Agent
    status: planning
    current_goal: Define MVP and module architecture.
```

### `data/plans.yaml`

```yaml
plans:
  - id: plan_english_001
    title: Improve English ability
    kind: main
    status: active
    goal: Build enough English ability to read AI documents and express project ideas.
    progress_percent: 12
    cadence: daily
    reminder_mode: passive
    current_stage: Build vocabulary and short expression habit.
    tags:
      - English
      - career growth
      - knowledge work
```

### `data/plan_tasks.jsonl`

```json
{"id":"task_20260502_001","plan_id":"plan_english_001","date":"2026-05-02","title":"Review 10 English words and write 3 short sentences","status":"todo","source":"plan"}
```

### `data/plan_progress.jsonl`

```json
{"id":"prog_20260502_001","plan_id":"plan_english_001","created_at":"2026-05-02T00:00:00+08:00","summary":"Started the English improvement plan.","progress_delta":1,"note":"Keep the first daily task small enough to complete."}
```

### `data/reminders.yaml`

```yaml
reminders:
  default_mode: passive
  daily_time: "21:00"
  quiet_hours:
    start: "23:00"
    end: "08:00"
```

### `data/constraints.yaml`

```yaml
constraints:
  - Generic AI training is not suitable as the current main direction.
  - Resources are limited, so the MVP must stay narrow.
  - Privacy and permission control are important.
```

### `data/settings.yaml`

```yaml
permission_mode: ask_first
model:
  provider: openai_compatible
  base_url: ""
  model_name: ""
  api_key_env: PERSONAL_AGENT_API_KEY
storage:
  mode: local_only
runtime:
  python_env_name: py39
  python_executable: "C:\\Users\\STAR\\.conda\\envs\\py39\\python.exe"
```

### Python runtime rule

All backend Python commands should use the `py39` virtual environment explicitly:

```powershell
C:\Users\STAR\.conda\envs\py39\python.exe -m pytest
cd C:\Users\STAR\Desktop\Personal_Agent\backend
C:\Users\STAR\.conda\envs\py39\python.exe -m flask --app personal_agent.api run --debug --port 5000
```

Do not rely on the shell's default `python` unless the active interpreter has been verified to be `C:\Users\STAR\.conda\envs\py39\python.exe`.

## 7. Development Milestones

### Phase 0: Planning

Deliverables:

- `MVP_PLAN.md`
- Initial module boundaries
- First vertical user flow

Status:

- Done.

### Phase 1: Local Backend and Memory Files

Deliverables:

- Flask backend skeleton
- Data directory and seed files
- Memory loader
- Context builder
- Basic tests for context loading

Success criteria:

- Backend can load profile, goals, projects, constraints, and memories.
- Backend can build a context pack.

### Phase 1.5: Module Debug Console

Deliverables:

- Flask local debug service
- `GET /debug`
- `POST /api/context/build`
- `GET /api/memory/summary`
- `GET /api/settings`
- Simple HTML/CSS/JS module debug UI

Success criteria:

- User can visually test Context Builder input and output.
- UI shows `context_markdown`, sources, omitted items, stats, and raw JSON.
- Placeholder tabs exist for Model Gateway, Suggestion Engine, Permission Engine, Action Executor, OpenClaw Adapter, and Long-term Plan / System Panel.

Status:

- Done. `/debug` remains a developer console, not the user product surface.

### Phase 2: Long-term Plan / System Panel

Deliverables:

- `plans.yaml`
- `plan_tasks.jsonl`
- `plan_progress.jsonl`
- `reminders.yaml`
- Plan loader and plan context builder
- Plan progress card in the debug UI
- Expandable daily task checklist
- Reminder mode setting: `off`, `passive`, `daily`

Success criteria:

- User can create or inspect an active long-term plan.
- User can see a progress bar and today's tasks.
- User can update task status and append progress.
- Context Builder can include active plans and recent progress in the context pack.

Status:

- Done for the first local demo. Seed tasks may not be dated today, so the user-facing empty state must stay natural.

### Phase 3: Model Gateway and Ask Flow

Deliverables:

- OpenAI-compatible model gateway
- `/api/ask` endpoint
- Prompt template using context pack
- Basic CLI or API test

Success criteria:

- User asks a question.
- Agent answers with visible awareness of personal context.

Status:

- Done for mock-mode local demo.

### Phase 4: Suggestion and Confirmation Flow

Deliverables:

- Suggestion engine
- Permission engine
- Action schema
- Confirm/cancel endpoints
- Audit log

Success criteria:

- Agent proposes a useful action.
- User confirms.
- System executes one safe local action and logs it.

Status:

- Done for the first allowlisted loop: answer-only, save memory candidate, create plan candidate, create today's task candidate, update plan task status, confirm/cancel, and audit log.

### Phase 5: User-Facing `/app` Demo

Deliverables:

- Flask-served `/app`
- Growth system panel with today's status, long-term plans, recent progress, conversation, suggestion card, and recent audit records
- Confirm/cancel action card
- Natural empty state for no today's tasks, with a button that asks the suggestion loop to generate one minimal task

Success criteria:

- User can complete the vertical MVP path from `/app`.
- The first screen communicates long-term plan / growth system panel, not a debug console.

Status:

- Current demo stage.

### Phase 5.5: Desktop Packaging Later

Deliverables:

- Electron or Tauri wrapper
- Floating button
- Compact chat panel
- Settings view for model and permission mode

Success criteria:

- The validated `/app` loop can be used from a desktop shell.

Status:

- Future. Do not start before the local demo story is clear.

### Phase 6: OpenClaw Adapter

Deliverables:

- Adapter interface
- One placeholder/mock OpenClaw tool
- One real integration path if OpenClaw local interface is available

Success criteria:

- Confirmed action can be routed through the adapter.

### Phase 7: Voice Input

Deliverables:

- Push-to-talk voice input
- STT integration
- Optional TTS

Success criteria:

- User can speak a request and receive a context-aware response.

## 8. First User Stories

### Story 1: Context-Aware Answer

As a user, I ask:

> Am I suited to enter the AI training market now?

The agent should answer based on stored context:

- Generic AI training is not suitable right now.
- AI + technical project practice is more suitable.
- The Personal Context Agent project is the current better direction.

### Story 2: Proactive Document Creation

As a user discussing the project plan, the agent suggests:

> Do you want me to create an MVP_PLAN.md file for this project?

Buttons:

```text
[Confirm] [Cancel]
```

On confirm:

- Create or update `MVP_PLAN.md`
- Write audit log
- Optionally propose a memory update

### Story 3: Memory Confirmation

After a major conclusion, the agent asks:

> Do you want me to save this as a long-term decision memory?

On confirm:

- Append to `decisions.jsonl`

### Story 4: Long-term Plan System Panel

As a user, I say:

> Help me keep improving my English over the next three months.

The agent should propose a long-term plan card:

- Main plan title
- Current stage
- Progress bar
- Today's expandable task list
- Reminder mode toggle: `off`, `passive`, `daily`

On confirm:

- Create or update `plans.yaml`
- Add today's tasks to `plan_tasks.jsonl`
- Log the action

Later, when the user asks:

> What should I do today?

The agent should answer with awareness of the active plan, current progress, and today's pending tasks.

## 9. Risk List

### Scope Creep

Risk:

- The project may expand into Doubao + ChatGPT + OpenClaw + Notion + mobile sync too early.

Mitigation:

- Follow the vertical MVP path.
- Keep mobile, cloud sync, and full OpenClaw fork out of MVP.

### Weak Differentiation

Risk:

- The product may look like another chat UI.

Mitigation:

- Make personal context and proactive suggestion the core.
- Every demo should show how the answer differs from a generic assistant.

### Privacy Risk

Risk:

- Personal memories may be sensitive.

Mitigation:

- Local-first storage.
- Transparent memory files.
- Explicit memory confirmation.
- No hidden cloud sync in MVP.

### Permission Risk

Risk:

- Agent actions may be unsafe if automation becomes too broad.

Mitigation:

- Default to confirmation.
- Risk-level action schema.
- Critical actions always require confirmation.
- Audit every action.

### OpenClaw Coupling Risk

Risk:

- Deeply modifying OpenClaw too early may create maintenance burden.

Mitigation:

- Use adapter pattern first.
- Consider source-level integration only after the MVP is validated.

### Multi-Model Complexity

Risk:

- Supporting too many providers early may slow development.

Mitigation:

- Start with OpenAI-compatible API only.
- Add provider-specific integrations later.

### Plan Feature Scope Creep

Risk:

- Long-term plans may turn the product into a generic habit app, task manager, or gamified productivity system.

Mitigation:

- Keep long-term plans as a personal context feature.
- Focus on visibility, continuity, and optional reminders.
- Avoid strict supervision, punishment mechanics, and complex scheduling in the MVP.

## 10. Immediate Next Steps

1. Use `C:\Users\STAR\.conda\envs\py39\python.exe` for all backend Python commands.
2. Keep `/app` as the user-facing growth system panel and `/debug` as the developer console.
3. Tighten the first demo path documented in `DEMO_GUIDE.md`.
4. Improve wording around answer-only responses so mock mode does not feel like a debug artifact.
5. Keep Suggestion, Permission, Action Executor, and Audit focused on supporting memory/plan/task/progress actions.
6. Defer desktop packaging, OpenClaw, voice, mobile sync, and broad automation until the growth-panel loop is compelling.

## 11. MVP Success Definition

The MVP is successful if:

- The user can open `/app` as a local product demo.
- The first screen clearly communicates today's status, active long-term plans, growth progress, and next-step suggestions.
- The agent can answer with awareness of stored personal context.
- The agent can answer with awareness of active long-term plans and recent progress.
- The user can inspect a plan progress card and expandable daily task checklist.
- If today's task list is empty, the user still sees active long-term plans and a natural explanation.
- If today's task list is empty, the user can generate one minimal task from an active long-term plan after confirmation.
- The user can turn reminders off or choose passive/daily reminders.
- The agent can propose a relevant next action.
- The user can confirm or cancel the action.
- A confirmed action can create/update a local artifact.
- The system logs what happened.
- The user can inspect the memory files.

The MVP does not need to be beautiful or complete. It needs to prove that a local long-term plan / growth system panel makes an AI assistant feel more continuous, useful, and trustworthy.
