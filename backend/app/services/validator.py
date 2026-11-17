"""AI が作ったスケジュールの確認（02-4「確認の仕組み」）。副作用のない関数として実装する。

確認項目：形式（Pydantic で確認済み）／日付が期間内か／学習しない日に予定がないか／
1日の合計が確保時間以内か／全体の合計が総学習可能時間以内か／選んだ教材がすべて入っているか。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.schemas import AIDay

EPS = 1e-6


@dataclass
class ExamRule:
    """資格試験の単元の確認条件：全分野を網羅し、試験日より後に予定を入れず、過去問・模擬試験を入れる。"""

    topic: str
    exam_date: dt.date
    areas: list[str]
    material_ids: set[int] = field(default_factory=set)


def validate_days(
    days: list[AIDay],
    *,
    start: dt.date,
    end: dt.date,
    available: Iterable[dt.date],
    hours_per_day: float,
    required_material_ids: Iterable[int] = (),
    exam_rules: Iterable[ExamRule] = (),
) -> list[str]:
    """問題点を日本語の文のリストで返す（空なら合格）。この文はそのまま AI への作り直し依頼に使う。"""
    issues: list[str] = []
    available_set = set(available)
    seen: set[dt.date] = set()
    total = 0.0
    used_materials: set[int] = set()

    for day in days:
        if day.date in seen:
            issues.append(f"{day.date} が複数回出てきます。1日分は1つにまとめてください")
        seen.add(day.date)

        if day.date < start or day.date > end:
            issues.append(f"{day.date} は期間（{start}〜{end}）の外です")
        elif day.date not in available_set:
            issues.append(f"{day.date} は学習しない日（祝日・休み・除外した曜日）です")

        day_total = 0.0
        for task in day.tasks:
            if task.hours <= 0:
                issues.append(f"{day.date} の「{task.title}」の時間が0以下です")
            day_total += task.hours
            if task.material_id is not None:
                used_materials.add(task.material_id)
        if day_total > hours_per_day + EPS:
            issues.append(
                f"{day.date} の合計が {day_total:g} 時間で、1日の上限 {hours_per_day:g} 時間を超えています"
            )
        total += day_total

    max_total = len(available_set) * hours_per_day
    if total > max_total + EPS:
        issues.append(f"全体の合計が {total:g} 時間で、学習できる時間 {max_total:g} 時間を超えています")

    missing = sorted(set(required_material_ids) - used_materials)
    if missing:
        issues.append(f"教材 ID {missing} がスケジュールに入っていません")

    for rule in exam_rules:
        issues.extend(_check_exam(days, rule))

    return issues


def _check_exam(days: list[AIDay], rule: ExamRule) -> list[str]:
    issues: list[str] = []
    covered: set[str] = set()
    late: list[str] = []
    has_practice = False
    for day in days:
        for task in day.tasks:
            mine = task.material_id in rule.material_ids or (task.area in rule.areas)
            if not mine or task.type == "buffer":
                continue
            if task.area:
                covered.add(task.area)
            if task.type == "exercise":
                has_practice = True
            if day.date > rule.exam_date:
                late.append(f"{day.date}「{task.title}」")
    not_covered = [a for a in rule.areas if a not in covered]
    if not_covered:
        issues.append(
            f"「{rule.topic}」の出題範囲のうち {'・'.join(not_covered)} がスケジュールに入っていません"
            "（全分野を網羅し、タスクの area に分野名を入れてください）"
        )
    if late:
        issues.append(
            f"「{rule.topic}」の試験日（{rule.exam_date}）より後に予定があります：{'、'.join(late[:5])}"
        )
    if not has_practice:
        issues.append(f"「{rule.topic}」に過去問演習・模擬試験（type=exercise）が入っていません")
    return issues
