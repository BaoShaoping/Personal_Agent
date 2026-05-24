import json
import shutil
from datetime import date
from pathlib import Path

from personal_agent.audit_log import read_audit_events
from personal_agent.demo_seed_reset import reset_demo_today_tasks
from personal_agent.memory_store import read_jsonl_file
from personal_agent.plan_store import list_today_tasks


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def _copy_data(name):
    data_dir = ROOT / "backend" / "tests" / name
    if data_dir.exists():
        shutil.rmtree(data_dir)
    shutil.copytree(DATA_DIR, data_dir)
    audit_file = data_dir / "audit_log.jsonl"
    if audit_file.exists():
        audit_file.unlink()
    return data_dir


def test_reset_demo_today_tasks_archives_only_tasks_dated_today():
    data_dir = _copy_data("_tmp_demo_seed_reset")
    target_day = date(2026, 5, 23)
    today_task = {
        "id": "task_demo_today_001",
        "plan_id": "plan_english_001",
        "date": target_day.isoformat(),
        "title": "Demo task that should be archived",
        "status": "todo",
        "source": "test",
    }
    old_task = {
        "id": "task_demo_old_001",
        "plan_id": "plan_english_001",
        "date": "2026-05-22",
        "title": "Older task that should remain active",
        "status": "todo",
        "source": "test",
    }
    try:
        before_plans = (data_dir / "plans.yaml").read_bytes()
        with (data_dir / "plan_tasks.jsonl").open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(today_task, ensure_ascii=False) + "\n")
            handle.write(json.dumps(old_task, ensure_ascii=False) + "\n")

        result = reset_demo_today_tasks(data_dir=data_dir, today=target_day)

        assert result["ok"] is True
        assert result["removed_count"] == 1
        assert list_today_tasks(data_dir=data_dir, today=target_day) == []
        remaining_tasks = read_jsonl_file(data_dir / "plan_tasks.jsonl")
        assert any(task.get("id") == "task_demo_old_001" for task in remaining_tasks)
        assert not any(task.get("id") == "task_demo_today_001" for task in remaining_tasks)
        assert (data_dir / "plans.yaml").read_bytes() == before_plans

        archive_path = Path(result["archive_path"])
        assert archive_path.exists()
        archived_tasks = read_jsonl_file(archive_path)
        assert [task["id"] for task in archived_tasks] == ["task_demo_today_001"]

        events = read_audit_events(data_dir=data_dir, event_type="demo_seed_reset")
        assert events
        assert events[0]["payload"]["removed_count"] == 1
        assert events[0]["payload"]["archive_path"] == str(archive_path)
    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)


def test_reset_demo_today_tasks_is_noop_when_today_is_already_empty():
    data_dir = _copy_data("_tmp_demo_seed_reset_empty")
    target_day = date(2026, 5, 24)
    old_task = {
        "id": "task_demo_old_002",
        "plan_id": "plan_english_001",
        "date": "2026-05-22",
        "title": "Older task that should remain active",
        "status": "todo",
        "source": "test",
    }
    try:
        with (data_dir / "plan_tasks.jsonl").open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(old_task, ensure_ascii=False) + "\n")
        before_tasks = (data_dir / "plan_tasks.jsonl").read_bytes()

        result = reset_demo_today_tasks(data_dir=data_dir, today=target_day)

        assert result["ok"] is True
        assert result["removed_count"] == 0
        assert result["archive_path"] == ""
        assert result["audit_event"] is None
        assert (data_dir / "plan_tasks.jsonl").read_bytes() == before_tasks
        assert not (data_dir / "demo_reset_archive").exists()
        assert read_audit_events(data_dir=data_dir, event_type="demo_seed_reset") == []
    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)
