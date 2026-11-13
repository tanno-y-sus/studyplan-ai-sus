"""プランの作成・表示・リスケ。"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.config import settings
from app.models import Material, Plan, PlanAINote, PlanMaterial, Task, User
from app.schemas import (
    AINoteOut,
    AITask,
    Allocation,
    AvailabilityOut,
    MaterialInfo,
    MaterialOut,
    PlanCreate,
    PlanOut,
    PlanSummary,
    RescheduleChange,
    RescheduleContext,
    ReschedulePreview,
    ScheduleContext,
    SectionInfo,
    TaskOut,
)
from app.services.calendar import available_dates, count_all_days
from app.services.materials import materials_for_topic
from app.services.normalize import resolve_topic
from app.services.schedule import generate_with_checks, reschedule_with_checks


def availability(plan_or_data) -> AvailabilityOut:
    days = available_dates(plan_or_data.start_date, plan_or_data.end_date, plan_or_data.excluded_weekdays)
    total = count_all_days(plan_or_data.start_date, plan_or_data.end_date)
    return AvailabilityOut(
        available_days=len(days),
        excluded_days=total - len(days),
        max_hours=len(days) * plan_or_data.hours_per_day,
    )


def material_info(m: Material, current: int, target: int) -> MaterialInfo:
    """AI に渡す教材情報（個人情報は含めない）。"""
    sections = [
        SectionInfo(title=s.title, est_hours=s.est_hours, level_from=s.level_from, level_to=s.level_to)
        for s in m.sections
    ]
    has_basis = m.reference_basis and not m.reference_basis.startswith("AI推定")
    return MaterialInfo(
        material_id=m.id,
        title=m.title,
        type=m.type,
        url=m.url,
        supplementary=m.supplementary,
        reference_hours=m.reference_hours if (has_basis or not sections) else None,
        reference_basis=m.reference_basis or None,
        sections=sections,
    )


def create_plan(db: Session, user: User, data: PlanCreate, ai: AIProvider) -> Plan:
    topic = resolve_topic(db, data.topic, ai)
    dates = available_dates(data.start_date, data.end_date, data.excluded_weekdays)
    if not dates:
        raise ValueError("期間内に学習できる日がありません。期間や学習しない曜日を見直してください")
    materials, notes = materials_for_topic(db, topic, data.current_level, data.target_level, ai)

    ctx = ScheduleContext(
        topic=topic.name,
        current_level=data.current_level,
        target_level=data.target_level,
        purpose=data.purpose,
        start_date=data.start_date,
        end_date=data.end_date,
        hours_per_day=data.hours_per_day,
        available_dates=dates,
        materials=[material_info(m, data.current_level, data.target_level) for m in materials],
    )
    result = generate_with_checks(ai, ctx)

    plan = Plan(
        user_id=user.id,
        topic_id=topic.id,
        purpose=data.purpose,
        current_level=data.current_level,
        target_level=data.target_level,
        start_date=data.start_date,
        end_date=data.end_date,
        hours_per_day=data.hours_per_day,
        excluded_weekdays=data.excluded_weekdays,
        status="proposed",
        warnings=list(notes),
    )
    db.add(plan)
    schedule = result.schedule
    times = {t.material_id: t for t in schedule.materials} if schedule else {}
    for i, m in enumerate(materials):
        t = times.get(m.id)
        plan.plan_materials.append(
            PlanMaterial(
                material_id=m.id,
                order=i,
                reference_hours=t.reference_hours if t else m.reference_hours,
                reference_basis=t.reference_basis if t else m.reference_basis,
            )
        )
    plan.ai_note = PlanAINote(
        provider=ai.name,
        order_reason=schedule.order_reason if schedule else "",
        focus=schedule.focus if schedule else "",
        dropped=[d.model_dump() for d in schedule.dropped] if schedule else [],
        allocation=schedule.allocation.model_dump() if schedule else {},
        check_passed=result.passed,
        check_issues=result.issues,
        retries=result.retries,
    )
    if schedule:
        _set_tasks(plan, [(d.date, d.tasks) for d in schedule.days])
    if not result.passed:
        plan.warnings.append("AI のスケジュールに問題が残っています。該当する日を確認して調整してください")
    db.flush()
    return plan


def _set_tasks(plan: Plan, days: list[tuple[dt.date, list[AITask]]], keep: list[Task] | None = None) -> None:
    plan.tasks = list(keep or [])
    for day, tasks in days:
        for i, t in enumerate(tasks):
            plan.tasks.append(
                Task(
                    date=day,
                    order=i,
                    title=t.title,
                    type=t.type,
                    planned_hours=t.hours,
                    material_id=t.material_id,
                )
            )


def progress(plan: Plan, today: dt.date | None = None) -> dict:
    today = today or settings.today()
    tasks = [t for t in plan.tasks if t.type != "buffer"]
    planned = sum(t.planned_hours for t in tasks)
    done = sum(t.planned_hours for t in tasks if t.status == "done")
    due = sum(t.planned_hours for t in tasks if t.date < today)
    done_due = sum(t.planned_hours for t in tasks if t.date < today and t.status == "done")
    buffer_left = sum(t.planned_hours for t in plan.tasks if t.type == "buffer" and t.date >= today)
    actual = sum(t.actual_hours or 0 for t in plan.tasks)
    return {
        "planned_hours": round(planned, 2),
        "done_hours": round(done, 2),
        "percent": round(done / planned * 100) if planned else 0,
        "delay_hours": round(due - done_due, 2),
        "actual_hours": round(actual, 2),
        "buffer_left_hours": round(buffer_left, 2),
        "today": today.isoformat(),
    }


def to_out(plan: Plan) -> PlanOut:
    note = plan.ai_note
    return PlanOut(
        id=plan.id,
        user_id=plan.user_id,
        user_name=plan.user.name,
        topic=plan.topic.name,
        purpose=plan.purpose,
        current_level=plan.current_level,
        target_level=plan.target_level,
        start_date=plan.start_date,
        end_date=plan.end_date,
        hours_per_day=plan.hours_per_day,
        excluded_weekdays=plan.excluded_weekdays,
        status=plan.status,
        warnings=plan.warnings or [],
        availability=availability(plan),
        materials=[
            MaterialOut(
                id=pm.material.id,
                title=pm.material.title,
                url=pm.material.url,
                type=pm.material.type,
                source=pm.material.source,
                status=pm.material.status,
                supplementary=pm.material.supplementary,
                url_check=pm.material.url_check,
                reference_hours=pm.reference_hours,
                reference_basis=pm.reference_basis,
                sections=[s.title for s in pm.material.sections],
            )
            for pm in plan.plan_materials
        ],
        ai_note=AINoteOut(
            provider=note.provider,
            order_reason=note.order_reason,
            focus=note.focus,
            dropped=note.dropped,
            allocation=Allocation(**note.allocation) if note.allocation else None,
            check_passed=note.check_passed,
            check_issues=note.check_issues,
            retries=note.retries,
        )
        if note
        else None,
        tasks=[TaskOut.model_validate(t) for t in plan.tasks],
        progress=progress(plan),
    )


def to_summary(plan: Plan) -> PlanSummary:
    return PlanSummary(
        id=plan.id,
        topic=plan.topic.name,
        current_level=plan.current_level,
        target_level=plan.target_level,
        start_date=plan.start_date,
        end_date=plan.end_date,
        hours_per_day=plan.hours_per_day,
        status=plan.status,
        progress=progress(plan),
    )


# ---------------------------------------------------------------- リスケ（02-6）


def reschedule_preview(plan: Plan, ai: AIProvider, today: dt.date | None = None) -> ReschedulePreview:
    today = today or settings.today()
    pending = [t for t in plan.tasks if t.status == "todo"]
    ctx = RescheduleContext(
        topic=plan.topic.name,
        today=today,
        end_date=plan.end_date,
        hours_per_day=plan.hours_per_day,
        available_dates=available_dates(max(today, plan.start_date), plan.end_date, plan.excluded_weekdays),
        pending_tasks=[
            AITask(type=t.type, title=t.title, hours=t.planned_hours, material_id=t.material_id)
            for t in pending
        ],
    )
    result = reschedule_with_checks(ai, ctx)
    days = result.plan.days if result.plan else []
    old_dates = {}
    for t in pending:
        old_dates.setdefault(t.title, t.date)
    # タスクごとに1行（日をまたいで分割されたものは合計時間と最初の日で表示）
    first_new: dict[str, dt.date] = {}
    total_hours: dict[str, float] = {}
    for d in days:
        for t in d.tasks:
            first_new.setdefault(t.title, d.date)
            total_hours[t.title] = total_hours.get(t.title, 0) + t.hours
    changes = [
        RescheduleChange(title=title, hours=total_hours[title], from_date=old_dates.get(title), to_date=new)
        for title, new in first_new.items()
        if old_dates.get(title) != new
    ]
    return ReschedulePreview(
        today=today,
        pending_hours=round(sum(t.planned_hours for t in pending if t.type != "buffer"), 2),
        remaining_days=len(ctx.available_dates),
        changes=changes,
        dropped=result.plan.dropped if result.plan else [],
        advice=result.plan.advice if result.plan else "AI からリスケ案を受け取れませんでした",
        check_passed=result.plan is not None and not result.issues,
        check_issues=result.issues,
        days=days,
    )


def reschedule_apply(plan: Plan, preview: ReschedulePreview) -> None:
    if not preview.check_passed:
        raise ValueError("確認で問題が見つかったリスケ案は適用できません")
    keep = [t for t in plan.tasks if t.status != "todo"]
    _set_tasks(plan, [(d.date, d.tasks) for d in preview.days], keep=keep)
