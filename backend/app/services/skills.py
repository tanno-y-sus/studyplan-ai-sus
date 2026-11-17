"""単元ごとの「できること」チェックリストと、チェックからのレベル計算（02-2 スキル判定）。

チェックリストは単元ごとに1回だけ AI に作ってもらい、DB に保存して使い回す。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.models import Topic, TopicSkill

# 目的ごとに、最初から「できるようになりたいこと」にチェックを入れる目安（この level 以下）
PURPOSE_LEVELS = {"basics": 2, "exam": 3, "work": 4, "other": 0}


def checklist_for(db: Session, topic: Topic, ai: AIProvider) -> list[TopicSkill]:
    if not topic.skills:
        result = ai.skill_checklist(topic.name, topic.category)
        items = sorted(result.items, key=lambda i: i.level)  # 易しい順
        for i, item in enumerate(items):
            topic.skills.append(TopicSkill(order=i, text=item.text.strip(), level=item.level))
        db.flush()
    return list(topic.skills)


def levels_from_checks(skills: list[TopicSkill], can_do: list[str], goals: list[str]) -> tuple[int, int]:
    """チェックから（現在, 目標）のレベル目安を計算する。

    現在：その level 以下の項目がすべて「できる」になっている最大の level（何もなければ 1）
    目標：「できるようになりたい」項目の最大 level（現在より下にはしない）
    """
    can = set(can_do)
    current = 1
    for level in range(1, 6):
        at_or_below = [s for s in skills if s.level <= level]
        if at_or_below and all(s.text in can for s in at_or_below):
            current = level
        else:
            break
    level_of = {s.text: s.level for s in skills}
    wanted = [level_of[g] for g in goals if g in level_of]
    target = max(wanted) if wanted else current + 1
    return current, max(min(target, 5), current)
