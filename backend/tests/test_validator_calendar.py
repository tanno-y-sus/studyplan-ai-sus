import datetime as dt

from app.schemas import AIDay, AITask
from app.services.calendar import available_dates
from app.services.reference_time import extract_hours, parse_iso8601_duration, video_hours
from app.services.validator import validate_days

D = dt.date


def day(d, *hours, mid=1):
    return AIDay(
        date=d,
        tasks=[AITask(type="learn", title=f"t{i}", hours=h, material_id=mid) for i, h in enumerate(hours)],
    )


def test_available_dates_excludes_weekends_holidays_and_year_end():
    days = available_dates(D(2026, 12, 21), D(2027, 1, 8), [5, 6])
    assert D(2026, 12, 26) not in days  # 土曜
    assert D(2026, 12, 29) not in days  # 年末年始
    assert D(2027, 1, 1) not in days
    assert D(2026, 12, 21) in days
    assert D(2027, 1, 5) in days


def test_available_dates_excludes_national_holiday():
    assert D(2026, 11, 23) not in available_dates(D(2026, 11, 23), D(2026, 11, 24), [])  # 勤労感謝の日


def test_validator_passes_valid_schedule():
    avail = [D(2026, 12, 1), D(2026, 12, 2)]
    issues = validate_days(
        [day(avail[0], 1.5, 1.5), day(avail[1], 3)],
        start=avail[0],
        end=avail[1],
        available=avail,
        hours_per_day=3,
        required_material_ids=[1],
    )
    assert issues == []


def test_validator_detects_each_problem():
    avail = [D(2026, 12, 1), D(2026, 12, 2)]
    days = [
        day(D(2026, 11, 30), 1),  # 期間外
        day(D(2026, 12, 1), 2, 2),  # 1日の上限超過
        day(D(2026, 12, 1), 1),  # 同じ日が2回
        day(D(2026, 12, 2), 0),  # 0時間
    ]
    issues = validate_days(
        days, start=avail[0], end=avail[1], available=avail, hours_per_day=3, required_material_ids=[1, 2]
    )
    text = "\n".join(issues)
    assert "期間" in text
    assert "1日の上限" in text
    assert "複数回" in text
    assert "0以下" in text
    assert "教材 ID [2]" in text


def test_validator_detects_unavailable_day_and_total():
    avail = [D(2026, 12, 1)]
    issues = validate_days(
        [day(D(2026, 12, 2), 1)], start=D(2026, 12, 1), end=D(2026, 12, 3), available=avail, hours_per_day=1
    )
    assert any("学習しない日" in i for i in issues)


def test_reference_time_extraction():
    hours, basis = extract_hours("この記事の所要時間 約40分。")
    assert hours == 1.0 and "所要時間" in basis
    assert extract_hours("所要時間：約２時間")[0] == 3.0
    assert extract_hours("5 min read")[0] == 0.5
    assert extract_hours("記載なし") is None
    assert video_hours(58) == 1.5
    assert parse_iso8601_duration("PT1H2M30S") == 62.5
