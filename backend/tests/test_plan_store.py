import json
import shutil
from datetime import date
from pathlib import Path

from personal_agent.context_builder import build_context_pack
from personal_agent.plan_store import build_plan_context, list_today_tasks, load_plan_data


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def test_loads_plans_yaml():
    data = load_plan_data(DATA_DIR)

    assert data.plans
    assert any(plan["id"] == "plan_english_001" for plan in data.plans)


def test_lists_today_task():
    tasks = list_today_tasks(data_dir=DATA_DIR, today=date(2026, 5, 2))

    assert tasks
    assert any(task["id"] == "task_20260502_001" for task in tasks)


def test_missing_plan_files_return_diagnostics():
    partial_data = ROOT / "backend" / "tests" / "_tmp_plan_missing_data"
    if partial_data.exists():
        shutil.rmtree(partial_data)
    partial_data.mkdir()
    try:
        data = load_plan_data(partial_data)

        assert "plans.yaml" in data.missing_files
        assert "plan_tasks.jsonl" in data.missing_files
        assert "plan_progress.jsonl" in data.missing_files
        assert "reminders.yaml" in data.missing_files
    finally:
        if partial_data.exists():
            shutil.rmtree(partial_data)


def test_build_plan_context_returns_active_plans_and_sources():
    working_data = ROOT / "backend" / "tests" / "_tmp_plan_context_today"
    if working_data.exists():
        shutil.rmtree(working_data)
    shutil.copytree(DATA_DIR, working_data)
    try:
        today_task = {
            "id": "task_dynamic_today_001",
            "plan_id": "plan_english_001",
            "date": date.today().isoformat(),
            "title": "Dynamic test task for today's plan context",
            "status": "todo",
            "source": "test",
        }
        with (working_data / "plan_tasks.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(today_task, ensure_ascii=False) + "\n")

        context = build_plan_context("我今天应该做什么？", data_dir=working_data)

        assert context["active_plans"]
        assert context["today_tasks"]
        assert any(source["source"] == "plans.yaml" for source in context["sources"])
    finally:
        if working_data.exists():
            shutil.rmtree(working_data)


def test_context_builder_includes_active_long_term_plans():
    pack = build_context_pack("我今天应该做什么？", data_dir=str(DATA_DIR))

    assert "Active Long-term Plans" in pack.context_markdown
    assert pack.active_plans
    assert "plans" in pack.stats["loaded"]
    assert any(source["source"] == "plans.yaml" for source in pack.sources)
