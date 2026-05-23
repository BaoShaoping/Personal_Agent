"""Local file-backed memory loading for the Context Builder MVP."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


YAML_FILES = {
    "profile": "profile.yaml",
    "goals": "goals.yaml",
    "projects": "projects.yaml",
    "constraints": "constraints.yaml",
    "settings": "settings.yaml",
}

JSONL_FILES = {
    "decisions": "decisions.jsonl",
    "memories": "memories.jsonl",
}


@dataclass
class MemoryData:
    """All local memory files plus loader diagnostics."""

    data_dir: Path
    profile: dict[str, Any] = field(default_factory=dict)
    goals: dict[str, Any] = field(default_factory=dict)
    projects: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    memories: list[dict[str, Any]] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    load_errors: list[dict[str, str]] = field(default_factory=list)


def load_memory_data(data_dir: str | Path = "data") -> MemoryData:
    """Load local YAML and JSONL memory files.

    Missing or malformed files are reported in ``missing_files`` or
    ``load_errors`` rather than raising, so the context builder can still return
    a useful empty or partial pack.
    """

    root = Path(data_dir)
    data = MemoryData(data_dir=root)

    for attr, filename in YAML_FILES.items():
        path = root / filename
        if not path.exists():
            data.missing_files.append(filename)
            continue
        try:
            value = read_yaml_file(path)
            setattr(data, attr, value if isinstance(value, dict) else {})
        except Exception as exc:  # pragma: no cover - defensive diagnostics
            data.load_errors.append({"file": filename, "error": str(exc)})
            setattr(data, attr, {})

    for attr, filename in JSONL_FILES.items():
        path = root / filename
        if not path.exists():
            data.missing_files.append(filename)
            continue
        try:
            setattr(data, attr, read_jsonl_file(path))
        except Exception as exc:  # pragma: no cover - defensive diagnostics
            data.load_errors.append({"file": filename, "error": str(exc)})
            setattr(data, attr, [])

    return data


def read_jsonl_file(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL file, skipping blank lines and malformed records."""

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError:
            records.append(
                {
                    "id": f"invalid_jsonl_line_{line_number}",
                    "type": "load_error",
                    "content": stripped,
                    "source": str(path),
                    "_load_error": "invalid_json",
                }
            )
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def read_yaml_file(path: str | Path) -> Any:
    """Read YAML with PyYAML when available, otherwise use a tiny fallback.

    The fallback intentionally supports only the simple mapping/list/scalar YAML
    used by the MVP seed files and tests.
    """

    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except ModuleNotFoundError:
        return parse_simple_yaml(text)


def parse_simple_yaml(text: str) -> Any:
    """Parse the small YAML subset used by this project."""

    cleaned: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        cleaned.append((indent, raw_line.strip()))

    if not cleaned:
        return {}

    value, _ = _parse_yaml_block(cleaned, 0, cleaned[0][0])
    return value


def _parse_yaml_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index

    is_list = lines[index][0] == indent and lines[index][1].startswith("- ")
    if is_list:
        items: list[Any] = []
        while index < len(lines):
            current_indent, text = lines[index]
            if current_indent != indent or not text.startswith("- "):
                break
            rest = text[2:].strip()
            index += 1
            if not rest:
                child, index = _parse_yaml_block(lines, index, indent + 2)
                items.append(child)
                continue
            if _looks_like_mapping_item(rest):
                item = _mapping_from_inline_item(rest)
                while index < len(lines) and lines[index][0] > indent:
                    child_indent = lines[index][0]
                    child, index = _parse_yaml_block(lines, index, child_indent)
                    if isinstance(child, dict):
                        item.update(child)
                items.append(item)
            else:
                items.append(_parse_scalar(rest))
        return items, index

    mapping: dict[str, Any] = {}
    while index < len(lines):
        current_indent, text = lines[index]
        if current_indent != indent or text.startswith("- "):
            break
        key, raw_value = _split_yaml_key_value(text)
        index += 1
        if raw_value == "":
            if index < len(lines) and lines[index][0] > indent:
                child, index = _parse_yaml_block(lines, index, lines[index][0])
                mapping[key] = child
            else:
                mapping[key] = {}
        else:
            mapping[key] = _parse_scalar(raw_value)
    return mapping, index


def _looks_like_mapping_item(text: str) -> bool:
    return ":" in text and not text.startswith(("http://", "https://"))


def _mapping_from_inline_item(text: str) -> dict[str, Any]:
    key, raw_value = _split_yaml_key_value(text)
    return {key: _parse_scalar(raw_value) if raw_value else {}}


def _split_yaml_key_value(text: str) -> tuple[str, str]:
    key, _, raw_value = text.partition(":")
    return key.strip(), raw_value.strip()


def _parse_scalar(value: str) -> Any:
    if value == "":
        return ""
    lowered = value.lower()
    if lowered in {"null", "none", "~"}:
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
