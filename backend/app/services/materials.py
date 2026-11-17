"""教材選定（02-3）。カタログ → なければ無料検索 API で候補を集めて AI が選ぶ。"""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.config import Settings, settings
from app.models import Material, MaterialSection, Topic
from app.search.router import search_materials, uses_demo_search


def check_url(url: str | None, cfg: Settings = settings) -> str:
    if not url:
        return "URLなし"
    if url.startswith("https://example.com/demo/"):
        return "デモ（実在しない）"
    if not cfg.url_check:
        return "未確認"
    try:
        res = httpx.head(url, follow_redirects=True, timeout=10)
        if res.status_code == 405:
            res = httpx.get(url, follow_redirects=True, timeout=10)
        return f"{res.status_code} OK" if res.status_code < 400 else f"{res.status_code} エラー"
    except httpx.HTTPError:
        return "接続できません"


DEMO_RETIRED_COMMENT = "本物の検索 API に切り替えたため、デモ検索の教材（実在しない URL）を除外しました"


def retire_demo_materials(topic: Topic) -> int:
    """デモ検索で見つけた教材（example.com のダミー）を、使い回しの対象から外す。

    デモ教材と一緒に AI が作った実践課題（source=ai）も同じ組なので一緒に外す。
    """
    retired = 0
    for status in ("approved", "ai_pending"):
        group = [m for m in topic.materials if m.status == status]
        if not any(m.source == "demo" for m in group):
            continue
        for m in group:
            if m.source in ("demo", "ai"):
                m.status = "rejected"
                m.review_comment = DEMO_RETIRED_COMMENT
                retired += 1
    return retired


def materials_for_topic(
    db: Session,
    topic: Topic,
    current_level: int,
    target_level: int,
    ai: AIProvider,
    cfg: Settings = settings,
    goals: list[str] | None = None,
) -> tuple[list[Material], list[str]]:
    """プランに使う教材と、利用者への注意文を返す。"""
    if not uses_demo_search(cfg):
        retire_demo_materials(topic)
    approved = [m for m in topic.materials if m.status == "approved"]
    if approved:
        return approved, []

    pending = [m for m in topic.materials if m.status == "ai_pending"]
    if pending:  # 以前 AI が探した結果を使い回す（検索回数の節約）
        return pending, [f"「{topic.name}」は AI が探した教材です（育成担当のレビュー前）"]

    outcome = search_materials(db, topic.name, cfg=cfg)
    notes = [f"「{topic.name}」は AI が探した教材です（育成担当のレビュー前）"]
    if outcome.skipped:
        notes.append("一部の検索 API を使えませんでした：" + " / ".join(outcome.skipped[:3]))
    selection = ai.select_materials(topic.name, current_level, target_level, outcome.candidates, goals=goals)

    created: list[Material] = []
    for choice in selection.chosen:
        if not (0 <= choice.candidate_index < len(outcome.candidates)):
            continue
        c = outcome.candidates[choice.candidate_index]
        m = Material(
            topic=topic,
            title=c.title,
            url=c.url,
            type=c.type,
            source=c.source,
            status="ai_pending",
            supplementary=c.type == "video",
            reference_hours=choice.reference_hours or sum(s.est_hours for s in choice.sections),
            reference_basis=choice.reference_basis or "AI推定",
            url_check=check_url(c.url),
        )
        for i, s in enumerate(choice.sections):
            m.sections.append(
                MaterialSection(
                    order=i,
                    title=s.title,
                    est_hours=s.est_hours,
                    level_from=s.level_from,
                    level_to=s.level_to,
                )
            )
        created.append(m)
    exercise = Material(
        topic=topic,
        title=selection.exercise_title,
        url=None,
        type="exercise",
        source="ai",
        status="ai_pending",
        reference_hours=selection.exercise_hours,
        reference_basis="AI推定（課題の手順の数から）",
        url_check="URLなし",
        review_comment=selection.exercise_description,
    )
    created.append(exercise)
    db.add_all(created)
    db.flush()
    return created, notes
