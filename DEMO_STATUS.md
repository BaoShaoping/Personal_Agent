# Demo Status

## Current Stage

Growth Loop demo freeze.

The first usable demo is established. The current goal is stability and presentation polish, not feature expansion.

## Verified Link

The verified user-facing path is:

```text
/app -> generate today's minimal task -> suggestion card -> confirm execution -> today's task refresh -> Audit action_executed -> expand JSON
```

The current core loop is:

```text
long-term plan -> today's minimal task -> confirm execution -> today's task -> audit record
```

## Known Limits

- `/app` is the main demo surface; `/debug` remains a development console.
- The demo creates a minimal task from existing active plans only.
- Demo repeatability now has a local seed reset helper: run `C:\Users\STAR\.conda\envs\py39\python.exe scripts\reset_demo_seed.py` from the repo root before presenting to archive tasks dated today and start with an empty today task list.
- The freeze path now has a Flask/API-level app smoke test covering `/app`, static assets, reset-to-empty state, suggestion, confirmation, task refresh, audit `action_executed`, and JSON traceability markers. It is not a real browser automation test.
- `/app` visible Chinese copy has been polished in UTF-8 source files; remaining encoding risk is mostly terminal/display-tool rendering, not the app files themselves.
- Actions still require explicit confirmation in `ask_first` mode.
- Audit JSON is for traceability, not for everyday user reading.
- The project does not yet include OpenClaw integration, desktop packaging, voice, sync, or generic Todo management.
- The action schema and backend core loop are intentionally unchanged during this freeze.

## Candidate Next Directions

- Run a short demo rehearsal from reset to confirm in a real browser.
- Add true browser automation only if a stable browser dependency is already available and the demo needs layout/click regression coverage.
- Decide whether the next milestone is deeper Growth Loop behavior or packaging/presentation work.
