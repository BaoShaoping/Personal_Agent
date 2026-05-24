# Personal Agent Product Overview

## Product Positioning

Personal Agent is a local-first personal growth system panel.

It helps a user keep long-term plans connected to a concrete daily action. The current product is intentionally narrow: it is not a generic Todo app, not a broad autonomous agent runtime, not a Codex replacement, and not an OpenClaw replacement.

The core promise is:

```text
long-term plan -> today's minimal task -> confirm execution -> today's task -> audit record
```

## Target User

Personal Agent is designed for a user who is managing long-running personal improvement or project-building work and wants a local secretary-like system that remembers context, proposes a small next step, and records what happened.

The first demo user is a solo builder who wants to:

- keep active long-term plans visible
- reduce daily decision friction
- avoid opaque automation
- confirm actions before local data is changed
- inspect what the system did through audit records

## Main Experience

The main product surface is:

```text
http://127.0.0.1:5000/app
```

The `/app` page acts as a local growth dashboard. It shows active long-term plans, today's status, today's task list, recent progress, a conversation area, confirmable suggestions, and recent audit records.

The intended first-use loop is:

1. The user opens the growth dashboard.
2. The dashboard shows active long-term plans and today's task state.
3. If today's task list is empty, the user asks for one minimal task.
4. Personal Agent proposes a confirmable action.
5. The user confirms execution.
6. The system writes the new task into today's task list.
7. The audit panel records the permission and execution trail.
8. JSON details can be expanded for traceability.

## Current Capabilities

The current demo can:

- load active plans from local files
- show today's task count and active plan count
- generate a minimal task for today from an active long-term plan
- require explicit confirmation before writing the task
- append the confirmed task to today's task list
- show recent progress and audit events
- expand raw JSON details for debugging and trust
- reset demo seed data so a presentation can start from an empty today-task list
- run a Flask/API-level smoke test for the freeze path

## Trust And Safety Model

The product uses an ask-first model for meaningful local writes.

For the current Growth Loop demo, Personal Agent does not silently create tasks. It proposes an action, evaluates permission/risk, waits for confirmation, executes only after confirmation, and writes an audit event.

This keeps the system understandable:

- suggestions are visible before execution
- confirmation is explicit
- local data writes are narrow
- audit records are preserved
- raw action details remain inspectable

## Local-First Data

The current demo stores data locally under:

```text
C:\Users\STAR\Desktop\Personal_Agent\data
```

Important files include:

- `plans.yaml`: active long-term plans
- `plan_tasks.jsonl`: task records
- `plan_progress.jsonl`: progress records
- `audit_log.jsonl`: audit records
- `settings.yaml`: local settings

Runtime JSONL files are intentionally excluded from git so personal/demo activity does not become version-control noise.

## Demo Readiness

The current Growth Loop demo is in freeze / polish.

Verified status:

- seed reset helper is available
- `/app` page and static assets are covered by smoke tests
- core API flow is covered by smoke tests
- visible Chinese copy has been polished
- real-browser visual rehearsal was manually confirmed
- full test suite passes with `93 passed`
- local git baseline is established

The demo should be rehearsed with `DEMO_GUIDE.md` before presentations.

## Non-Goals For The Current Freeze

The current demo intentionally does not include:

- generic Todo management
- broad autonomous automation
- OpenClaw integration
- desktop packaging
- voice input or TTS
- cloud sync or accounts
- action schema expansion
- backend core-loop refactors

These may become future directions only if they support the Growth Loop product direction.

## Near-Term Roadmap

The next product work should remain small unless the demo exposes a concrete issue.

Good next steps:

- run formal demo rehearsals before presentations
- polish copy or layout only where the user-facing demo needs it
- decide whether the next milestone is deeper Growth Loop behavior or packaging/presentation work
- add true browser automation only when a stable browser dependency is available and the value is clear

The product should continue to protect its main differentiator: a calm local system panel that turns long-term direction into today's smallest confirmed action.
