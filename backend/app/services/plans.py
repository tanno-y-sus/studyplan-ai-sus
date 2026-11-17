"""プランの作成・表示・リスケ。"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.config import settings
from app.models import Material, Plan, PlanAINote, PlanMaterial, PlanTopic, Task, User
from app.schemas import (
    PURPOSE_LABEL,
    AINoteOut,
    AITask,
    Allocation,
    AreaProgress,
    AvailabilityOut,
    Deadline,
    ExamArea,
    MaterialInfo,
    MaterialOut,
    PlanCreate,
    PlanOut,
    PlanSummary,
    PlanTopicOut,
    RescheduleChange,
    RescheduleContext,
    ReschedulePreview,
    ScheduleContext,
    SectionInfo,
    TaskOut,
    TaskUpdate,
    TaskUpdateOut,
    TopicAllocation,
    TopicGoal,
)
from app.services.calendar import available_dates, count_all_days
from app.services.materials import materials_for_topic
from app.services.normalize import resolve_topic
from app.services.schedule import generate_with_checks, reschedule_with_checks
from app.services.skills import checklist_for, exam_areas_for, levels_from_checks


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
        topic=m.topic.name,
        title=m.title,
        type=m.type,
        url=m.url,
        supplementary=m.supplementary,
        reference_hours=m.reference_hours if (has_basis or not sections) else None,
        reference_basis=m.reference_basis or None,
        sections=sections,
    )


def _purpose_text(purpose: str, note: str | None) -> str:
    label = PURPOSE_LABEL.get(purpose, purpose)
    return f"{label}（{note}）" if note else label


def create_plan(db: Session, user: User, data: PlanCreate, ai: AIProvider) -> Plan:
    dates = available_dates(data.start_date, data.end_date, data.excluded_weekdays)
    if not dates:
        raise ValueError("期間内に学習できる日がありません。期間や学習しない曜日を見直してください")

    plan_topics: list[PlanTopic] = []
    goals: list[TopicGoal] = []
    materials: list[Material] = []
    notes: list[str] = []
    seen_topics: set[int] = set()
    for i, item in enumerate(data.topics):
        topic = resolve_topic(db, item.topic, ai, item.kind)
        if topic.id in seen_topics:
            raise ValueError(f"「{topic.name}」が2回入っています")
        seen_topics.add(topic.id)
        if item.kind == "exam":
            # 資格試験：出題範囲を網羅する。レベルのチェックは使わない
            areas = exam_areas_for(db, topic, ai)
            exam_date = item.exam_date or data.end_date
            if not any(d <= exam_date for d in dates):
                raise ValueError(f"「{topic.name}」の試験日までに学習できる日がありません")
            if any(a.status != "approved" for a in areas):
                notes.append(f"「{topic.name}」の出題範囲は AI が作った一覧です（育成担当の確認前）")
            current, target = 1, 5
            purpose, purpose_note, can_do, item_goals = "exam", None, [], []
            area_info = [
                ExamArea(name=a.name, description=a.description, weight=a.weight, est_hours=a.est_hours)
                for a in areas
            ]
        else:
            skills = checklist_for(db, topic, ai)
            current, target = levels_from_checks(skills, item.can_do, item.goals)
            exam_date = None
            purpose, purpose_note, can_do, item_goals = (
                item.purpose,
                item.purpose_note,
                item.can_do,
                item.goals,
            )
            area_info = []
        plan_topics.append(
            PlanTopic(
                topic_id=topic.id,
                order=i,
                kind=item.kind,
                exam_date=exam_date,
                purpose=purpose,
                purpose_note=purpose_note,
                can_do=can_do,
                goals=item_goals,
                current_level=current,
                target_level=target,
            )
        )
        goals.append(
            TopicGoal(
                topic=topic.name,
                kind=item.kind,
                exam_date=exam_date,
                areas=area_info,
                purpose=_purpose_text(purpose, purpose_note),
                can_do=can_do,
                goals=item_goals,
                current_level=current,
                target_level=target,
            )
        )
        found, topic_notes = materials_for_topic(
            db, topic, current, target, ai, goals=item_goals or None, kind=item.kind
        )
        materials.extend(found)
        notes.extend(topic_notes)

    ctx = ScheduleContext(
        topics=goals,
        start_date=data.start_date,
        end_date=data.end_date,
        hours_per_day=data.hours_per_day,
        available_dates=dates,
        materials=[material_info(m, 0, 0) for m in materials],
    )
    result = generate_with_checks(ai, ctx)

    plan = Plan(
        user_id=user.id,
        start_date=data.start_date,
        end_date=data.end_date,
        hours_per_day=data.hours_per_day,
        excluded_weekdays=data.excluded_weekdays,
        status="proposed",
        warnings=list(notes),
    )
    plan.plan_topics = plan_topics
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
        strategy=schedule.strategy if schedule else "",
        topic_allocation=[a.model_dump() for a in schedule.topic_allocation] if schedule else [],
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
                    area=t.area,
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


def topic_names(plan: Plan) -> str:
    return " ＋ ".join(pt.topic.name for pt in plan.plan_topics)


def _task_topic(t: Task) -> str | None:
    return t.material.topic.name if t.material is not None else None


def task_out(t: Task) -> TaskOut:
    out = TaskOut.model_validate(t)
    out.topic = _task_topic(t)
    return out


def topics_out(plan: Plan) -> list[PlanTopicOut]:
    out = []
    for pt in plan.plan_topics:
        tasks = [t for t in plan.tasks if t.type != "buffer" and _task_topic(t) == pt.topic.name]
        planned = sum(t.planned_hours for t in tasks)
        done = sum(t.planned_hours for t in tasks if t.status == "done")
        areas = []
        if pt.kind == "exam":
            for a in pt.topic.areas:
                mine = [t for t in tasks if t.area == a.name]
                areas.append(
                    AreaProgress(
                        name=a.name,
                        weight=a.weight,
                        planned_hours=round(sum(t.planned_hours for t in mine), 2),
                        done_hours=round(sum(t.planned_hours for t in mine if t.status == "done"), 2),
                    )
                )
        out.append(
            PlanTopicOut(
                name=pt.topic.name,
                kind=pt.kind,
                exam_date=pt.exam_date,
                areas=areas,
                purpose=pt.purpose,
                purpose_label=PURPOSE_LABEL.get(pt.purpose, pt.purpose),
                purpose_note=pt.purpose_note,
                can_do=pt.can_do or [],
                goals=pt.goals or [],
                current_level=pt.current_level,
                target_level=pt.target_level,
                planned_hours=round(planned, 2),
                done_hours=round(done, 2),
                percent=round(done / planned * 100) if planned else 0,
            )
        )
    return out


def to_out(plan: Plan) -> PlanOut:
    note = plan.ai_note
    return PlanOut(
        id=plan.id,
        user_id=plan.user_id,
        user_name=plan.user.name,
        topic=topic_names(plan),
        topics=topics_out(plan),
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
                topic=pm.material.topic.name,
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
            strategy=note.strategy or "",
            topic_allocation=[TopicAllocation(**a) for a in (note.topic_allocation or [])],
            dropped=note.dropped,
            allocation=Allocation(**note.allocation) if note.allocation else None,
            check_passed=note.check_passed,
            check_issues=note.check_issues,
            retries=note.retries,
        )
        if note
        else None,
        tasks=[task_out(t) for t in plan.tasks],
        progress=progress(plan),
    )


def to_summary(plan: Plan) -> PlanSummary:
    return PlanSummary(
        id=plan.id,
        topic=topic_names(plan),
        topics=topics_out(plan),
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
        topic=topic_names(plan),
        today=today,
        end_date=plan.end_date,
        hours_per_day=plan.hours_per_day,
        available_dates=available_dates(max(today, plan.start_date), plan.end_date, plan.excluded_weekdays),
        pending_tasks=[
            AITask(type=t.type, title=t.title, hours=t.planned_hours, material_id=t.material_id, area=t.area)
            for t in pending
        ],
        deadlines=[
            Deadline(
                topic=pt.topic.name,
                date=pt.exam_date,
                material_ids=[
                    pm.material_id for pm in plan.plan_materials if pm.material.topic_id == pt.topic_id
                ],
            )
            for pt in plan.plan_topics
            if pt.kind == "exam" and pt.exam_date
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


# ---------------------------------------------------------------- タスクの完了と実績（S02・S06）
REMAINDER_SUFFIX = "（残り）"
EPS = 1e-6


def _merge_remainder(plan: Plan, task: Task) -> None:
    """以前作った「残り」のタスクがまだ未完了なら、元のタスクに戻す（実績の入れ直し・完了の取り消し用）。"""
    for r in [t for t in plan.tasks if t.remainder_of_id == task.id and t.status == "todo"]:
        task.planned_hours = round(task.planned_hours + r.planned_hours, 2)
        plan.tasks.remove(r)


def update_task(db: Session, plan: Plan, task: Task, data: TaskUpdate) -> TaskUpdateOut:
    """完了チェック・実績の入力。

    - 完了チェック（status=done、実績なし）：予定どおり終わった扱い（実績＝予定時間）
    - 実績が予定以上：その時間で完了
    - 実績が予定より少ない：その時間で完了にし、足りない分を「○○（残り）」として未完了で残す
      （画面はこのあと AI のリスケ案を作り、確認してから反映する）
    - 完了の取り消し（status=todo）・実績 0：未完了に戻し、実績を空にする（残りのタスクは元に戻す）
    """
    if data.memo is not None:
        task.memo = data.memo
    remainder: Task | None = None
    shortfall = 0.0

    def undo() -> None:
        _merge_remainder(plan, task)
        task.status = "todo"
        task.actual_hours = None
        task.completed_at = None

    def complete(actual: float) -> None:
        task.status = "done"
        task.actual_hours = round(actual, 2)
        task.completed_at = dt.datetime.now(dt.UTC)

    if data.actual_hours is not None:
        if data.actual_hours <= EPS:
            undo()
        else:
            _merge_remainder(plan, task)
            planned = task.planned_hours
            if data.actual_hours + EPS >= planned or task.type == "buffer":
                complete(data.actual_hours)
            else:
                shortfall = round(planned - data.actual_hours, 2)
                task.planned_hours = round(data.actual_hours, 2)
                complete(data.actual_hours)
                base = task.title.removesuffix(REMAINDER_SUFFIX)
                remainder = Task(
                    date=task.date,
                    order=task.order + 1,
                    title=f"{base}{REMAINDER_SUFFIX}",
                    type=task.type,
                    planned_hours=shortfall,
                    material_id=task.material_id,
                    area=task.area,
                    remainder_of_id=task.id,
                )
                plan.tasks.append(remainder)
    elif data.status == "done":
        if task.status != "done":
            complete(task.planned_hours)
    elif data.status == "todo":
        undo()
    elif data.status == "skipped":
        task.status = "skipped"

    db.flush()
    return TaskUpdateOut(
        task=task_out(task),
        remainder=task_out(remainder) if remainder is not None else None,
        shortfall_hours=shortfall,
    )
