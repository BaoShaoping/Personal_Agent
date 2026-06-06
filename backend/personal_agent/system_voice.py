"""System Edition: 系统-voice narration for task completion (step 6).

In live mode the LLM (GLM) speaks in the System's persona to congratulate the
host; otherwise (mock/offline/failure) a deterministic template line is used.
The narration is the 「叮！」 text persisted in the reward audit event and shown
on the panel, so it stays consistent between the burst and the 系统记录 feed.
"""

from __future__ import annotations

from typing import Any

from .model_gateway import boost_max_tokens, generate_response, load_model_config


NARRATION_PROMPT = """你是绑定在宿主身上的专属「系统」——像网络小说里的那种「系统」：温暖、鼓励、带一点仪式感，称用户为「宿主」。
宿主刚刚完成了一个任务。用一句话祝贺他，可用「叮！」开头。

硬性要求：
- **必须用简体中文**。
- 只输出这一句话：不要解释、不要换行、不超过 30 个字。
- 绝不施压或惩罚。"""


def narrate_completion(
    task_title: str,
    rewards: dict[str, Any],
    leveled_up: bool,
    level: int,
    attribute_label: str,
    data_dir: str = "data",
) -> str:
    """Return the 「叮！」 line for a completed task (LLM in live mode, else template)."""

    config = load_model_config(data_dir)
    if config.get("mode") == "live":
        line = _llm_narration(task_title, rewards, leveled_up, level, config)
        if line:
            return line
    return template_ding(task_title, rewards, leveled_up, level, attribute_label)


def template_ding(
    task_title: str,
    rewards: dict[str, Any],
    leveled_up: bool,
    level: int,
    attribute_label: str,
) -> str:
    exp = int(rewards.get("exp") or 0)
    magic = int(rewards.get("magic_points") or 0)
    text = f"叮！宿主完成「{task_title}」，经验 +{exp}，✦ +{magic}"
    if attribute_label:
        text += f"，{attribute_label} ↑"
    if leveled_up:
        text += f"（升级！Lv.{level}）"
    return text


def _llm_narration(
    task_title: str,
    rewards: dict[str, Any],
    leveled_up: bool,
    level: int,
    config: dict[str, Any],
) -> str | None:
    user = f"任务：{task_title}\n获得经验 {rewards.get('exp', 0)}，魔法点 {rewards.get('magic_points', 0)}"
    if leveled_up:
        user += f"，并升到了 Lv.{level}"
    response = generate_response(
        [{"role": "system", "content": NARRATION_PROMPT}, {"role": "user", "content": user}],
        boost_max_tokens(config),
    )
    if not response.get("ok"):
        return None
    answer = str(response.get("answer") or "").strip()
    if not answer:
        return None
    return answer.splitlines()[0].strip()[:60] or None
