from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.base import AIError, AIProvider, AIUnavailable
from app.ai.factory import choose_ai
from app.api.deps import ai_provider, current_user, require_role
from app.config import settings
from app.db import get_db
from app.models import ApiUsage, Material, Plan, Task, Topic, TopicAlias, User
from app.schemas import (
    AIStatusOut,
    AvailabilityOut,
    ChecklistOut,
    PlanCreate,
    PlanOut,
    PlanSummary,
    ReschedulePreview,
    RescheduleRequest,
    ReviewDecision,
    SkillItem,
    TaskUpdate,
    TaskUpdateOut,
    TopicSuggestion,
    UsageOut,
)
from app.search.router import search_status
from app.services import plans as plan_service
from app.services.calendar import available_dates, count_all_days
from app.services.normalize import TopicError, resolve_topic
from app.services.skills import PURPOSE_LEVELS, checklist_for
from app.services.usage import latest_usage, period_key

router = APIRouter()


# ---------------------------------------------------------------- 共通
@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "ai_provider": settings.ai_provider,
        "search_providers": settings.search_providers,
        "today": settings.today().isoformat(),
    }


@router.get("/ai/status", response_model=AIStatusOut)
def ai_status(db: Session = Depends(get_db), user: User = Depends(current_user)):
    choice = choose_ai(settings)
    search, missing = search_status(settings)
    out = AIStatusOut(
        provider=choice.provider,
        model=choice.model,
        configured=settings.ai_provider,
        reason=choice.reason,
        search=search,
        search_missing=missing,
    )
    if choice.provider == "gemini":
        row = db.scalar(
            select(ApiUsage).where(ApiUsage.provider == "gemini", ApiUsage.period == period_key("day"))
        )
        out.today_count = row.count if row else 0
        out.daily_limit = settings.gemini_daily_limit
    return out


# ---------------------------------------------------------------- 単元（S03）
@router.get("/topics/suggest", response_model=list[TopicSuggestion])
def suggest_topics(
    q: str = Query(default="", max_length=100),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    key = f"%{q.strip().lower()}%"
    topics = db.scalars(
        select(Topic)
        .outerjoin(TopicAlias)
        .where((func.lower(Topic.name).like(key)) | (func.lower(TopicAlias.alias).like(key)))
        .distinct()
        .order_by(Topic.name)
        .limit(8)
    ).all()
    return [
        TopicSuggestion(
            name=t.name, category=t.category, in_catalog=any(m.status == "approved" for m in t.materials)
        )
        for t in topics
    ]


@router.get("/topics/checklist", response_model=ChecklistOut)
def topic_checklist(
    topic: str = Query(min_length=1, max_length=200),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
    ai: AIProvider = Depends(ai_provider),
):
    """単元名をそろえ、「できること」チェックリストを返す（なければ AI が作って保存する）。"""
    try:
        found = resolve_topic(db, topic, ai)
        skills = checklist_for(db, found, ai)
    except TopicError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail={"message": str(e), "suggestions": e.suggestions}) from e
    except AIError as e:
        if isinstance(e, AIUnavailable):
            db.rollback()
            raise
        db.rollback()
        raise HTTPException(status_code=422, detail={"message": str(e), "suggestions": []}) from e
    db.commit()
    return ChecklistOut(
        topic=found.name,
        category=found.category,
        items=[SkillItem(text=s.text, level=s.level) for s in skills],
        purpose_levels=PURPOSE_LEVELS,
    )


@router.get("/availability", response_model=AvailabilityOut)
def availability(
    start_date: dt.date,
    end_date: dt.date,
    hours_per_day: float,
    excluded_weekdays: str = Query(default="5,6"),
    _: User = Depends(current_user),
):
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="終了日は開始日より後にしてください")
    excluded = [int(x) for x in excluded_weekdays.split(",") if x.strip()]
    days = available_dates(start_date, end_date, excluded)
    return AvailabilityOut(
        available_days=len(days),
        excluded_days=count_all_days(start_date, end_date) - len(days),
        max_hours=len(days) * hours_per_day,
    )


# ---------------------------------------------------------------- プラン（S02・S05・S06）
def _get_plan(db: Session, plan_id: int, user: User) -> Plan:
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="プランが見つかりません")
    if plan.user_id != user.id and user.role not in ("mentor", "admin"):
        raise HTTPException(status_code=403, detail="このプランを見る権限がありません")
    return plan


@router.post("/plans", response_model=PlanOut, status_code=201)
def create_plan(
    data: PlanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    ai: AIProvider = Depends(ai_provider),
):
    try:
        plan = plan_service.create_plan(db, user, data, ai)
    except AIUnavailable:
        db.rollback()  # 途中まで作ったプランは保存しない（503 は main.py でまとめて返す）
        raise
    except TopicError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail={"message": str(e), "suggestions": e.suggestions}) from e
    except (ValueError, AIError) as e:
        db.rollback()
        raise HTTPException(status_code=422, detail={"message": str(e), "suggestions": []}) from e
    db.commit()
    db.refresh(plan)
    return plan_service.to_out(plan)


