"""外部 API の利用回数の記録（無料枠の管理）。上限に近づいたら別の API に切り替えるために使う。"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApiUsage


class LimitReached(Exception):
    pass


def period_key(kind: str, now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(dt.UTC)
    if kind == "month":
        return now.strftime("%Y-%m")
    if kind == "hour":
        return now.strftime("%Y-%m-%dT%H")
    return now.strftime("%Y-%m-%d")


def consume(db: Session, provider: str, period: str, limit: int, amount: int = 1) -> ApiUsage:
    """1回分の利用を記録する。上限を超える場合は LimitReached を出して記録しない。"""
    row = db.scalar(select(ApiUsage).where(ApiUsage.provider == provider, ApiUsage.period == period))
    if row is None:
        row = ApiUsage(provider=provider, period=period, count=0, limit=limit)
        db.add(row)
    row.limit = limit
    if row.count + amount > limit:
        raise LimitReached(f"{provider} の無料枠（{period}：{limit}回）の上限に達しました")
    row.count += amount
    db.flush()
    return row


def latest_usage(db: Session) -> list[ApiUsage]:
    rows = db.scalars(select(ApiUsage).order_by(ApiUsage.provider, ApiUsage.period.desc())).all()
    latest: dict[str, ApiUsage] = {}
    for r in rows:
        latest.setdefault(r.provider, r)
    return list(latest.values())
