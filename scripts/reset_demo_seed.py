"""Repo-root entry point for resetting Growth Loop demo seed data."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from personal_agent.demo_seed_reset import main


if __name__ == "__main__":
    raise SystemExit(main())