@router.get("/plans", response_model=list[PlanSummary])
def list_plans(db: Session = Depends(get_db), user: User = Depends(current_user)):
    plans = db.scalars(select(Plan).where(Plan.user_id == user.id).order_by(Plan.created_at.desc())).all()
    return [plan_service.to_summary(p) for p in plans]


@router.get("/plans/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return plan_service.to_out(_get_plan(db, plan_id, user))


@router.post("/plans/{plan_id}/confirm", response_model=PlanOut)
def confirm_plan(plan_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    plan = _get_plan(db, plan_id, user)
    if plan.status != "proposed":
        raise HTTPException(status_code=409, detail="このプランはすでに確定しています")
    plan.status = "active"
    db.commit()
    return plan_service.to_out(plan)


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    plan = _get_plan(db, plan_id, user)
    db.delete(plan)
    db.commit()


@router.patch("/tasks/{task_id}", response_model=TaskUpdateOut)
def update_task(
    task_id: int, data: TaskUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    plan = _get_plan(db, task.plan_id, user)
    out = plan_service.update_task(db, plan, task, data)
    db.commit()
    return out


@router.post("/plans/{plan_id}/reschedule/preview", response_model=ReschedulePreview)
def reschedule_preview(
    plan_id: int,
    data: RescheduleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    ai: AIProvider = Depends(ai_provider),
):
    plan = _get_plan(db, plan_id, user)
    preview = plan_service.reschedule_preview(plan, ai, data.today)
    db.commit()  # AI の利用回数の記録を残す
    return preview


@router.post("/plans/{plan_id}/reschedule/apply", response_model=PlanOut)
def reschedule_apply(
    plan_id: int,
    preview: ReschedulePreview,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    plan = _get_plan(db, plan_id, user)
    try:
        plan_service.reschedule_apply(plan, preview)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    db.commit()
    db.refresh(plan)
    return plan_service.to_out(plan)


# ---------------------------------------------------------------- 育成担当（S07）
@router.get("/mentor/members")
def mentor_members(db: Session = Depends(get_db), user: User = Depends(require_role("mentor", "admin"))):
    members = db.scalars(select(User).where(User.role == "member").order_by(User.id)).all()
    pending = db.scalar(select(func.count(Material.id)).where(Material.status == "ai_pending")) or 0
    rows = []
    for m in members:
        plans = db.scalars(select(Plan).where(Plan.user_id == m.id).order_by(Plan.created_at.desc())).all()
        rows.append(
            {
                "user": {"id": m.id, "name": m.name},
                "plans": [plan_service.to_summary(p).model_dump(mode="json") for p in plans],
            }
        )
    return {"members": rows, "pending_reviews": pending}


# ---------------------------------------------------------------- AI 提案レビュー（S08）
def _material_dict(m: Material) -> dict:
    return {
        "id": m.id,
        "topic": m.topic.name,
        "title": m.title,
        "url": m.url,
        "type": m.type,
        "source": m.source,
        "status": m.status,
        "supplementary": m.supplementary,
        "url_check": m.url_check,
        "reference_hours": m.reference_hours,
        "reference_basis": m.reference_basis,
        "sections": [
            {"title": s.title, "est_hours": s.est_hours, "level_from": s.level_from, "level_to": s.level_to}
            for s in m.sections
        ],
        "comment": m.review_comment,
    }


@router.get("/review/materials")
def review_materials(db: Session = Depends(get_db), user: User = Depends(require_role("mentor", "admin"))):
    rows = db.scalars(
        select(Material).where(Material.status == "ai_pending").order_by(Material.topic_id, Material.id)
    ).all()
    return [_material_dict(m) for m in rows]


def _decide(material_id: int, status: str, data: ReviewDecision, db: Session) -> dict:
    m = db.get(Material, material_id)
    if m is None or m.status != "ai_pending":
        raise HTTPException(status_code=404, detail="レビュー待ちの教材が見つかりません")
    m.status = status
    if data.comment:
        m.review_comment = data.comment
    db.commit()
    return _material_dict(m)


@router.post("/review/materials/{material_id}/approve")
def approve_material(
    material_id: int,
    data: ReviewDecision,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("mentor", "admin")),
):
    return _decide(material_id, "approved", data, db)


@router.post("/review/materials/{material_id}/reject")
def reject_material(
    material_id: int,
    data: ReviewDecision,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("mentor", "admin")),
):
    return _decide(material_id, "rejected", data, db)


@router.get("/usage", response_model=list[UsageOut])
def usage(db: Session = Depends(get_db), user: User = Depends(require_role("mentor", "admin"))):
    return [
        UsageOut(provider=r.provider, period=r.period, count=r.count, limit=r.limit) for r in latest_usage(db)
    ]
