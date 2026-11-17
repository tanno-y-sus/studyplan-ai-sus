"""AI の共通インターフェース。Gemini（無料枠）・デモ・将来の Claude などを同じ形で差し替える。"""

from __future__ import annotations

from typing import Protocol

from app.schemas import (
    AIReschedule,
    AISchedule,
    MaterialSelection,
    RescheduleContext,
    ScheduleContext,
    SearchCandidate,
    SkillChecklist,
    TopicNormalization,
)


class AIError(Exception):
    """AI の呼び出し失敗、または決まった形式で返ってこなかった場合。"""


class AIUnavailable(AIError):
    """AI を使えない場合（通信できない・キーが正しくない・無料枠の上限・一時的な障害）。

    作り直しを頼んでも結果は変わらないので、その場で処理を止めて画面にエラーを返す。
    """


class AILimitReached(AIUnavailable):
    """無料枠の上限に達した場合（アプリ側で数えている1日の上限）。"""


class AIProvider(Protocol):
    name: str

    def normalize_topic(self, text: str) -> TopicNormalization:
        """入力された単元名をそろえ、IT 技術かどうか・前提単元などを返す。"""
        ...

    def skill_checklist(self, topic: str, category: str) -> SkillChecklist:
        """単元の「できること」を易しい順に5〜8個作る（現在・目標のチェックに使う）。"""
        ...

    def select_materials(
        self,
        topic: str,
        current_level: int,
        target_level: int,
        candidates: list[SearchCandidate],
        goals: list[str] | None = None,
    ) -> MaterialSelection:
        """検索 API で集めた候補から、レベルに合う教材を選び、実践課題を作る。"""
        ...

    def generate_schedule(self, ctx: ScheduleContext) -> AISchedule:
        """参考時間の読み取り・順番・時間配分・日別スケジュールまでを作る（02-4）。"""
        ...

    def reschedule(self, ctx: RescheduleContext) -> AIReschedule:
        """未完了のタスクを残りの学習できる日に組み直す（02-6）。"""
        ...
