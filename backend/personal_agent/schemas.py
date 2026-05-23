"""Data shapes used by the Context Builder MVP.

The project can move to Pydantic later if a FastAPI layer needs runtime
validation. For this first module, dataclasses keep the dependency surface tiny.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceRef:
    """Traceable origin for a context item included in a context pack."""

    source: str
    id: str | None = None
    path: str | None = None
    kind: str | None = None


@dataclass
class ContextPack:
    """Prompt-ready personal context selected for a single user message."""

    user_message: str
    profile_summary: str
    active_goals: list[dict[str, Any]] = field(default_factory=list)
    active_projects: list[dict[str, Any]] = field(default_factory=list)
    active_plans: list[dict[str, Any]] = field(default_factory=list)
    plan_context: dict[str, Any] = field(default_factory=dict)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    relevant_decisions: list[dict[str, Any]] = field(default_factory=list)
    relevant_memories: list[dict[str, Any]] = field(default_factory=list)
    context_markdown: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    omitted: dict[str, Any] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return asdict(self)
