"""AI によるスケジュール作成と確認（02-4）。

AI が作る → プログラムで確認 → 問題があれば問題点を伝えて作り直し（最大2回）→ それでもだめなら警告付きで返す。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.base import AIError, AIProvider
from app.config import settings
from app.schemas import AIReschedule, AISchedule, RescheduleContext, ScheduleContext
from app.services.validator import validate_days


@dataclass
class ScheduleResult:
    schedule: AISchedule | None
    issues: list[str] = field(default_factory=list)
    retries: int = 0

    @property
    def passed(self) -> bool:
        return self.schedule is not None and not self.issues


def generate_with_checks(
    ai: AIProvider, ctx: ScheduleContext, max_retries: int = settings.max_ai_retries
) -> ScheduleResult:
    required = [m.material_id for m in ctx.materials]
    last: ScheduleResult = ScheduleResult(schedule=None, issues=["AI から結果を受け取れませんでした"])
    for attempt in range(max_retries + 1):
        try:
            schedule = ai.generate_schedule(ctx)
        except AIError as e:
            last = ScheduleResult(schedule=last.schedule, issues=[str(e)], retries=attempt)
            ctx = ctx.model_copy(update={"feedback": [str(e)]})
            continue
        issues = validate_days(
            schedule.days,
            start=ctx.start_date,
            end=ctx.end_date,
            available=ctx.available_dates,
            hours_per_day=ctx.hours_per_day,
            required_material_ids=required,
        )
        last = ScheduleResult(schedule=schedule, issues=issues, retries=attempt)
        if not issues:
            return last
        ctx = ctx.model_copy(update={"feedback": issues})
    return last


@dataclass
class RescheduleResult:
    plan: AIReschedule | None
    issues: list[str] = field(default_factory=list)
    retries: int = 0


def reschedule_with_checks(
    ai: AIProvider, ctx: RescheduleContext, max_retries: int = settings.max_ai_retries
) -> RescheduleResult:
    available = [d for d in ctx.available_dates if d >= ctx.today]
    last = RescheduleResult(plan=None, issues=["AI から結果を受け取れませんでした"])
    for attempt in range(max_retries + 1):
        try:
            plan = ai.reschedule(ctx)
        except AIError as e:
            last = RescheduleResult(plan=last.plan, issues=[str(e)], retries=attempt)
            ctx = ctx.model_copy(update={"feedback": [str(e)]})
            continue
        issues = validate_days(
            plan.days, start=ctx.today, end=ctx.end_date, available=available, hours_per_day=ctx.hours_per_day
        )
        last = RescheduleResult(plan=plan, issues=issues, retries=attempt)
        if not issues:
            return last
        ctx = ctx.model_copy(update={"feedback": issues})
    return last
