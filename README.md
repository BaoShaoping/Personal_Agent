# Personal Agent

Personal Agent is a local-first personal growth system panel.

It is focused on long-term plans, daily status, growth progress, confirmable next-step suggestions, and transparent audit records. It is not trying to be a general agent runtime, a Codex replacement, or an OpenClaw replacement.

## Current Stage

The first usable Growth Loop demo is now established and in demo freeze / polish.

The core closed loop is:

```text
long-term plan -> today's minimal task -> confirm execution -> today's task -> audit record
```

The product surface is:

- `/app`: user-facing Growth Loop dashboard and main demo interface
- `/debug`: developer debug console for inspecting modules, raw data, and API behavior

## What The Demo Shows

The current local demo can:

- load active long-term plans from local data files
- show today's task count, active plan count, recent progress, and recent audit records
- generate one small task for today from an active long-term plan
- show the generated task as a confirmable suggestion card
- require the user to confirm before writing the task
- append the confirmed task into today's task list
- write permission/action audit events, including `action_executed`
- keep raw JSON available for inspection without making it the primary UI

This demo is intentionally narrow. The main thing it proves is that the Growth Loop can move from a long-term plan to a concrete task through a user-confirmed action, with traceability.

## Start The Backend

Use the project Python environment explicitly:

```powershell
cd C:\Users\STAR\Desktop\Personal_Agent\backend
C:\Users\STAR\.conda\envs\py39\python.exe -m flask --app personal_agent.api run --debug --port 5000
```

Then open:

```text
http://127.0.0.1:5000/app
```

Open the developer console only when needed:

```text
http://127.0.0.1:5000/debug
```

## Run Tests

From the repository root:

```powershell
cd C:\Users\STAR\Desktop\Personal_Agent
C:\Users\STAR\.conda\envs\py39\python.exe -m pytest
```

## Current Non-Goals

The freeze demo intentionally does not include:

- OpenClaw integration
- desktop packaging
- voice input or TTS
- mobile sync
- cloud account sync
- broad autonomous automation
- generic Todo management
- action schema changes
- backend core-loop refactors
