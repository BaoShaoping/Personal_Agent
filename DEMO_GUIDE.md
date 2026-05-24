# Growth Loop Demo Guide

This guide is for the first usable Personal Agent Growth Loop demo freeze.

The demo path is deliberately small:

```text
long-term plan -> today's minimal task -> confirm execution -> today's task -> audit record
```

## Pre-Demo Rehearsal Checklist

Run the reset helper from the repository root:

```powershell
cd C:\Users\STAR\Desktop\Personal_Agent
C:\Users\STAR\.conda\envs\py39\python.exe scripts\reset_demo_seed.py
```

Run the automated test suite:

```powershell
C:\Users\STAR\.conda\envs\py39\python.exe -m pytest
```

Start Flask with the project Python:

```powershell
cd C:\Users\STAR\Desktop\Personal_Agent\backend
C:\Users\STAR\.conda\envs\py39\python.exe -m flask --app personal_agent.api run --debug --port 5000
```

Open:

```text
http://127.0.0.1:5000/app
```

Manually confirm:

- active long-term plans are visible
- today's task list starts empty
- `生成今日最小任务` works
- the suggestion card appears
- `确认执行` works
- today's task count and task list refresh
- recent audit records show `action_executed`
- `查看 JSON` expands cleanly
- narrow/mobile width remains usable
- Chinese copy displays correctly

After rehearsal, check local git status:

```powershell
cd C:\Users\STAR\Desktop\Personal_Agent
git status --short
```

Runtime data changes such as `data\*.jsonl` and `data\demo_reset_archive\` are ignored by `.gitignore` and should not be committed.

## 1. Start The Service

Before a presentation, reset the demo seed data so today's task list starts empty:

```powershell
cd C:\Users\STAR\Desktop\Personal_Agent
C:\Users\STAR\.conda\envs\py39\python.exe scripts\reset_demo_seed.py
```

The helper only moves tasks dated today out of `data\plan_tasks.jsonl`.
It keeps `data\plans.yaml` unchanged, archives moved tasks under `data\demo_reset_archive\`, and appends a `demo_seed_reset` audit event when it moves anything.

```powershell
cd C:\Users\STAR\Desktop\Personal_Agent\backend
C:\Users\STAR\.conda\envs\py39\python.exe -m flask --app personal_agent.api run --debug --port 5000
```

Open:

```text
http://127.0.0.1:5000/app
```

`/app` is the user-facing demo interface. `/debug` is only for development inspection.

## 2. Open `/app`

Check that the first screen shows:

- active long-term plans
- today's task count
- today's task section
- recent progress
- recent audit records

If today's task list is empty, that is the intended starting point for the freeze demo.

## 3. Generate Today's Minimal Task

When today's task list is empty, click:

```text
生成今日最小任务
```

Expected result:

- the conversation sends a request to generate one small task from the active long-term plan
- a suggestion card appears
- the card explains the proposed action and permission decision
- the action is still pending and needs confirmation

## 4. Confirm Execution

Click:

```text
确认执行
```

Expected result:

- the success state clearly says the action has been executed
- today's task count refreshes to `1`
- the today's task list now shows the newly created task
- the task receives a short visual highlight after refresh

## 5. Check Audit Records

In the recent records panel, confirm that a new audit event appears:

```text
action_executed
```

The normal trace may also include `permission_evaluated` and `action_confirmed`.

## 6. Expand JSON

Expand `查看 JSON` on the suggestion card or an audit record.

Expected result:

- raw action, permission, and audit details are visible
- JSON stays visually secondary while collapsed
- the page layout remains usable when JSON is open

## 7. Optional Narrow-Screen Check

Resize the browser to a narrow mobile-like width.

Expected result:

- the panels stack cleanly
- the prompt area remains usable
- task and audit cards do not overflow horizontally
- JSON remains scrollable instead of breaking layout
