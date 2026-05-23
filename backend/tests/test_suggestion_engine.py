import shutil
from datetime import date
from pathlib import Path

from personal_agent.suggestion_engine import suggest_next_action


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def _context(today_tasks=None, active_plans=None):
    return {
        "context_markdown": "# Personal Context Pack",
        "sources": [],
        "active_plans": active_plans or [],
        "plan_context": {
            "active_plans": active_plans or [],
            "today_tasks": today_tasks or [],
            "recent_progress": [],
        },
    }


def _task():
    return {
        "id": "task_test_today_001",
        "plan_id": "plan_english_001",
        "date": "2026-05-03",
        "title": "Review 10 English words",
        "status": "todo",
    }


def _active_plan():
    return {
        "id": "plan_english_001",
        "title": "Improve English ability",
        "goal": "Build vocabulary and short expression habit.",
        "tags": ["English", "career growth"],
        "status": "active",
    }


def test_regular_question_returns_answer_only():
    result = suggest_next_action(
        "这个项目现在有哪些模块？",
        _context(),
        ask_result={"answer": "Current modules are listed in the context."},
    )

    assert result["type"] == "answer_only"
    assert result["answer"]
    assert "没有需要执行" in result["reason"]


def test_memory_request_returns_save_memory_candidate():
    result = suggest_next_action("请帮我记住：我更喜欢简单直接的回答。", _context())

    assert result["type"] == "suggested_action"
    assert result["title"] == "保存记忆候选"
    assert "长期上下文" in result["message"]
    assert result["action"]["kind"] == "save_memory_candidate"
    assert result["action"]["title"] == "保存记忆候选"
    assert "记忆候选" in result["action"]["summary"]
    assert result["action"]["target"] == "memories.jsonl"
    assert result["action"]["requires_confirmation"] is True


def test_suggested_action_uses_canonical_action_metadata():
    result = suggest_next_action("please remember: I prefer direct answers.", _context())
    action = result["action"]

    assert action["id"].startswith("act_")
    assert action["title"] == result["title"]
    assert action["summary"]
    assert action["source"] == "suggestion_engine"
    assert "T" in action["created_at"]
    assert isinstance(action["payload"], dict)


def test_long_term_learning_request_returns_create_plan_candidate():
    result = suggest_next_action("我想长期提升英语表达能力。", _context())

    assert result["type"] == "suggested_action"
    assert result["title"] == "创建计划候选"
    assert "长期方向" in result["message"]
    assert result["action"]["kind"] == "create_plan_candidate"
    assert result["action"]["title"] == "创建计划候选"
    assert result["action"]["target"] == "plans.yaml"


def test_unrelated_active_plan_does_not_block_new_plan_candidate():
    result = suggest_next_action(
        "I want a long-term plan to improve Python ability.",
        _context(active_plans=[{"id": "plan_english_001", "title": "Improve English ability", "tags": ["English"]}]),
    )

    assert result["type"] == "suggested_action"
    assert result["action"]["kind"] == "create_plan_candidate"


def test_today_task_request_with_empty_today_tasks_returns_create_today_task_candidate():
    result = suggest_next_action(
        "根据我的长期计划，生成一个今天可以完成的最小任务。",
        _context(active_plans=[_active_plan()]),
    )

    assert result["type"] == "suggested_action"
    assert result["title"] == "生成今日最小任务"
    assert result["action"]["kind"] == "create_today_task_candidate"
    assert result["action"]["target"] == "plan_english_001"
    assert result["action"]["payload"]["plan_id"] == "plan_english_001"
    assert result["action"]["payload"]["date"] == date.today().isoformat()
    assert "英语单词" in result["action"]["payload"]["title"]
    assert result["action"]["requires_confirmation"] is True


def test_completed_today_task_returns_update_done():
    result = suggest_next_action("我今天的任务完成了。", _context(today_tasks=[_task()]))

    assert result["type"] == "suggested_action"
    assert result["title"] == "更新任务状态"
    assert result["action"]["kind"] == "update_plan_task_status"
    assert result["action"]["target"] == "task_test_today_001"
    assert result["action"]["payload"]["status"] == "done"
    assert result["action"]["payload"]["note"] == "用户表示任务已完成。"


def test_blocked_today_task_returns_update_blocked():
    result = suggest_next_action("我今天卡住了，不会做。", _context(today_tasks=[_task()]))

    assert result["type"] == "suggested_action"
    assert result["action"]["kind"] == "update_plan_task_status"
    assert result["action"]["payload"]["status"] == "blocked"


def test_suggestion_engine_does_not_write_data_files():
    working_data = ROOT / "backend" / "tests" / "_tmp_suggestion_readonly"
    if working_data.exists():
        shutil.rmtree(working_data)
    shutil.copytree(DATA_DIR, working_data)
    try:
        before = {
            path.relative_to(working_data).as_posix(): path.read_bytes()
            for path in working_data.rglob("*")
            if path.is_file()
        }

        suggest_next_action("请帮我记住：这是一个决定。", _context(today_tasks=[_task()]))
        suggest_next_action("我今天的任务完成了。", _context(today_tasks=[_task()]))
        suggest_next_action("我想长期提升英语。", _context())

        after = {
            path.relative_to(working_data).as_posix(): path.read_bytes()
            for path in working_data.rglob("*")
            if path.is_file()
        }
        assert after == before
    finally:
        if working_data.exists():
            shutil.rmtree(working_data)
