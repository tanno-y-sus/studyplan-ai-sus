"""API キーなしで動く「デモ AI」。

本物の AI（Gemini など）と同じ入出力の形で、決まった手順で結果を作る。
画面と処理の流れを確認するためのもので、教材の中身を理解して判断しているわけではない。
"""

from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import dataclass

from app.schemas import (
    AIDay,
    AIDropped,
    AIMaterialTime,
    AIReschedule,
    AISchedule,
    AITask,
    Allocation,
    MaterialChoice,
    MaterialSelection,
    RescheduleContext,
    ScheduleContext,
    SearchCandidate,
    SectionInfo,
    TopicNormalization,
)
from app.services.reference_time import extract_hours, video_hours

Q = 4  # 15分単位で計算する（1時間 = 4）

_CATEGORY_WORDS = {
    "クラウド": ["aws", "azure", "gcp", "google cloud", "lambda", "ec2", "s3", "クラウド"],
    "データベース": ["sql", "mysql", "postgres", "oracle", "mongodb", "redis", "データベース"],
    "インフラ": [
        "docker",
        "kubernetes",
        "k8s",
        "linux",
        "terraform",
        "ansible",
        "ネットワーク",
        "github actions",
    ],
    "フレームワーク": ["react", "vue", "next", "django", "flask", "fastapi", "spring", "rails", "laravel"],
    "言語": ["python", "java", "javascript", "typescript", "go", "rust", "c#", "kotlin", "php", "ruby"],
}
_NOT_IT_WORDS = ["英語", "toeic", "簿記", "会計", "営業", "マナー", "料理"]
_TOO_BROAD = {
    "aws": ["AWS（EC2・VPC）", "AWS Lambda（サーバーレス）", "AWS（S3・IAM）"],
    "azure": ["Azure 基礎（AZ-900 範囲）", "Azure App Service"],
    "クラウド": ["AWS（EC2・VPC）", "Azure 基礎（AZ-900 範囲）"],
    "プログラミング": ["Python", "Java", "JavaScript"],
}


@dataclass
class _Item:
    title: str
    quarters: int
    type: str
    material_id: int
    level_from: int
    level_to: int
    reviewable: bool


