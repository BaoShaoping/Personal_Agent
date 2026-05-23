import shutil
from pathlib import Path

from personal_agent.action_executor import cancel_action, execute_confirmed_action
from personal_agent.audit_log import read_audit_events
from personal_agent.memory_store import read_jsonl_file, read_yaml_file


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


def _decision(kind="update_plan_task_status", hard_block=False):
    return {
        "ok": True,
        "permission_mode": "ask_first",
        "action_kind": kind,
        "risk_level": "medium",
        "requires_confirmation": True,
        "allowed_without_confirmation": False,
        "reason": "test decision",
        "hard_block": hard_block,
    }


def test_cancel_action_writes_audit_and_does_not_mutate_target_file():
    data_dir = _copy_data("_tmp_action_cancel")
    try:
        before = (data_dir / "plan_tasks.jsonl").read_bytes()
        result = cancel_action(
            {
                "id": "act_cancel_001",
                "kind": "update_plan_task_status",
                "target": "task_20260502_001",
                "payload": {"status": "done"},
            },
            permission_decision=_decision(),
            data_dir=data_dir,
        )

        assert result["status"] == "canceled"
        assert (data_dir / "plan_tasks.jsonl").read_bytes() == before
        events = read_audit_events(data_dir=data_dir, event_type="action_canceled")
        assert len(events) == 1
        assert events[0]["action_id"] == "act_cancel_001"
    finally:
        shutil.rmtree(data_dir)


def test_unknown_action_fails_and_writes_audit_event():
    data_dir = _copy_data("_tmp_action_unknown")
    try:
        result = execute_confirmed_action(
            {"id": "act_unknown_001", "kind": "run_shell_command", "target": "pwsh"},
            permission_decision={**_decision("run_shell_command"), "risk_level": "high"},
            confirmed=True,
            data_dir=data_dir,
        )

        assert result["ok"] is False
        assert result["status"] == "failed"
        events = read_audit_events(data_dir=data_dir, event_type="action_failed")
        assert events[0]["action_kind"] == "run_shell_command"
    finally:
        shutil.rmtree(data_dir)


def test_hard_block_permission_decision_prevents_execution():
    data_dir = _copy_data("_tmp_action_hard_block")
    try:
        result = execute_confirmed_action(
            {"id": "act_block_001", "kind": "delete_files", "target": "data"},
            permission_decision=_decision("delete_files", hard_block=True),
            confirmed=True,
            data_dir=data_dir,
        )

        assert result["ok"] is False
        assert result["status"] == "failed"
        assert "hard_block" in result["error"]["message"]
        events = read_audit_events(data_dir=data_dir, event_type="action_failed")
        assert events[0]["action_kind"] == "delete_files"
        assert "权限策略" in events[0]["summary"]
    finally:
        shutil.rmtree(data_dir)


def test_update_plan_task_status_updates_task_and_writes_audit_event():
    data_dir = _copy_data("_tmp_action_update_task")
    try:
        result = execute_confirmed_action(
            {
                "id": "act_task_001",
                "kind": "update_plan_task_status",
                "target": "task_20260502_001",
                "payload": {"status": "done", "note": "done in test"},
            },
            permission_decision=_decision(),
            confirmed=True,
            data_dir=data_dir,
        )

        assert result["ok"] is True
        assert result["status"] == "executed"
        assert result["execution_result"]["task"]["status"] == "done"
        events = read_audit_events(data_dir=data_dir, event_type="action_executed")
        assert events[0]["action_kind"] == "update_plan_task_status"
        assert "已成功执行" in events[0]["summary"]
    finally:
        shutil.rmtree(data_dir)


def test_create_plan_candidate_appends_new_plan_to_yaml():
    data_dir = _copy_data("_tmp_action_create_plan")
    try:
        before = read_yaml_file(data_dir / "plans.yaml")
        result = execute_confirmed_action(
            {
                "id": "act_plan_001",
                "kind": "create_plan_candidate",
                "target": "plans.yaml",
                "payload": {
                    "title": "Read AI papers",
                    "goal": "Build a steady AI paper reading habit.",
                    "kind": "side",
                    "status": "active",
                    "reminder_mode": "passive",
                },
            },
            permission_decision=_decision("create_plan_candidate"),
            confirmed=True,
            data_dir=data_dir,
        )

        after = read_yaml_file(data_dir / "plans.yaml")
        assert result["ok"] is True
        assert len(after["plans"]) == len(before["plans"]) + 1
        assert after["plans"][-1]["title"] == "Read AI papers"
    finally:
        shutil.rmtree(data_dir)


