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
    ExamArea,
    ExamSyllabus,
    MaterialChoice,
    MaterialSelection,
    RescheduleContext,
    ScheduleContext,
    SearchCandidate,
    SectionInfo,
    SkillChecklist,
    SkillItem,
    TopicAllocation,
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


# 情報処理技術者試験（IPA）の出題分野（テクノロジ系・マネジメント系・ストラテジ系）と、だいたいの比重
_IPA_AREAS = [
    ("基礎理論（離散数学・応用数学・情報理論）", 10),
    ("アルゴリズムとプログラミング", 12),
    ("コンピュータシステム（構成要素・ソフトウェア・ハードウェア）", 12),
    ("データベース", 9),
    ("ネットワーク", 9),
    ("セキュリティ", 14),
    ("開発技術（システム開発・ソフトウェア開発管理）", 8),
    ("プロジェクトマネジメント・サービスマネジメント", 10),
    ("システム監査", 4),
    ("システム戦略・経営戦略", 8),
    ("企業活動と法務", 4),
]
_GENERIC_AREAS = [
    ("試験の概要と頻出用語", 10),
    ("基礎知識", 20),
    ("主要分野 1", 20),
    ("主要分野 2", 20),
    ("応用・ケーススタディ", 15),
    ("運用・管理・関連法規", 15),
]


@dataclass
class _Item:
    title: str
    quarters: int
    type: str
    material_id: int
    level_from: int
    level_to: int
    reviewable: bool
    area: str | None = None  # 資格試験の分野
    protected: bool = False  # 時間が足りなくても後回しにしない（試験の分野・過去問・模擬試験）
    deadline: dt.date | None = None  # 資格試験の試験日