class DemoAI:
    name = "demo"

    # ------------------------------------------------------------------ 単元の正規化
    def normalize_topic(self, text: str) -> TopicNormalization:
        raw = text.strip()
        low = raw.lower()
        if any(w in low for w in _NOT_IT_WORDS):
            return TopicNormalization(name=raw, category="対象外", is_it=False)
        if low in _TOO_BROAD:
            return TopicNormalization(
                name=raw, category="クラウド", is_it=True, too_broad=True, suggestions=_TOO_BROAD[low]
            )
        category = "その他IT"
        for cat, words in _CATEGORY_WORDS.items():
            if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low) for w in words):
                category = cat
                break
        name = raw if not raw.isascii() else " ".join(w[:1].upper() + w[1:] for w in raw.split())
        return TopicNormalization(name=name, category=category, is_it=True)

    # ------------------------------------------------------------------ 教材の選定
    def select_materials(
        self, topic: str, current_level: int, target_level: int, candidates: list[SearchCandidate]
    ) -> MaterialSelection:
        chosen: list[MaterialChoice] = []
        for wanted in ("official_doc", "article", "video"):
            for i, c in enumerate(candidates):
                if c.type == wanted:
                    chosen.append(self._choice(i, c, current_level, target_level))
                    break
        span = max(1, target_level - current_level)
        return MaterialSelection(
            chosen=chosen,
            exercise_title=f"実践課題：{topic} で小さな成果物を作る",
            exercise_description=f"{topic} の基本機能を使って、動くものを1つ作り、手順を README にまとめる",
            exercise_hours=3.0 + 1.5 * span,
        )

    def _choice(self, index: int, c: SearchCandidate, cur: int, tgt: int) -> MaterialChoice:
        if c.type == "video" and c.duration_minutes:
            return MaterialChoice(
                candidate_index=index,
                reason="全体像を短時間でつかむための補助教材",
                reference_hours=video_hours(c.duration_minutes),
                reference_basis=f"動画の長さ {c.duration_minutes:g}分 × 1.5（止めながら手を動かす時間）",
            )
        if c.type == "article":
            found = extract_hours(c.snippet)
            hours, basis = found if found else (1.0, "AI推定（記事の分量から）")
            return MaterialChoice(
                candidate_index=index,
                reason="日本語で手順を確認できる記事",
                reference_hours=hours,
                reference_basis=basis,
            )
        # 公式ドキュメント：目次の代わりに一般的な節立てで提案（育成担当がレビューで修正する）
        span = max(1, tgt - cur)
        sections = [
            SectionInfo(title="基本概念と用語", est_hours=2.0, level_from=1, level_to=2),
            SectionInfo(title="環境構築と基本操作", est_hours=2.0 + span, level_from=2, level_to=3),
            SectionInfo(title="主要機能のハンズオン", est_hours=3.0 + span, level_from=3, level_to=4),
            SectionInfo(title="応用とトラブル対応", est_hours=3.0, level_from=4, level_to=5),
        ]
        return MaterialChoice(
            candidate_index=index,
            reason="主教材となる公式ドキュメント",
            sections=sections,
            reference_basis="AI推定（節の数と分量から）",
        )

    # ------------------------------------------------------------------ スケジュール作成
    def generate_schedule(self, ctx: ScheduleContext) -> AISchedule:
        cap_q = int(round(ctx.hours_per_day * Q))
        capacity = cap_q * len(ctx.available_dates)
        buffer_target = _round_q(capacity * 0.10)
        review_target = _round_q(capacity * 0.07)
        learn_budget = capacity - buffer_target - review_target

        items, dropped, times = self._items(ctx)

        # 時間が足りなければ、目標レベルに遠い節から後回しにする（教材ごとに最低1つは残す）
        total = sum(i.quarters for i in items)
        while total > learn_budget:
            candidates = [
                it
                for it in items
                if it.type in ("learn",) and sum(1 for x in items if x.material_id == it.material_id) > 1
            ]
            if not candidates:
                break
            victim = max(candidates, key=lambda it: (it.level_from, items.index(it)))
            items.remove(victim)
            dropped.append(
                AIDropped(
                    title=victim.title, reason="期間内に収まらないため後回し（目標レベルに必須ではない）"
                )
            )
            total -= victim.quarters
        if total > learn_budget and total > 0:
            # それでも入らない場合は各教材の時間を同じ割合で縮める
            ratio = learn_budget / total
            for it in items:
                it.quarters = max(1, int(it.quarters * ratio))
            dropped.append(AIDropped(title="各教材の学習時間", reason=f"期間が短いため約{ratio:.0%}に圧縮"))

        days, review_used = self._pack(items, ctx.available_dates, cap_q, review_target)
        learn_used = sum(it.quarters for it in items)
        buffer_used = self._fill_buffer(days, cap_q, buffer_target)

        focus_item = max(items, key=lambda it: it.quarters) if items else None
        titles = {m.material_id: m.title for m in ctx.materials}
        order = " → ".join(
            _type_label(it.type, titles.get(it.material_id, it.title))
            for it in {it.material_id: it for it in items}.values()
        )
        return AISchedule(
            materials=times,
            allocation=Allocation(learn=learn_used / Q, review=review_used / Q, buffer=buffer_used / Q),
            order_reason=f"{order} の順に進めます。全体像をつかんでから手を動かし、最後に実践課題で定着させます",
            focus=(
                f"「{focus_item.title}」に最も時間を使います（{focus_item.quarters / Q:g}時間）"
                if focus_item
                else ""
            ),
            dropped=dropped,
            days=[AIDay(date=d, tasks=t) for d, t in days if t],
        )

    def _items(self, ctx: ScheduleContext) -> tuple[list[_Item], list[AIDropped], list[AIMaterialTime]]:
        priority = {
            "video": 0,
            "roadmap": 1,
            "official_doc": 2,
            "official_learning": 3,
            "article": 4,
            "exercise": 5,
        }
        items: list[_Item] = []
        dropped: list[AIDropped] = []
        times: list[AIMaterialTime] = []
        for m in sorted(ctx.materials, key=lambda m: priority.get(m.type, 9)):
            task_type = {"video": "video", "exercise": "exercise"}.get(m.type, "learn")
            if m.sections:
                hours = 0.0
                for s in m.sections:
                    if s.level_to < ctx.current_level or s.level_from > ctx.target_level:
                        dropped.append(
                            AIDropped(title=s.title, reason="現在〜目標レベルの範囲外のため対象外")
                        )
                        continue
                    q = max(1, _round_q(s.est_hours * Q))
                    hours += q / Q
                    items.append(
                        _Item(
                            s.title,
                            q,
                            task_type,
                            m.material_id,
                            s.level_from,
                            s.level_to,
                            reviewable=task_type == "learn",
                        )
                    )
                basis = m.reference_basis or "AI推定（節の数と分量から）"
            else:
                hours = m.reference_hours or 2.0
                basis = m.reference_basis or "AI推定（教材の種類と分量から）"
                items.append(
                    _Item(
                        m.title,
                        max(1, _round_q(hours * Q)),
                        task_type,
                        m.material_id,
                        ctx.current_level,
                        ctx.target_level,
                        reviewable=task_type == "learn",
                    )
                )
            times.append(
                AIMaterialTime(
                    material_id=m.material_id, reference_hours=round(hours, 2), reference_basis=basis
                )
            )
        return items, dropped, times

    def _pack(self, items: list[_Item], dates: list[dt.date], cap_q: int, review_target: int):
        days: list[tuple[dt.date, list[AITask]]] = [(d, []) for d in dates]
        free = [cap_q] * len(dates)
        reviews: list[tuple[int, str, int]] = []  # (復習する日の番号, タイトル, 教材ID)
        review_used = 0
        di = 0
        for it in items:
            remaining = it.quarters
            while remaining > 0 and di < len(dates):
                # 期日が来た復習を先に入れる（学習の1〜3日後）
                for r in [r for r in reviews if r[0] <= di]:
                    rq = 2  # 30分
                    if free[di] >= rq + 1 and review_used + rq <= review_target:
                        days[di][1].append(
                            AITask(type="review", title=f"復習：{r[1]}", hours=rq / Q, material_id=r[2])
                        )
                        free[di] -= rq
                        review_used += rq
                    reviews.remove(r)
                take = min(remaining, free[di])
                if take > 0:
                    days[di][1].append(
                        AITask(type=it.type, title=it.title, hours=take / Q, material_id=it.material_id)
                    )
                    free[di] -= take
                    remaining -= take
                if free[di] == 0:
                    di += 1
            if it.reviewable:
                reviews.append((di + 2, it.title, it.material_id))
        return days, review_used

    def _fill_buffer(self, days, cap_q: int, buffer_target: int) -> int:
        used = 0
        for _d, tasks in reversed(days):
            if used >= buffer_target:
                break
            free = cap_q - int(round(sum(t.hours for t in tasks) * Q))
            take = min(free, buffer_target - used)
            if take > 0:
                tasks.append(AITask(type="buffer", title="予備（遅れの調整・振り返り）", hours=take / Q))
                used += take
        return used

    # ------------------------------------------------------------------ リスケ
    def reschedule(self, ctx: RescheduleContext) -> AIReschedule:
        cap_q = int(round(ctx.hours_per_day * Q))
        dates = [d for d in ctx.available_dates if d >= ctx.today]
        free = [cap_q] * len(dates)
        days: list[tuple[dt.date, list[AITask]]] = [(d, []) for d in dates]
        dropped: list[AIDropped] = []
        # 日をまたいで分割されていた同じタスクは1つにまとめてから詰め直す
        merged: dict[tuple, AITask] = {}
        for t in ctx.pending_tasks:
            if t.type == "buffer":
                continue
            key = (t.title, t.type, t.material_id)
            prev = merged.get(key)
            merged[key] = prev.model_copy(update={"hours": prev.hours + t.hours}) if prev else t
        pending = list(merged.values())
        di = 0
        for t in pending:
            remaining = _round_q(t.hours * Q)
            while remaining > 0 and di < len(dates):
                take = min(remaining, free[di])
                if take > 0:
                    days[di][1].append(
                        AITask(type=t.type, title=t.title, hours=take / Q, material_id=t.material_id)
                    )
                    free[di] -= take
                    remaining -= take
                if free[di] == 0:
                    di += 1
            if remaining > 0:
                dropped.append(AIDropped(title=t.title, reason="残りの期間に収まらないため後回し"))
        pending_q = sum(_round_q(t.hours * Q) for t in pending)
        capacity = cap_q * len(dates)
        if dropped:
            advice = "残りの期間に収まらないタスクがあります。1日の学習時間を増やすか、終了日を延ばすことを検討してください"
        elif pending_q > capacity * 0.9:
            advice = "残りの予定がほぼいっぱいです。遅れが続く場合は1日の学習時間の見直しをおすすめします"
        else:
            advice = "予備の時間を使って、未完了のタスクを前から順に詰め直しました"
        return AIReschedule(
            days=[AIDay(date=d, tasks=t) for d, t in days if t], dropped=dropped, advice=advice
        )


def _round_q(value: float) -> int:
    return int(math.floor(value + 1e-9))


def _type_label(task_type: str, title: str) -> str:
    if task_type == "video":
        return f"動画「{title}」で全体像をつかむ"
    if task_type == "exercise":
        return "実践課題"
    return f"「{title}」"
