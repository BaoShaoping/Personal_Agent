import json
from datetime import date

from personal_agent.plan_store import load_plan_data
from personal_agent.system_engine import (
    ATTRIBUTE_KEYS,
    attribute_value,
    build_system_summary,
    complete_and_settle_task,
    default_task_rewards,
    forest_stage,
    level_info,
    level_threshold,
    load_system_state,
    save_system_state,
)


def test_level_info_thresholds():
    assert level_info(0)["level"] == 1
    assert level_info(0)["exp_into_level"] == 0

    at_threshold = level_info(100)
    assert at_threshold["level"] == 2
    assert at_threshold["exp_into_level"] == 0

    # 520 = 100 (->Lv2) + 150 (->Lv3) + 200 (->Lv4), leaving 70 into Lv4.
    info = level_info(520)
    assert info["level"] == 4
    assert info["exp_into_level"] == 70
    assert info["exp_for_next"] == level_threshold(4)
    assert 0 <= info["progress_percent"] <= 100


def test_attribute_value_is_floor_sqrt():
    assert attribute_value(1600) == 40
    assert attribute_value(0) == 0
    assert attribute_value(99) == 9


def test_forest_stage_tiers():
    assert forest_stage(0) == "种子"
    assert forest_stage(2) == "萌芽"
    assert forest_stage(5) == "树苗"
    assert forest_stage(12) == "小林"
    assert forest_stage(25) == "森林"


def test_load_defaults_when_missing(tmp_path):
    state = load_system_state(tmp_path)
    assert state["total_exp"] == 0
    assert state["magic_points"] == 0
    assert set(state["attributes"].keys()) == set(ATTRIBUTE_KEYS)
    assert all(state["attributes"][key]["exp"] == 0 for key in ATTRIBUTE_KEYS)
    assert state["forest"]["growth"] == 0
    assert state["forest"]["decorations"] == []


def test_save_and_load_round_trip(tmp_path):
    save_system_state(
        {
            "total_exp": 520,
            "magic_points": 145,
            "character": {"name": "阿系", "theme": "default"},
            "attributes": {"intellect": {"exp": 1600}},
            "forest": {
                "growth": 12,
                "decorations": [{"id": "tree_sakura", "label": "樱花树", "kind": "tree"}],
            },
        },
        tmp_path,
    )

    # Atomic write leaves no temp file behind.
    assert not (tmp_path / "system_state.yaml.tmp").exists()
    assert (tmp_path / "system_state.yaml").exists()

    loaded = load_system_state(tmp_path)
    assert loaded["total_exp"] == 520
    assert loaded["magic_points"] == 145
    assert loaded["character"]["name"] == "阿系"
    assert loaded["attributes"]["intellect"]["exp"] == 1600
    # Unspecified attributes fall back to default 0.
    assert loaded["attributes"]["spirit"]["exp"] == 0
    assert loaded["forest"]["growth"] == 12
    assert loaded["forest"]["decorations"][0]["label"] == "樱花树"


def test_default_task_rewards_infers_attribute():
    assert default_task_rewards({"title": "慢跑 20 分钟"})["attribute"] == "constitution"
    assert default_task_rewards({"title": "背 10 个单词"})["attribute"] == "intellect"
    assert default_task_rewards({"title": "给系统面板写渲染逻辑"})["attribute"] == "creativity"
    reward = default_task_rewards({"title": "随便做点别的"})
    assert reward["exp"] == 10 and reward["magic_points"] == 5 and reward["attribute_exp"] == 15


