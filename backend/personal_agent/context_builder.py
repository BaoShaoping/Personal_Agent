"""Build small, traceable personal context packs for LLM prompts."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .memory_store import MemoryData, load_memory_data
from .plan_store import build_plan_context
from .schemas import ContextPack


TYPE_WEIGHTS = {
    "decision": 3.0,
    "project": 2.3,
    "goal": 2.0,
    "constraint": 1.9,
    "preference": 1.5,
    "risk": 1.4,
    "task": 1.2,
    "profile": 1.0,
}

STOPWORDS = {
    "the",
    "and",
    "or",
    "to",
    "of",
    "a",
    "an",
    "is",
    "are",
    "for",
    "now",
    "next",
    "what",
    "how",
    "我",
    "我们",
    "现在",
    "下一步",
    "怎么",
    "适合",
    "做",
    "吗",
    "的",
    "了",
    "和",
    "与",
}


def build_context_pack(
    user_message: str,
    data_dir: str = "data",
    max_chars: int = 6000,
    max_memories: int = 8,
) -> ContextPack:
    """Build a compact context pack from local memory files.

    No LLM calls or vector database are used. Relevance comes from simple
    keyword overlap, tag matching, item type weights, and recency.
    """

    data = load_memory_data(data_dir)
    query_terms = extract_terms(user_message)

    profile_summary = summarize_profile(data.profile)
    active_goals = active_goal_items(data.goals)
    active_projects = select_active_projects(data.projects, query_terms)
    plan_context = build_plan_context(user_message, data_dir=data_dir, max_items=max_memories)
    active_plans = plan_context.get("active_plans", [])
    constraints = constraint_items(data.constraints)

    scored_decisions = rank_records(data.decisions, query_terms, preferred_types={"decision"})
    scored_memories = rank_records(data.memories, query_terms)

    relevant_decisions = [item for item, _score in scored_decisions[:max_memories]]
    remaining_slots = max(0, max_memories - len(relevant_decisions))
    relevant_memories = [item for item, _score in scored_memories[:remaining_slots]]

    context_inputs = {
        "user_message": user_message,
        "profile_summary": profile_summary,
        "active_goals": active_goals,
        "active_projects": active_projects,
        "active_plans": active_plans,
        "plan_context": plan_context,
        "constraints": constraints,
        "relevant_decisions": relevant_decisions,
        "relevant_memories": relevant_memories,
    }

    markdown, omitted = render_context_markdown(context_inputs, max_chars=max_chars)
    sources = collect_sources(data, context_inputs)
    stats = {
        "max_chars": max_chars,
        "context_chars": len(markdown),
        "query_terms": sorted(query_terms),
        "loaded": {
            "goals": len(active_goals),
            "projects": len(active_projects),
            "plans": plan_context.get("stats", {}).get("loaded", {}).get("plans", 0),
            "plan_tasks": plan_context.get("stats", {}).get("loaded", {}).get("tasks", 0),
            "plan_progress": plan_context.get("stats", {}).get("loaded", {}).get("progress", 0),
            "constraints": len(constraints),
            "decisions": len(data.decisions),
            "memories": len(data.memories),
        },
        "selected": {
            "plans": plan_context.get("stats", {}).get("selected", {}).get("plans", 0),
            "today_tasks": plan_context.get("stats", {}).get("selected", {}).get("today_tasks", 0),
            "recent_progress": plan_context.get("stats", {}).get("selected", {}).get("recent_progress", 0),
            "decisions": len(relevant_decisions),
            "memories": len(relevant_memories),
        },
        "missing_files": data.missing_files + plan_context.get("missing_files", []),
        "load_errors": data.load_errors + plan_context.get("load_errors", []),
    }

    return ContextPack(
        user_message=user_message,
        profile_summary=profile_summary,
        active_goals=active_goals,
        active_projects=active_projects,
        active_plans=active_plans,
        plan_context=plan_context,
        constraints=constraints,
        relevant_decisions=relevant_decisions,
        relevant_memories=relevant_memories,
        context_markdown=markdown,
        sources=sources,
        omitted=omitted,
        stats=stats,
    )


def extract_terms(text: str) -> set[str]:
    """Extract mixed Chinese/English keywords without external NLP deps."""

    lowered = text.lower()
    terms = {
        token
        for token in re.findall(r"[a-z0-9_+\-]{2,}|[\u4e00-\u9fff]{2,}", lowered)
        if token not in STOPWORDS
    }

    # Add useful CJK bigrams so short Chinese queries can match longer content.
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", lowered):
        terms.update(chunk[i : i + 2] for i in range(0, max(0, len(chunk) - 1)))

    return {term for term in terms if term and term not in STOPWORDS}


def summarize_profile(profile: dict[str, Any]) -> str:
    if not profile:
        return ""

    parts: list[str] = []
    identity = profile.get("identity", {})
    preferences = profile.get("preferences", {})

    if isinstance(identity, dict):
        current_focus = identity.get("current_focus")
        role_candidates = _ensure_list(identity.get("role_candidates"))
        if current_focus:
            parts.append(f"Current focus: {current_focus}")
        if role_candidates:
            parts.append("Role candidates: " + ", ".join(map(str, role_candidates)))

    if isinstance(preferences, dict):
        language = preferences.get("language")
        answer_style = _ensure_list(preferences.get("answer_style"))
        if language:
            parts.append(f"Preferred language: {language}")
        if answer_style:
            parts.append("Answer style: " + ", ".join(map(str, answer_style)))

    if parts:
        return "; ".join(parts)
    return _compact_text(profile)


def active_goal_items(goals: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for section in ("near_term", "long_term"):
        for index, goal in enumerate(_ensure_list(goals.get(section))):
            items.append(
                {
                    "id": f"goal_{section}_{index + 1}",
                    "type": "goal",
                    "timeframe": section,
                    "content": _compact_text(goal),
                    "source": "goals.yaml",
                }
            )
    return items


def select_active_projects(projects: dict[str, Any], query_terms: set[str]) -> list[dict[str, Any]]:
    records = [_normalize_record(project, "project", "projects.yaml") for project in _ensure_list(projects.get("projects"))]
    ranked = rank_records(records, query_terms, preferred_types={"project"})
    if ranked:
        return [record for record, _score in ranked[:3]]
    return records[:3]


def constraint_items(constraints: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, constraint in enumerate(_ensure_list(constraints.get("constraints"))):
        items.append(
            {
                "id": f"constraint_{index + 1}",
                "type": "constraint",
                "content": _compact_text(constraint),
                "source": "constraints.yaml",
            }
        )
    return items


def rank_records(
    records: list[dict[str, Any]],
    query_terms: set[str],
    preferred_types: set[str] | None = None,
) -> list[tuple[dict[str, Any], float]]:
    scored: list[tuple[dict[str, Any], float]] = []
    for index, raw_record in enumerate(records):
        record = _normalize_record(raw_record, raw_record.get("type", "memory"), raw_record.get("source", "local_file"))
        score = score_record(record, query_terms, preferred_types=preferred_types)
        if score > 0:
            record.setdefault("id", f"record_{index + 1}")
            scored.append((record, score))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def score_record(
    record: dict[str, Any],
    query_terms: set[str],
    preferred_types: set[str] | None = None,
) -> float:
    record_type = str(record.get("type", "memory"))
    content = _record_search_text(record)
    record_terms = extract_terms(content)
    tags = {str(tag).lower() for tag in _ensure_list(record.get("tags"))}

    keyword_overlap = len(query_terms & record_terms)
    tag_overlap = sum(1 for term in query_terms if any(term in tag or tag in term for tag in tags))
    fuzzy_overlap = sum(1 for term in query_terms if term in content.lower())

    score = keyword_overlap * 2.0 + tag_overlap * 3.0 + fuzzy_overlap * 0.5
    score += TYPE_WEIGHTS.get(record_type, 1.0)
    if preferred_types and record_type in preferred_types:
        score += 1.5
    score += recency_weight(record.get("created_at") or record.get("updated_at"))
    score += float(record.get("confidence", 0) or 0) * 0.4

    return score


def recency_weight(timestamp: Any) -> float:
    if not timestamp:
        return 0.0
    try:
        created = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    age_days = max(0, (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).days)
    if age_days <= 7:
        return 1.2
    if age_days <= 30:
        return 0.8
    if age_days <= 180:
        return 0.4
    return 0.1


def render_context_markdown(context: dict[str, Any], max_chars: int) -> tuple[str, dict[str, Any]]:
    sections = [
        ("User Message", [context["user_message"]]),
        ("Profile", [context["profile_summary"]] if context["profile_summary"] else []),
        ("Active Goals", _format_items(context["active_goals"])),
        ("Active Projects", _format_items(context["active_projects"])),
        ("Active Long-term Plans", _format_plan_context(context["plan_context"])),
        ("Constraints", _format_items(context["constraints"])),
        ("Relevant Decisions", _format_items(context["relevant_decisions"])),
        ("Relevant Memories", _format_items(context["relevant_memories"])),
    ]

    included: list[str] = ["# Personal Context Pack"]
    omitted: dict[str, Any] = {"sections": [], "items": 0, "truncated": False}

    for title, lines in sections:
        if not lines:
            continue
        header = f"\n## {title}"
        section_added = False
        for item_line in (f"- {line}" for line in lines):
            candidate_lines = included + ([header] if not section_added else []) + [item_line]
            candidate = "\n".join(candidate_lines)
            if len(candidate) > max_chars:
                if not section_added and title not in omitted["sections"]:
                    omitted["sections"].append(title)
                omitted["items"] += 1
                omitted["truncated"] = True
                continue
            if not section_added:
                included.append(header)
                section_added = True
            included.append(item_line)

    markdown = "\n".join(included).strip()
    if len(markdown) > max_chars:
        omitted["truncated"] = True
        markdown = markdown[: max(0, max_chars - 24)].rstrip() + "\n\n[context truncated]"
    return markdown, omitted


def collect_sources(data: MemoryData, context: dict[str, Any]) -> list[dict[str, Any]]:
    sources_by_key: dict[tuple[str, str | None], dict[str, Any]] = {}

    static_sources = [
        ("profile.yaml", "profile", context["profile_summary"]),
        ("goals.yaml", "goal", context["active_goals"]),
        ("projects.yaml", "project", context["active_projects"]),
        ("constraints.yaml", "constraint", context["constraints"]),
    ]
    for filename, kind, value in static_sources:
        if value:
            path = str(Path(data.data_dir) / filename)
            sources_by_key[(filename, None)] = {"source": filename, "id": None, "path": path, "kind": kind}

    for key, filename, kind in (
        ("relevant_decisions", "decisions.jsonl", "decision"),
        ("relevant_memories", "memories.jsonl", "memory"),
    ):
        for item in context[key]:
            source = str(item.get("source") or filename)
            item_id = str(item.get("id")) if item.get("id") is not None else None
            sources_by_key[(source, item_id)] = {
                "source": source,
                "id": item_id,
                "path": str(Path(data.data_dir) / filename),
                "kind": str(item.get("type") or kind),
            }

    for source in context.get("plan_context", {}).get("sources", []):
        source_name = str(source.get("source") or "")
        item_id = str(source.get("id")) if source.get("id") is not None else None
        sources_by_key[(source_name, item_id)] = {
            "source": source_name,
            "id": item_id,
            "path": source.get("path"),
            "kind": source.get("kind"),
        }

    return list(sources_by_key.values())


def _format_items(items: list[dict[str, Any]]) -> list[str]:
    formatted: list[str] = []
    for item in items:
        content = _compact_text(item.get("content") or item.get("name") or item)
        source = item.get("source")
        item_id = item.get("id")
        trace = ", ".join(part for part in (str(source) if source else "", str(item_id) if item_id else "") if part)
        formatted.append(f"{content} [{trace}]" if trace else content)
    return formatted


def _format_plan_context(plan_context: dict[str, Any]) -> list[str]:
    formatted: list[str] = []
    for plan in plan_context.get("active_plans", []):
        title = plan.get("title") or plan.get("id")
        kind = plan.get("kind", "side")
        progress = plan.get("progress_percent", 0)
        stage = plan.get("current_stage") or ""
        goal = plan.get("goal") or ""
        formatted.append(f"{title} ({kind}, {progress}%): {stage or goal} [plans.yaml, {plan.get('id')}]")

    for task in plan_context.get("today_tasks", []):
        formatted.append(
            f"Today task: {task.get('title')} ({task.get('status', 'todo')}) [plan_tasks.jsonl, {task.get('id')}]"
        )

    for entry in plan_context.get("recent_progress", []):
        summary = entry.get("summary") or entry.get("note") or entry
        formatted.append(f"Recent progress: {_compact_text(summary)} [plan_progress.jsonl, {entry.get('id')}]")
    return formatted


def _normalize_record(record: Any, default_type: str, default_source: str) -> dict[str, Any]:
    if isinstance(record, dict):
        normalized = dict(record)
    else:
        normalized = {"content": _compact_text(record)}

    normalized.setdefault("type", default_type)
    normalized.setdefault("source", default_source)

    if "content" not in normalized:
        fields = []
        for key in ("name", "current_goal", "status", "description"):
            if normalized.get(key):
                fields.append(f"{key}: {normalized[key]}")
        normalized["content"] = "; ".join(fields) if fields else _compact_text(normalized)
    return normalized


def _record_search_text(record: dict[str, Any]) -> str:
    fields = [
        record.get("id"),
        record.get("type"),
        record.get("content"),
        record.get("name"),
        record.get("current_goal"),
        record.get("status"),
        " ".join(map(str, _ensure_list(record.get("tags")))),
    ]
    return " ".join(str(field) for field in fields if field)


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _compact_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_compact_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(_compact_text(item) for item in value)
    return str(value)
