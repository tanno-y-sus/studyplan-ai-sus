"""AI によるスケジュール作成と確認（02-4）。

AI が作る → プログラムで確認 → 問題があれば問題点を伝えて作り直し（最大2回）→ それでもだめなら警告付きで返す。
AI を使えない場合（通信できない・キーが正しくない・無料枠の上限）は、作り直しても同じなのでその場で止める。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.base import AIError, AIProvider, AIUnavailable
from app.config import settings
from app.schemas import AIReschedule, AISchedule, RescheduleContext, ScheduleContext
from app.services.validator import ExamRule, validate_days


@dataclass
class ScheduleResult:
    schedule: AISchedule | None
    issues: list[str] = field(default_factory=list)
    retries: int = 0

    @property
    def passed(self) -> bool:
        return self.schedule is not None and not self.issues


def exam_rules(ctx: ScheduleContext) -> list[ExamRule]:
    rules = []
    for g in ctx.topics:
        if g.kind != "exam":
            continue
        rules.append(
            ExamRule(
                topic=g.topic,
                exam_date=g.exam_date or ctx.end_date,
                areas=[a.name for a in g.areas],
                material_ids={m.material_id for m in ctx.materials if m.topic == g.topic},
            )
        )
    return rules


def generate_with_checks(
    ai: AIProvider, ctx: ScheduleContext, max_retries: int = settings.max_ai_retries
) -> ScheduleResult:
    required = [m.material_id for m in ctx.materials]
    rules = exam_rules(ctx)
    last: ScheduleResult = ScheduleResult(schedule=None, issues=["AI から結果を受け取れませんでした"])
    for attempt in range(max_retries + 1):
        try:
            schedule = ai.generate_schedule(ctx)
        except AIUnavailable:
            raise
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
            exam_rules=rules,
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
        except AIUnavailable:
            raise
        except AIError as e:
            last = RescheduleResult(plan=last.plan, issues=[str(e)], retries=attempt)
            ctx = ctx.model_copy(update={"feedback": [str(e)]})
            continue
        issues = validate_days(
            plan.days, start=ctx.today, end=ctx.end_date, available=available, hours_per_day=ctx.hours_per_day
        )
        issues += _deadline_issues(plan.days, ctx)
        last = RescheduleResult(plan=plan, issues=issues, retries=attempt)
        if not issues:
            return last
        ctx = ctx.model_copy(update={"feedback": issues})
    return last


def _deadline_issues(days, ctx: RescheduleContext) -> list[str]:
    """リスケで、資格試験のタスクを試験日より後に入れていないか。"""
    issues = []
    for d in ctx.deadlines:
        late = [
            f"{day.date}「{t.title}」"
            for day in days
            if day.date > d.date
            for t in day.tasks
            if t.material_id in d.material_ids and t.type != "buffer"
        ]
        if late:
            issues.append(f"「{d.topic}」の試験日（{d.date}）より後に予定があります：{'、'.join(late[:5])}")
    return issues