def test_build_system_summary_shape(tmp_path):
    (tmp_path / "plans.yaml").write_text(
        "plans:\n"
        "  - id: plan_eng\n"
        "    title: 英语能力\n"
        "    kind: side\n"
        "    status: active\n"
        "    progress_percent: 71\n",
        encoding="utf-8",
    )
    today = date.today().isoformat()
    (tmp_path / "plan_tasks.jsonl").write_text(
        json.dumps(
            {"id": "task_a", "plan_id": "plan_eng", "date": today, "title": "背单词", "status": "todo"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    save_system_state({"total_exp": 520, "magic_points": 145, "forest": {"growth": 12}}, tmp_path)

    summary = build_system_summary(tmp_path)
    assert summary["ok"] is True
    assert summary["level"]["level"] == 4
    assert summary["magic_points"] == 145
    assert len(summary["attributes"]) == 5
    assert summary["forest"]["stage"] == "小林"
    assert any(q["plan_id"] == "plan_eng" for q in summary["quest_lines"])

    task = next(t for t in summary["today_tasks"] if t["id"] == "task_a")
    assert task["rewards"]["attribute"] == "intellect"
    assert summary["recent_dings"] == []


def _setup_settlement(tmp_path, total_exp=0, task_rewards=None):
    (tmp_path / "plans.yaml").write_text(
        "plans:\n  - id: plan_eng\n    title: 英语能力\n    kind: side\n    status: active\n    progress_percent: 10\n",
        encoding="utf-8",
    )
    task = {"id": "task_x", "plan_id": "plan_eng", "date": "2026-05-30", "title": "背单词", "status": "todo"}
    if task_rewards is not None:
        task["rewards"] = task_rewards
    (tmp_path / "plan_tasks.jsonl").write_text(json.dumps(task, ensure_ascii=False) + "\n", encoding="utf-8")
    save_system_state({"total_exp": total_exp}, tmp_path)


def test_complete_and_settle_grants_rewards(tmp_path):
    _setup_settlement(
        tmp_path,
        total_exp=0,
        task_rewards={"exp": 40, "magic_points": 12, "attribute": "intellect", "attribute_exp": 50},
    )
    result = complete_and_settle_task("task_x", tmp_path)
    assert result["ok"] is True and result["already_done"] is False

    settlement = result["settlement"]
    assert settlement["deltas"]["exp"] == 40
    assert settlement["deltas"]["forest_growth"] == 1
    assert settlement["leveled_up"] is False and settlement["level"] == 1

    state = load_system_state(tmp_path)
    assert state["total_exp"] == 40
    assert state["magic_points"] == 12
    assert state["attributes"]["intellect"]["exp"] == 50
    assert state["forest"]["growth"] == 1

    summary = build_system_summary(tmp_path)
    assert summary["recent_dings"] and "背单词" in summary["recent_dings"][0]["text"]

    done = next(t for t in load_plan_data(tmp_path).tasks if t["id"] == "task_x")
    assert done["status"] == "done"


def test_complete_is_idempotent(tmp_path):
    _setup_settlement(
        tmp_path,
        total_exp=0,
        task_rewards={"exp": 40, "magic_points": 12, "attribute": "intellect", "attribute_exp": 50},
    )
    complete_and_settle_task("task_x", tmp_path)
    again = complete_and_settle_task("task_x", tmp_path)
    assert again["already_done"] is True
    # Rewards are not granted a second time.
    assert load_system_state(tmp_path)["total_exp"] == 40


def test_complete_detects_level_up(tmp_path):
    _setup_settlement(
        tmp_path,
        total_exp=80,
        task_rewards={"exp": 30, "magic_points": 5, "attribute": "willpower", "attribute_exp": 10},
    )
    settlement = complete_and_settle_task("task_x", tmp_path)["settlement"]
    assert settlement["leveled_up"] is True
    assert settlement["level"] == 2
    assert "升级" in settlement["ding_text"]


def test_complete_unknown_task_returns_error(tmp_path):
    _setup_settlement(tmp_path)
    result = complete_and_settle_task("nope", tmp_path)
    assert result["ok"] is False


def test_system_task_complete_endpoint_validates_task_id():
    from personal_agent.api import app

    client = app.test_client()
    res = client.post("/api/system/tasks/complete", json={})
    assert res.status_code == 400
    assert res.get_json()["ok"] is False
