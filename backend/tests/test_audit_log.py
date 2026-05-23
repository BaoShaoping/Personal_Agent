import shutil
from pathlib import Path

from personal_agent.audit_log import append_audit_event, read_audit_events, redact_sensitive


ROOT = Path(__file__).resolve().parents[2]


def _clean_dir(name):
    data_dir = ROOT / "backend" / "tests" / name
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    return data_dir


def test_append_audit_event_creates_file_if_missing():
    data_dir = _clean_dir("_tmp_audit_create")
    try:
        event = append_audit_event(
            {
                "event_type": "permission_evaluated",
                "module": "permission_engine",
                "summary": "Permission checked.",
            },
            data_dir=data_dir,
        )

        assert (data_dir / "audit_log.jsonl").exists()
        assert event["event_type"] == "permission_evaluated"
    finally:
        shutil.rmtree(data_dir)


def test_append_audit_event_adds_id_and_created_at():
    data_dir = _clean_dir("_tmp_audit_defaults")
    try:
        event = append_audit_event({"event_type": "suggestion_generated"}, data_dir=data_dir)

        assert event["id"].startswith("audit_")
        assert "T" in event["created_at"]
    finally:
        shutil.rmtree(data_dir)


def test_read_audit_events_returns_newest_recent_with_limit():
    data_dir = _clean_dir("_tmp_audit_recent")
    try:
        append_audit_event({"event_type": "suggestion_generated", "summary": "one"}, data_dir=data_dir)
        second = append_audit_event({"event_type": "permission_evaluated", "summary": "two"}, data_dir=data_dir)
        third = append_audit_event({"event_type": "action_canceled", "summary": "three"}, data_dir=data_dir)

        events = read_audit_events(data_dir=data_dir, limit=2)

        assert [event["id"] for event in events] == [third["id"], second["id"]]
    finally:
        shutil.rmtree(data_dir)


def test_read_audit_events_filters_by_event_type():
    data_dir = _clean_dir("_tmp_audit_event_type")
    try:
        append_audit_event({"event_type": "suggestion_generated"}, data_dir=data_dir)
        expected = append_audit_event({"event_type": "permission_evaluated"}, data_dir=data_dir)

        events = read_audit_events(data_dir=data_dir, event_type="permission_evaluated")

        assert [event["id"] for event in events] == [expected["id"]]
    finally:
        shutil.rmtree(data_dir)


def test_read_audit_events_filters_by_action_id():
    data_dir = _clean_dir("_tmp_audit_action_id")
    try:
        append_audit_event({"event_type": "permission_evaluated", "action_id": "act_other"}, data_dir=data_dir)
        expected = append_audit_event(
            {"event_type": "permission_evaluated", "action_id": "act_keep"},
            data_dir=data_dir,
        )

        events = read_audit_events(data_dir=data_dir, action_id="act_keep")

        assert [event["id"] for event in events] == [expected["id"]]
    finally:
        shutil.rmtree(data_dir)


def test_missing_audit_file_returns_empty_events():
    data_dir = _clean_dir("_tmp_audit_missing")
    try:
        assert read_audit_events(data_dir=data_dir) == []
    finally:
        shutil.rmtree(data_dir)


def test_sensitive_fields_are_redacted_recursively():
    value = {
        "api_key": "abc",
        "nested": {
            "token_value": "secret-token",
            "items": [{"password": "pw"}, {"safe": "ok"}],
        },
        "authorization": "Bearer 123",
    }

    redacted = redact_sensitive(value)

    assert redacted["api_key"] == "[redacted]"
    assert redacted["nested"]["token_value"] == "[redacted]"
    assert redacted["nested"]["items"][0]["password"] == "[redacted]"
    assert redacted["nested"]["items"][1]["safe"] == "ok"
    assert redacted["authorization"] == "[redacted]"
