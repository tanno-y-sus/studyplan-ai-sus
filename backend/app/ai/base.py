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
    TopicNormalization,
)


class AIError(Exception):
    """AI の呼び出し失敗、または決まった形式で返ってこなかった場合。"""


class AILimitReached(AIError):
    """無料枠の上限に達した場合。"""


class AIProvider(Protocol):
    name: str

    def normalize_topic(self, text: str) -> TopicNormalization:
        """入力された単元名をそろえ、IT 技術かどうか・前提単元などを返す。"""
        ...

    def select_materials(
        self, topic: str, current_level: int, target_level: int, candidates: list[SearchCandidate]
    ) -> MaterialSelection:
        """検索 API で集めた候補から、レベルに合う教材を選び、実践課題を作る。"""
        ...

    def generate_schedule(self, ctx: ScheduleContext) -> AISchedule:
        """参考時間の読み取り・順番・時間配分・日別スケジュールまでを作る（02-4）。"""
        ...

    def reschedule(self, ctx: RescheduleContext) -> AIReschedule:
        """未完了のタスクを残りの学習できる日に組み直す（02-6）。"""
        ...
