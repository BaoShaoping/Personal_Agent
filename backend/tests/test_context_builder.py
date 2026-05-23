import json
import shutil
from pathlib import Path

from personal_agent.context_builder import build_context_pack


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def test_reads_seed_context_from_data_dir():
    pack = build_context_pack("请根据我的背景回答", data_dir=str(DATA_DIR))

    assert "Personal Context Agent" in pack.profile_summary
    assert pack.active_goals
    assert pack.active_projects
    assert pack.constraints
    assert pack.sources


def test_ai_training_question_recalls_relevant_decision():
    pack = build_context_pack("我现在适合做AI培训吗？", data_dir=str(DATA_DIR))
    decision_text = " ".join(item["content"] for item in pack.relevant_decisions)

    assert "generic AI training" in decision_text
    assert "technical project practice" in decision_text


def test_personal_context_agent_question_recalls_project_and_mvp_context():
    pack = build_context_pack("我们下一步怎么开发 Personal Context Agent？", data_dir=str(DATA_DIR))
    project_text = " ".join(item["content"] for item in pack.active_projects)
    combined = pack.context_markdown

    assert "Personal Context Agent" in project_text
    assert "MVP" in combined
    assert "context builder" in combined.lower()


def test_context_markdown_respects_max_chars():
    pack = build_context_pack(
        "我们下一步怎么开发 Personal Context Agent？",
        data_dir=str(DATA_DIR),
        max_chars=500,
    )

    assert len(pack.context_markdown) <= 500
    assert pack.stats["context_chars"] <= 500


def test_missing_data_file_still_returns_pack():
    working_data = ROOT / "backend" / "tests" / "_tmp_missing_data"
    if working_data.exists():
        shutil.rmtree(working_data)
    shutil.copytree(DATA_DIR, working_data)
    try:
        (working_data / "memories.jsonl").unlink()

        pack = build_context_pack("我们下一步怎么开发 Personal Context Agent？", data_dir=str(working_data))

        assert pack.context_markdown
        assert "memories.jsonl" in pack.stats["missing_files"]
        assert isinstance(pack.relevant_memories, list)
    finally:
        if working_data.exists():
            shutil.rmtree(working_data)


def test_sources_include_traceable_ids():
    pack = build_context_pack("我现在适合做AI培训吗？", data_dir=str(DATA_DIR))

    assert pack.sources
    assert any(source["source"] == "conversation" and source["id"] == "dec_20260430_001" for source in pack.sources)


def test_context_pack_is_json_serializable():
    pack = build_context_pack("我们下一步怎么开发 Personal Context Agent？", data_dir=str(DATA_DIR))

    json.dumps(pack.to_dict(), ensure_ascii=False)
