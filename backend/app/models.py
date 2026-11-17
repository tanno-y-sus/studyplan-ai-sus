"""データモデル（Notion 04-4 準拠の MVP 分）。"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(200), unique=True)  # 小文字にそろえて保存
    role: Mapped[str] = mapped_column(String(20), default="member")  # member / mentor / admin
    password_hash: Mapped[str] = mapped_column(String(300))  # scrypt（パスワードそのものは保存しない）
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuthSession(Base):
    """ログイン中の状態。トークンそのものは保存せず、SHA-256 の値だけを保存する。"""

    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    category: Mapped[str] = mapped_column(String(50), default="その他")
    prerequisites: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(20), default="catalog")  # catalog / ai

    aliases: Mapped[list[TopicAlias]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    level_guides: Mapped[list[LevelGuide]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", order_by="LevelGuide.level"
    )
    materials: Mapped[list[Material]] = relationship(back_populates="topic", cascade="all, delete-orphan")


class TopicAlias(Base):
    __tablename__ = "topic_aliases"
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    alias: Mapped[str] = mapped_column(String(200), index=True)
    topic: Mapped[Topic] = relationship(back_populates="aliases")


class LevelGuide(Base):
    __tablename__ = "level_guides"
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    level: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    topic: Mapped[Topic] = relationship(back_populates="level_guides")


class Material(Base):
    __tablename__ = "materials"
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # official_doc / official_learning / article / video / roadmap / exercise
    type: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(
        String(30), default="catalog"
    )  # catalog / tavily / qiita / youtube / demo / ai
    reference_hours: Mapped[float] = mapped_column(Float, default=0)
    reference_basis: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(20), default="approved")  # approved / ai_pending / rejected
    url_check: Mapped[str] = mapped_column(String(30), default="未確認")
    supplementary: Mapped[bool] = mapped_column(default=False)  # 動画など補助教材
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    topic: Mapped[Topic] = relationship(back_populates="materials")
    sections: Mapped[list[MaterialSection]] = relationship(
        back_populates="material", cascade="all, delete-orphan", order_by="MaterialSection.order"
    )


class MaterialSection(Base):
    __tablename__ = "material_sections"
    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    order: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    level_from: Mapped[int] = mapped_column(Integer, default=1)
    level_to: Mapped[int] = mapped_column(Integer, default=5)
    est_hours: Mapped[float] = mapped_column(Float, default=1)
    material: Mapped[Material] = relationship(back_populates="sections")


class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_level: Mapped[int] = mapped_column(Integer)
    target_level: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[dt.date] = mapped_column(Date)
    end_date: Mapped[dt.date] = mapped_column(Date)
    hours_per_day: Mapped[float] = mapped_column(Float)
    excluded_weekdays: Mapped[list] = mapped_column(JSON, default=list)  # 0=月 … 6=日
    status: Mapped[str] = mapped_column(String(20), default="proposed")  # proposed / active / completed
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped[User] = relationship()
    topic: Mapped[Topic] = relationship()
    plan_materials: Mapped[list[PlanMaterial]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlanMaterial.order"
    )
    tasks: Mapped[list[Task]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="[Task.date, Task.order]"
    )
    ai_note: Mapped[PlanAINote | None] = relationship(
        back_populates="plan", cascade="all, delete-orphan", uselist=False
    )


class PlanMaterial(Base):
    __tablename__ = "plan_materials"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    order: Mapped[int] = mapped_column(Integer)
    reference_hours: Mapped[float] = mapped_column(Float)  # このプランで AI が使った参考時間
    reference_basis: Mapped[str] = mapped_column(String(300))
    plan: Mapped[Plan] = relationship(back_populates="plan_materials")
    material: Mapped[Material] = relationship()


class PlanAINote(Base):
    """AI の判断（順番の理由・重点・後回し・配分）と確認結果。"""

    __tablename__ = "plan_ai_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), unique=True)
    provider: Mapped[str] = mapped_column(String(30))
    order_reason: Mapped[str] = mapped_column(Text, default="")
    focus: Mapped[str] = mapped_column(Text, default="")
    dropped: Mapped[list] = mapped_column(JSON, default=list)
    allocation: Mapped[dict] = mapped_column(JSON, default=dict)
    check_passed: Mapped[bool] = mapped_column(default=False)
    check_issues: Mapped[list] = mapped_column(JSON, default=list)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    plan: Mapped[Plan] = relationship(back_populates="ai_note")


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), nullable=True)
    date: Mapped[dt.date] = mapped_column(Date)
    order: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(300))
    type: Mapped[str] = mapped_column(String(20))  # learn / review / exercise / video / buffer
    planned_hours: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="todo")  # todo / done / skipped
    actual_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan: Mapped[Plan] = relationship(back_populates="tasks")


class ApiUsage(Base):
    """外部 API の利用回数（無料枠の管理用）。period は "2026-11"（月）や "2026-11-13"（日）など。"""

    __tablename__ = "api_usage"
    __table_args__ = (UniqueConstraint("provider", "period"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(30))
    period: Mapped[str] = mapped_column(String(20))
    count: Mapped[int] = mapped_column(Integer, default=0)
    limit: Mapped[int] = mapped_column(Integer)