def test_create_today_task_candidate_appends_task_to_plan_tasks_jsonl():
    data_dir = _copy_data("_tmp_action_create_today_task")
    try:
        before = len(read_jsonl_file(data_dir / "plan_tasks.jsonl"))
        result = execute_confirmed_action(
            {
                "id": "act_today_task_001",
                "kind": "create_today_task_candidate",
                "target": "plan_english_001",
                "payload": {
                    "plan_id": "plan_english_001",
                    "date": "2026-05-16",
                    "title": "背 10 个英语单词",
                    "source": "test",
                },
            },
            permission_decision=_decision("create_today_task_candidate"),
            confirmed=True,
            data_dir=data_dir,
        )

        tasks = read_jsonl_file(data_dir / "plan_tasks.jsonl")
        created = tasks[-1]
        assert result["ok"] is True
        assert result["status"] == "executed"
        assert len(tasks) == before + 1
        assert created["id"].startswith("task_")
        assert created["plan_id"] == "plan_english_001"
        assert created["date"] == "2026-05-16"
        assert created["title"] == "背 10 个英语单词"
        assert created["status"] == "todo"
        assert created["source"] == "test"
        assert created["created_at"]
        events = read_audit_events(data_dir=data_dir, event_type="action_executed")
        assert events[0]["action_kind"] == "create_today_task_candidate"
    finally:
        shutil.rmtree(data_dir)


def test_save_memory_candidate_appends_to_memories_jsonl():
    data_dir = _copy_data("_tmp_action_save_memory")
    try:
        before = len(read_jsonl_file(data_dir / "memories.jsonl"))
        result = execute_confirmed_action(
            {
                "id": "act_mem_001",
                "kind": "save_memory_candidate",
                "target": "memories.jsonl",
                "payload": {"content": "I prefer concise answers.", "source": "test"},
            },
            permission_decision=_decision("save_memory_candidate"),
            confirmed=True,
            data_dir=data_dir,
        )

        records = read_jsonl_file(data_dir / "memories.jsonl")
        assert result["ok"] is True
        assert len(records) == before + 1
        assert records[-1]["type"] == "memory"
        assert records[-1]["confidence"] == 0.7
    finally:
        shutil.rmtree(data_dir)


def test_save_memory_candidate_appends_to_decisions_jsonl():
    data_dir = _copy_data("_tmp_action_save_decision")
    try:
        before = len(read_jsonl_file(data_dir / "decisions.jsonl"))
        result = execute_confirmed_action(
            {
                "id": "act_dec_001",
                "kind": "save_memory_candidate",
                "target": "decisions.jsonl",
                "payload": {"content": "We decided to keep the executor narrow."},
            },
            permission_decision=_decision("save_memory_candidate"),
            confirmed=True,
            data_dir=data_dir,
        )

        records = read_jsonl_file(data_dir / "decisions.jsonl")
        assert result["ok"] is True
        assert len(records) == before + 1
        assert records[-1]["type"] == "decision"
        assert records[-1]["id"].startswith("dec_")
    finally:
        shutil.rmtree(data_dir)


def test_sensitive_payload_fields_are_redacted_in_audit_log():
    data_dir = _copy_data("_tmp_action_redaction")
    try:
        execute_confirmed_action(
            {
                "id": "act_secret_001",
                "kind": "save_memory_candidate",
                "target": "memories.jsonl",
                "payload": {
                    "content": "Store a safe memory.",
                    "api_key": "should-not-survive",
                    "nested": {"token": "should-not-survive"},
                },
            },
            permission_decision=_decision("save_memory_candidate"),
            confirmed=True,
            data_dir=data_dir,
        )

        events = read_audit_events(data_dir=data_dir, event_type="action_executed")
        payload = events[0]["payload"]["action"]["payload"]
        assert payload["api_key"] == "[redacted]"
        assert payload["nested"]["token"] == "[redacted]"
    finally:
        shutil.rmtree(data_dir)
