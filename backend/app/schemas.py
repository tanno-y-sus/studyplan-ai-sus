"""API とAI のデータ形式（Pydantic）。"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TaskType = Literal["learn", "review", "exercise", "video", "buffer"]


# ---------------------------------------------------------------- AI の入出力


class SectionInfo(BaseModel):
    title: str
    est_hours: float
    level_from: int = 1
    level_to: int = 5


class MaterialInfo(BaseModel):
    """AI に渡す教材情報。氏名などの個人情報は含めない。"""

    material_id: int
    title: str
    type: str
    url: str | None = None
    supplementary: bool = False
    reference_hours: float | None = None  # 記載や動画の長さから分かった参考時間（不明なら None）
    reference_basis: str | None = None
    sections: list[SectionInfo] = Field(default_factory=list)


class ScheduleContext(BaseModel):
    """スケジュール作成のために AI に渡す情報（02-4「AI に渡す情報」）。"""

    topic: str
    current_level: int
    target_level: int
    purpose: str | None = None
    start_date: dt.date
    end_date: dt.date
    hours_per_day: float
    available_dates: list[dt.date]
    materials: list[MaterialInfo]
    feedback: list[str] = Field(default_factory=list)  # 作り直し時に伝える問題点


class AITask(BaseModel):
    type: TaskType
    title: str
    hours: float
    material_id: int | None = None


class AIDay(BaseModel):
    date: dt.date
    tasks: list[AITask]


class AIMaterialTime(BaseModel):
    material_id: int
    reference_hours: float
    reference_basis: str


class AIDropped(BaseModel):
    title: str
    reason: str


class Allocation(BaseModel):
    learn: float
    review: float
    buffer: float


class AISchedule(BaseModel):
    """AI が返すスケジュール。この形式に沿っているかも確認対象。"""

    materials: list[AIMaterialTime]
    allocation: Allocation
    order_reason: str
    focus: str
    dropped: list[AIDropped] = Field(default_factory=list)
    days: list[AIDay]


class RescheduleContext(BaseModel):
    topic: str
    today: dt.date
    end_date: dt.date
    hours_per_day: float
    available_dates: list[dt.date]
    pending_tasks: list[AITask]
    feedback: list[str] = Field(default_factory=list)


class AIReschedule(BaseModel):
    days: list[AIDay]
    dropped: list[AIDropped] = Field(default_factory=list)
    advice: str


class TopicNormalization(BaseModel):
    name: str
    category: str
    is_it: bool
    prerequisites: list[str] = Field(default_factory=list)
    too_broad: bool = False
    suggestions: list[str] = Field(default_factory=list)


class SearchCandidate(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source: str  # tavily / qiita / youtube / demo
    type: str  # official_doc / article / video / ...
    duration_minutes: float | None = None


class MaterialChoice(BaseModel):
    candidate_index: int
    reason: str
    sections: list[SectionInfo] = Field(default_factory=list)
    reference_hours: float | None = None
    reference_basis: str | None = None


class MaterialSelection(BaseModel):
    chosen: list[MaterialChoice]
    exercise_title: str
    exercise_description: str
    exercise_hours: float


# ---------------------------------------------------------------- API


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    role: str


class TopicSuggestion(BaseModel):
    name: str
    category: str
    in_catalog: bool


class LevelGuideOut(BaseModel):
    level: int
    description: str


class PlanCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    purpose: str | None = Field(default=None, max_length=500)
    current_level: int = Field(ge=1, le=5)
    target_level: int = Field(ge=1, le=5)
    start_date: dt.date
    end_date: dt.date
    hours_per_day: float = Field(ge=0.5, le=8)
    excluded_weekdays: list[int] = Field(default_factory=lambda: [5, 6])

    @model_validator(mode="after")
    def _check(self) -> PlanCreate:
        if self.target_level < self.current_level:
            raise ValueError("目標レベルは現在のレベル以上にしてください")
        if self.end_date <= self.start_date:
            raise ValueError("終了日は開始日より後にしてください")
        if any(w < 0 or w > 6 for w in self.excluded_weekdays):
            raise ValueError("学習しない曜日の指定が正しくありません")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("期間は1年以内にしてください")
        return self


class AvailabilityOut(BaseModel):
    available_days: int
    excluded_days: int
    max_hours: float


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: dt.date
    title: str
    type: str
    planned_hours: float
    status: str
    actual_hours: float | None
    memo: str | None
    material_id: int | None


class TaskUpdate(BaseModel):
    status: Literal["todo", "done", "skipped"] | None = None
    actual_hours: float | None = Field(default=None, ge=0, le=24)
    memo: str | None = Field(default=None, max_length=1000)


class MaterialOut(BaseModel):
    id: int
    title: str
    url: str | None
    type: str
    source: str
    status: str
    supplementary: bool
    url_check: str
    reference_hours: float
    reference_basis: str
    sections: list[str]


class AINoteOut(BaseModel):
    provider: str
    order_reason: str
    focus: str
    dropped: list[AIDropped]
    allocation: Allocation | None
    check_passed: bool
    check_issues: list[str]
    retries: int


class PlanOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    topic: str
    purpose: str | None
    current_level: int
    target_level: int
    start_date: dt.date
    end_date: dt.date
    hours_per_day: float
    excluded_weekdays: list[int]
    status: str
    warnings: list[str]
    availability: AvailabilityOut
    materials: list[MaterialOut]
    ai_note: AINoteOut | None
    tasks: list[TaskOut]
    progress: dict


class PlanSummary(BaseModel):
    id: int
    topic: str
    current_level: int
    target_level: int
    start_date: dt.date
    end_date: dt.date
    hours_per_day: float
    status: str
    progress: dict


class RescheduleRequest(BaseModel):
    today: dt.date | None = None


class RescheduleChange(BaseModel):
    title: str
    hours: float
    from_date: dt.date | None
    to_date: dt.date


class ReschedulePreview(BaseModel):
    today: dt.date
    pending_hours: float
    remaining_days: int
    changes: list[RescheduleChange]
    dropped: list[AIDropped]
    advice: str
    check_passed: bool
    check_issues: list[str]
    days: list[AIDay]


class ReviewDecision(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)


class UsageOut(BaseModel):
    provider: str
    period: str
    count: int
    limit: int