class DemoAI:
    name = "demo"

    # ------------------------------------------------------------------ 単元の正規化
    def normalize_topic(self, text: str, kind: str = "skill") -> TopicNormalization:
        raw = text.strip()
        low = raw.lower()
        if any(w in low for w in _NOT_IT_WORDS):
            return TopicNormalization(name=raw, category="対象外", is_it=False)
        if kind == "exam":
            # 資格試験は絞り込まず、試験全体を1つの単元にする
            return TopicNormalization(name=raw, category="資格試験", is_it=True)
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

    # ------------------------------------------------------------------ 資格試験の出題範囲
    def exam_areas(self, topic: str) -> ExamSyllabus:
        """デモ：情報処理技術者試験なら IPA の出題分野、それ以外は一般的な分野で作る。"""
        ipa = any(
            w in topic for w in ("情報技術者", "ITパスポート", "情報セキュリティ", "応用情報", "基本情報")
        )
        areas = _IPA_AREAS if ipa else _GENERIC_AREAS
        total_hours = 80 if ipa else 50
        return ExamSyllabus(
            areas=[
                ExamArea(
                    name=name,
                    description=f"{topic} の「{name}」の範囲（デモ AI の一般的な分け方です）",
                    weight=w,
                    est_hours=round(total_hours * w / 100 * 4) / 4 or 0.5,
                )
                for name, w in areas
            ],
            syllabus_url="https://www.ipa.go.jp/shiken/syllabus/index.html" if ipa else None,
        )

    # ------------------------------------------------------------------ できることのチェックリスト
    def skill_checklist(self, topic: str, category: str) -> SkillChecklist:
        """どの単元にも当てはまる一般的なリスト（本物の AI は単元に合わせた具体的な文を作る）。"""
        texts = [
            (f"{topic} が何のためのもので、どんな場面で使われるかを説明できる", 1),
            (f"{topic} の基本用語や仕組みを、自分の言葉で説明できる", 2),
            (f"{topic} の環境を用意し、チュートリアルどおりに動かせる", 2),
            (f"{topic} の基本機能を使って、手順書どおりに作業できる", 3),
            (f"{topic} で小さなものを、自分で調べながら作れる", 3),
            (f"{topic} のエラーやトラブルの原因を調べて自力で直せる", 4),
            (f"要件に合わせて {topic} の構成や設計を決められる", 5),
            (f"{topic} の使い方を他の人に教えられる", 5),
        ]
        return SkillChecklist(items=[SkillItem(text=t, level=lv) for t, lv in texts])

    # ------------------------------------------------------------------ 教材の選定
    def select_materials(
        self,
        topic: str,
        current_level: int,
        target_level: int,
        candidates: list[SearchCandidate],
        goals: list[str] | None = None,
        kind: str = "skill",
    ) -> MaterialSelection:
        chosen: list[MaterialChoice] = []
        for wanted in ("official_doc", "article", "video"):
            for i, c in enumerate(candidates):
                if c.type == wanted:
                    chosen.append(self._choice(i, c, current_level, target_level))
                    break
        span = max(1, target_level - current_level)
        if kind == "exam":
            # 資格試験は出題範囲の分野で学ぶので、技術向けの節立ては付けない
            chosen = [
                c.model_copy(update={"sections": [], "reason": "出題範囲（分野）に沿って進めるための教材"})
                if not c.reference_hours
                else c
                for c in chosen
            ]
            return MaterialSelection(
                chosen=chosen,
                exercise_title=f"模擬試験：{topic} の過去問を本番と同じ時間で解く",
                exercise_description="過去問1回分を本番と同じ時間で解き、間違えた問題の分野を復習する",
                exercise_hours=6.0,
            )
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

        items, dropped, times = self._items(ctx, cap_q)

        # 時間が足りなければ、目標レベルに遠い節から後回しにする（教材ごとに最低1つは残す）
        total = sum(i.quarters for i in items)
        while total > learn_budget:
            candidates = [
                it
                for it in items
                if it.type in ("learn",)
                and not it.protected
                and sum(1 for x in items if x.material_id == it.material_id) > 1
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
        topic_of = {m.material_id: m.topic for m in ctx.materials}
        order = " → ".join(
            _type_label(it.type, titles.get(it.material_id, it.title))
            for it in {it.material_id: it for it in items}.values()
        )
        topic_names = [g.topic for g in ctx.topics]
        hours_by_topic = {name: 0.0 for name in topic_names}
        for _d, tasks in days:
            for t in tasks:
                name = topic_of.get(t.material_id) if t.material_id is not None else None
                if name in hours_by_topic:
                    hours_by_topic[name] += t.hours
        exam_notes = [
            f"{g.topic} は試験日 {g.exam_date or ctx.end_date} までに出題範囲 {len(g.areas)} 分野をすべて学び、"
            "最後に過去問演習と模擬試験を入れます"
            for g in ctx.topics
            if g.kind == "exam"
        ]
        order_names = [g.topic for g in sorted(ctx.topics, key=lambda g: 0 if g.kind == "exam" else 1)]
        if len(topic_names) > 1:
            strategy = (
                f"{' → '.join(order_names)} の順に、1つずつ進めます（デモ AI は資格試験を先に、ほかは入力した順に並べます。"
                "本物の AI は前提関係や分量から順番・並行を決めます）"
            )
        else:
            strategy = ""
        strategy = "。".join(x for x in [strategy.rstrip("。"), *exam_notes] if x)
        return AISchedule(
            materials=times,
            allocation=Allocation(learn=learn_used / Q, review=review_used / Q, buffer=buffer_used / Q),
            strategy=strategy,
            topic_allocation=[TopicAllocation(topic=n, hours=round(h, 2)) for n, h in hours_by_topic.items()],
            order_reason=f"{order} の順に進めます。全体像をつかんでから手を動かし、最後に実践課題で定着させます",
            focus=(
                f"「{focus_item.title}」に最も時間を使います（{focus_item.quarters / Q:g}時間）"
                if focus_item
                else ""
            ),
            dropped=dropped,
            days=[AIDay(date=d, tasks=t) for d, t in days if t],
        )

    def _exam_items(
        self, ctx: ScheduleContext, goal, cap_q: int, used_q: int
    ) -> tuple[list[_Item], list[AIMaterialTime]]:
        """資格試験：全分野を比重で配分し、最後に過去問演習と模擬試験。試験日までに収まる量にする。"""
        deadline = goal.exam_date or ctx.end_date
        ms = [m for m in ctx.materials if m.topic == goal.topic]
        days_before = sum(1 for d in ctx.available_dates if d <= deadline)
        budget = int(days_before * cap_q * 0.8) - used_q  # 復習の分の余裕を残す
        videos = [m for m in ms if m.type == "video"]
        practice_m = next((m for m in ms if m.type == "exercise"), None)
        main = next((m for m in ms if m.type in ("official_doc", "official_learning")), None) or next(
            (m for m in ms if m.type not in ("video", "exercise")), None
        )
        others = [m for m in ms if m not in videos and m is not practice_m and m is not main]
        items: list[_Item] = []
        times: list[AIMaterialTime] = []
        for m in videos + others:
            q = max(1, _round_q((m.reference_hours or 1.0) * Q))
            kind = "video" if m.type == "video" else "learn"
            items.append(_Item(m.title, q, kind, m.material_id, 1, 5, False, deadline=deadline))
            times.append(
                AIMaterialTime(
                    material_id=m.material_id,
                    reference_hours=q / Q,
                    reference_basis=m.reference_basis or "AI推定（教材の種類と分量から）",
                )
            )
        remain = max(len(goal.areas) + 2, budget - sum(i.quarters for i in items))
        est_q = sum(max(1, _round_q(a.est_hours * Q)) for a in goal.areas)
        practice_q = max(2, int(min(remain * 0.25, max(8, est_q * 0.3))))
        area_q = max(len(goal.areas), min(est_q, remain - practice_q))
        total_w = sum(a.weight for a in goal.areas) or 1
        main_id = main.material_id if main else (ms[0].material_id if ms else 0)
        for a in goal.areas:
            q = max(1, int(area_q * a.weight / total_w))
            items.append(
                _Item(a.name, q, "learn", main_id, 1, 5, True, area=a.name, protected=True, deadline=deadline)
            )
        practice_id = practice_m.material_id if practice_m else main_id
        kakomon = max(1, practice_q * 6 // 10)
        items.append(
            _Item(
                "過去問演習（全分野）",
                kakomon,
                "exercise",
                practice_id,
                1,
                5,
                False,
                protected=True,
                deadline=deadline,
            )
        )
        items.append(
            _Item(
                "模擬試験（本番と同じ時間で）",
                max(1, practice_q - kakomon),
                "exercise",
                practice_id,
                1,
                5,
                False,
                protected=True,
                deadline=deadline,
            )
        )
        if main:
            hours = sum(i.quarters for i in items if i.area) / Q
            times.append(
                AIMaterialTime(
                    material_id=main.material_id,
                    reference_hours=hours,
                    reference_basis=f"出題範囲 {len(goal.areas)} 分野の比重と目安時間から（試験日 {deadline} までに収まる量）",
                )
            )
        if practice_m:
            times.append(
                AIMaterialTime(
                    material_id=practice_m.material_id,
                    reference_hours=practice_q / Q,
                    reference_basis="試験前の過去問演習と模擬試験の時間",
                )
            )
        return items, times

    def _items(
        self, ctx: ScheduleContext, cap_q: int = 8
    ) -> tuple[list[_Item], list[AIDropped], list[AIMaterialTime]]:
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
        # 資格試験は試験日の早い順に先に入れる（試験日までに終わらせるため）
        exams = sorted((g for g in ctx.topics if g.kind == "exam"), key=lambda g: g.exam_date or ctx.end_date)
        for g in exams:
            exam_items, exam_times = self._exam_items(ctx, g, cap_q, sum(i.quarters for i in items))
            items.extend(exam_items)
            times.extend(exam_times)
        exam_topics = {g.topic for g in exams}
        topic_index = {g.topic: i for i, g in enumerate(ctx.topics)}
        levels = {g.topic: (g.current_level, g.target_level) for g in ctx.topics}
        default_levels = (ctx.topics[0].current_level, ctx.topics[0].target_level) if ctx.topics else (1, 5)
        # 単元は入力した順に1つずつ。単元の中は 動画 → 公式 → 記事 → 実践課題 の順
        for m in sorted(ctx.materials, key=lambda m: (topic_index.get(m.topic, 99), priority.get(m.type, 9))):
            if m.topic in exam_topics:
                continue
            current_level, target_level = levels.get(m.topic, default_levels)
            task_type = {"video": "video", "exercise": "exercise"}.get(m.type, "learn")
            if m.sections:
                hours = 0.0
                for s in m.sections:
                    if s.level_to < current_level or s.level_from > target_level:
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
                        current_level,
                        target_level,
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
        reviews: list[
            tuple[int, str, int, dt.date | None]
        ] = []  # (復習する日の番号, タイトル, 教材ID, 締め切り)
        review_used = 0
        di = 0
        for it in items:
            remaining = it.quarters
            while remaining > 0 and di < len(dates):
                # 期日が来た復習を先に入れる（学習の1〜3日後）
                for r in [r for r in reviews if r[0] <= di]:
                    rq = 2  # 30分
                    in_time = r[3] is None or dates[di] <= r[3]  # 試験日を過ぎた復習は入れない
                    if in_time and free[di] >= rq + 1 and review_used + rq <= review_target:
                        days[di][1].append(
                            AITask(type="review", title=f"復習：{r[1]}", hours=rq / Q, material_id=r[2])
                        )
                        free[di] -= rq
                        review_used += rq
                    reviews.remove(r)
                take = min(remaining, free[di])
                if take > 0:
                    days[di][1].append(
                        AITask(
                            type=it.type,
                            title=it.title,
                            hours=take / Q,
                            material_id=it.material_id,
                            area=it.area,
                        )
                    )
                    free[di] -= take
                    remaining -= take
                if free[di] == 0:
                    di += 1
            if it.reviewable:
                reviews.append((di + 2, it.title, it.material_id, it.deadline))
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
        # 資格試験（締め切りのあるタスク）を試験日の早い順に先に詰める
        deadline_of: dict[int, dt.date] = {}
        for d in ctx.deadlines:
            for mid in d.material_ids:
                deadline_of[mid] = min(d.date, deadline_of.get(mid, d.date))
        pending = sorted(merged.values(), key=lambda t: deadline_of.get(t.material_id or -1, dt.date.max))
        di = 0
        for t in pending:
            remaining = _round_q(t.hours * Q)
            limit = deadline_of.get(t.material_id or -1)
            while remaining > 0 and di < len(dates):
                if limit is not None and dates[di] > limit:
                    break  # 試験日を過ぎる分は入れない
                take = min(remaining, free[di])
                if take > 0:
                    days[di][1].append(
                        AITask(
                            type=t.type, title=t.title, hours=take / Q, material_id=t.material_id, area=t.area
                        )
                    )
                    free[di] -= take
                    remaining -= take
                if free[di] == 0:
                    di += 1
            if remaining > 0:
                reason = (
                    "試験日までに収まらないため後回し"
                    if limit is not None
                    else "残りの期間に収まらないため後回し"
                )
                dropped.append(AIDropped(title=t.title, reason=reason))
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
