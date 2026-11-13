"""学習できる日の計算（AI の日付の間違いを減らすため、カレンダー情報として AI に渡す）。"""

from __future__ import annotations

import datetime as dt

import jpholiday


def available_dates(start: dt.date, end: dt.date, excluded_weekdays: list[int]) -> list[dt.date]:
    """開始日〜終了日のうち、祝日と学習しない曜日（0=月 … 6=日）を除いた日を返す。"""
    excluded = set(excluded_weekdays)
    days: list[dt.date] = []
    d = start
    while d <= end:
        if d.weekday() not in excluded and not jpholiday.is_holiday(d) and not _is_year_end(d):
            days.append(d)
        d += dt.timedelta(days=1)
    return days


def _is_year_end(d: dt.date) -> bool:
    """年末年始休暇（12/29〜1/3）。会社の休日カレンダーに合わせて変更する想定。"""
    return (d.month == 12 and d.day >= 29) or (d.month == 1 and d.day <= 3)


def count_all_days(start: dt.date, end: dt.date) -> int:
    return (end - start).days + 1
