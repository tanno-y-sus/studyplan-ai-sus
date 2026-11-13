"""単元の正規化（02-1）。別名の辞書で見つからなければ AI に聞く。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.models import LevelGuide, Topic, TopicAlias

GENERIC_LEVEL_GUIDES = {
    1: "その技術に触れたことがない",
    2: "基本用語・概念を説明できる",
    3: "チュートリアルや手順書どおりに使える",
    4: "自力で構成を決め、エラーやトラブルの原因を分析・対処できる",
    5: "要件に合わせて設計・構築でき、他者に教えられる",
}


class TopicError(ValueError):
    def __init__(self, message: str, suggestions: list[str] | None = None):
        super().__init__(message)
        self.suggestions = suggestions or []


def find_topic(db: Session, text: str) -> Topic | None:
    key = text.strip().lower()
    topic = db.scalar(select(Topic).where(func.lower(Topic.name) == key))
    if topic:
        return topic
    alias = db.scalar(select(TopicAlias).where(func.lower(TopicAlias.alias) == key))
    return alias.topic if alias else None


def resolve_topic(db: Session, text: str, ai: AIProvider) -> Topic:
    """入力を既存の単元に結び付ける。なければ AI で正規化して新しい単元を作る。"""
    found = find_topic(db, text)
    if found:
        return found
    norm = ai.normalize_topic(text)
    if not norm.is_it:
        raise TopicError("このアプリは IT 技術の単元のみ対応しています")
    if norm.too_broad:
        raise TopicError(
            f"「{text}」は範囲が広いため、学びたいサービスや領域を選んでください", norm.suggestions
        )
    found = find_topic(db, norm.name)
    if found:
        db.add(TopicAlias(topic=found, alias=text.strip()))
        return found
    topic = Topic(name=norm.name, category=norm.category, prerequisites=norm.prerequisites, source="ai")
    topic.aliases.append(TopicAlias(alias=text.strip()))
    for level, desc in GENERIC_LEVEL_GUIDES.items():
        topic.level_guides.append(LevelGuide(level=level, description=desc))
    db.add(topic)
    db.flush()
    return topic
