import datetime as dt
import random

import pytest

from app.ai.base import AIError
from app.ai.demo import DemoAI
from app.schemas import (
    AIDay,
    AISchedule,
    AITask,
    MaterialInfo,
    RescheduleContext,
    ScheduleContext,
    SectionInfo,
)
from app.services.calendar import available_dates
from app.services.schedule import generate_with_checks, reschedule_with_checks
from app.services.validator import validate_days


def _ctx(start, end, hpd, cur=2, tgt=4, excluded=(5, 6)):
    return ScheduleContext(
        topic="Python",
        current_level=cur,
        target_level=tgt,
        start_date=start,
        end_date=end,
        hours_per_day=hpd,
        available_dates=available_dates(start, end, list(excluded)),
        materials=[
            MaterialInfo(
                material_id=1,
                title="公式",
                type="official_doc",
                sections=[
                    SectionInfo(title=f"{i}章", est_hours=h, level_from=lf, level_to=lt)
                    for i, (h, lf, lt) in enumerate(
                        [(3, 1, 2), (5, 2, 3), (5, 2, 3), (4, 3, 4), (6, 3, 4), (3, 4, 5)]
                    )
                ],
            ),
            MaterialInfo(
                material_id=2, title="動画", type="video", reference_hours=1.5, reference_basis="動画の長さ"
            ),
            MaterialInfo(material_id=3, title="課題", type="exercise", reference_hours=4),
        ],
    )


@pytest.mark.parametrize("seed", range(40))
def test_demo_ai_schedule_always_passes_checks(seed):
    rnd = random.Random(seed)
    start = dt.date(2026, 12, 1) + dt.timedelta(days=rnd.randint(0, 60))
    end = start + dt.timedelta(days=rnd.randint(3, 60))
    hpd = rnd.choice([0.5, 1, 1.5, 2, 3, 4, 8])
    ctx = _ctx(start, end, hpd, cur=rnd.randint(1, 3), tgt=rnd.randint(3, 5))
    if not ctx.available_dates:
        pytest.skip("学習できる日がない期間")
    result = generate_with_checks(DemoAI(), ctx)
    assert result.passed, result.issues
    assert result.retries == 0


class FlakyAI(DemoAI):
    """1回目はわざと間違える（休みの日に予定を入れる）AI。2回目は正しく作る。"""

    def __init__(self):
        self.calls = 0
        self.feedback_seen: list[str] = []

    def generate_schedule(self, ctx):
        self.calls += 1
        self.feedback_seen = list(ctx.feedback)
        good = super().generate_schedule(ctx)
        if self.calls == 1:
            bad_day = AIDay(
                date=ctx.end_date + dt.timedelta(days=30),
                tasks=[AITask(type="learn", title="x", hours=1, material_id=1)],
            )
            return good.model_copy(update={"days": good.days + [bad_day]})
        return good


def test_retry_with_feedback_until_valid():
    ai = FlakyAI()
    result = generate_with_checks(ai, _ctx(dt.date(2026, 12, 1), dt.date(2026, 12, 25), 2))
    assert result.passed
    assert result.retries == 1
    assert any("期間" in f for f in ai.feedback_seen)  # 2回目の依頼に問題点が渡っている


class BrokenAI(DemoAI):
    def generate_schedule(self, ctx):
        raise AIError("形式が違います")


def test_gives_up_after_max_retries():
    result = generate_with_checks(
        BrokenAI(), _ctx(dt.date(2026, 12, 1), dt.date(2026, 12, 25), 2), max_retries=2
    )
    assert not result.passed
    assert result.retries == 2
    assert result.schedule is None


def test_short_period_drops_sections_with_reasons():
    ctx = _ctx(dt.date(2026, 12, 1), dt.date(2026, 12, 4), 2)
    result = generate_with_checks(DemoAI(), ctx)
    assert result.passed
    assert result.schedule.dropped, "時間が足りないので後回しの記録があるはず"


def test_reschedule_respects_capacity_and_today():
    today = dt.date(2026, 12, 8)
    dates = available_dates(dt.date(2026, 12, 1), dt.date(2026, 12, 19), [5, 6])
    ctx = RescheduleContext(
        topic="Python",
        today=today,
        end_date=dt.date(2026, 12, 19),
        hours_per_day=2,
        available_dates=dates,
        pending_tasks=[AITask(type="learn", title=f"t{i}", hours=1.5, material_id=1) for i in range(5)],
    )
    result = reschedule_with_checks(DemoAI(), ctx)
    assert result.issues == []
    assert all(d.date >= today for d in result.plan.days)
    assert (
        validate_days(result.plan.days, start=today, end=ctx.end_date, available=dates, hours_per_day=2) == []
    )


def test_schedule_context_has_no_personal_info():
    fields = set(ScheduleContext.model_fields) | set(MaterialInfo.model_fields)
    assert not {"name", "email", "user", "user_name", "user_id"} & fields


def test_ai_schedule_schema_rejects_bad_format():
    with pytest.raises(ValueError):
        AISchedule.model_validate({"days": "not a list"})
