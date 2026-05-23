# Project Record

This file tracks project stages, decisions, validation results, known limits, and next steps.

It is not a detailed implementation changelog. Keep each entry short enough for a new session to read quickly. Put implementation details in code, tests, module docs, or linked files; mention them here only when they affect project direction or handoff.

## How To Use

Add one entry at the end of each meaningful work session.

Each entry should answer:

- What stage is the project in?
- What changed at the product or module level?
- What was verified?
- What decisions were made?
- What is still risky or unclear?
- What should the next session do first?

Recommended entry shape:

```md
## YYYY-MM-DD - Short Stage Name

### Stage
- ...

### Product / Direction
- ...

### Stage Changes
- ...

### Verified
- ...

### Decisions
- ...

### Risks / Open Questions
- ...

### Next
- ...

### Detail Pointers
- `path/to/file`: why it matters
```

## 2026-05-16 - Growth Loop Demo Freeze

### Stage
- First usable Growth Loop demo is established.
- Current project mode is demo freeze / polish, not feature expansion.

### Product / Direction
- Personal Agent is positioned as a local-first personal growth system panel.
- The core loop is:
  `long-term plan -> today's minimal task -> confirm execution -> today's task -> audit record`.
- `/app` is the user-facing growth dashboard.
- `/debug` remains a developer inspection console.

### Stage Changes
- The product direction was narrowed around long-term plans, daily status, growth progress, confirmable suggestions, and transparent audit records.
- The freeze demo was documented and polished for presentation.
- The project explicitly excludes broad autonomous automation, generic Todo management, OpenClaw integration, cloud sync, voice, and desktop packaging during this stage.

### Verified
- The intended demo path is:
  `/app -> generate today's minimal task -> suggestion card -> confirm execution -> today's task refresh -> audit action_executed -> expand JSON`.
- Last known test result from the freeze session:
  `C:\Users\STAR\.conda\envs\py39\python.exe -m pytest`
  reported `90 passed`.
- Flask test client checks for `/app`, `/static/app.js`, and `/static/app.css` returned `200`.

### Decisions
- Use `C:\Users\STAR\.conda\envs\py39\python.exe` explicitly for backend Python commands.
- Keep `/app` and `/debug` separate in product meaning.
- Keep the action schema and backend core loop stable during freeze.
- Treat raw JSON as traceability, not the primary user experience.

### Risks / Open Questions
- Demo repeatability depends on seed data and whether today's task list starts empty.
- Current docs mention future directions but there is not yet a repeatable demo reset workflow.
- Browser-level smoke coverage for the freeze path is still a candidate next step.
- Next milestone is undecided: deeper Growth Loop behavior vs packaging/presentation work.

### Next
- Prefer a small stabilization task before expanding scope.
- Best candidates:
  - Add a browser smoke test for the `/app` freeze path.
  - Add seed-data reset support for repeatable demos.
  - Polish empty-state copy and audit summaries.

### Detail Pointers
- `README.md`: current product/stage overview.
- `DEMO_GUIDE.md`: current demo flow.
- `DEMO_STATUS.md`: current freeze status and known limits.
- `MVP_PLAN.md`: overall blueprint and milestones.
- `MODULE_INTERFACES.md`: module boundaries, APIs, data ownership, and test coverage.

## 2026-05-23 - Demo Seed Reset Helper

### Stage
- Growth Loop demo freeze / polish continues.
- Focus remains demo stability, not expanding into a generic Todo system or agent runtime.

### Product / Direction
- The demo can now be reset to the intended starting state: active long-term plans remain visible while today's task list starts empty.

### Stage Changes
- Added a local demo-only reset helper for tasks dated today.
- Updated demo docs and module ownership notes for the reset path.

### Verified
- `C:\Users\STAR\.conda\envs\py39\python.exe -m pytest` from the repo root reported `92 passed`.

### Decisions
- Preserve `data/plans.yaml` during reset.
- Archive today's removed task records instead of deleting them outright.
- Append a `demo_seed_reset` audit event only when the helper moves records.
- Keep the action schema and backend Growth Loop APIs unchanged.

### Risks / Open Questions
- The helper is intentionally local and demo-only; it is not exposed as a UI or HTTP API.
- Existing UI Chinese mojibake remains a known polish issue outside this reset task.

### Next
- Use the reset helper before demo rehearsals, then verify `/app` still follows the freeze path.

### Detail Pointers
- `backend/personal_agent/demo_seed_reset.py`: demo-only reset behavior.
- `scripts/reset_demo_seed.py`: repo-root Windows-friendly entry point.
- `backend/tests/test_demo_seed_reset.py`: helper behavior coverage.
- `DEMO_GUIDE.md`: pre-demo reset instructions.
- `DEMO_STATUS.md`: repeatability status.
- `MODULE_INTERFACES.md`: data ownership and module boundary notes.

## 2026-05-23 - App Smoke Test

### Stage
- Growth Loop demo freeze / polish continues.
- Focus remains stabilizing the verified demo path.

### Product / Direction
- The `/app` freeze path now has repeatable smoke coverage without adding browser or Node dependencies.

### Stage Changes
- Added an app-level smoke test that combines seed reset, `/app` and static asset checks, suggestion generation, user confirmation, task refresh, audit trace, and JSON traceability markers.
- Updated demo status and module test coverage notes.

### Verified
- `C:\Users\STAR\.conda\envs\py39\python.exe -m pytest backend\tests\test_app_smoke.py` reported `1 passed`.
- `C:\Users\STAR\.conda\envs\py39\python.exe -m pytest` from the repo root reported `93 passed`.

### Decisions
- Use Flask test client plus API flow coverage for the smoke test.
- Avoid new browser automation dependencies during freeze polish.
- Keep action schema and backend Growth Loop behavior unchanged.

### Risks / Open Questions
- This is not true browser automation; it does not click the UI or verify layout/rendering.
- Existing UI Chinese mojibake remains a known polish issue outside this smoke test.

### Next
- Consider true browser smoke only if a stable browser dependency is already available and layout/click regression coverage becomes necessary.

### Detail Pointers
- `backend/tests/test_app_smoke.py`: `/app` Growth Loop freeze-path smoke test.
- `DEMO_STATUS.md`: smoke coverage status.
- `MODULE_INTERFACES.md`: current test coverage notes.
