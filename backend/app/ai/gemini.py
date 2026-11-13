"""Gemini API（無料枠を想定）を使う AI。

- 結果は JSON で受け取り（responseMimeType=application/json）、Pydantic で形式を確認する
- 形式が違う・呼び出しに失敗した場合は AIError を出し、呼び出し側で作り直し（または警告）にする
- 送るのは単元名・レベル・日付・教材情報のみ。氏名などの個人情報は送らない
  （Gemini の無料枠では、送った内容が Google の製品改善に使われるため）
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.base import AIError
from app.schemas import (
    AIReschedule,
    AISchedule,
    MaterialSelection,
    RescheduleContext,
    ScheduleContext,
    SearchCandidate,
    TopicNormalization,
)

T = TypeVar("T", bound=BaseModel)

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM = (
    "あなたは社内のIT技術研修の学習計画を作るアシスタントです。"
    "必ず指定された JSON 形式だけを返してください。説明文やコードブロックは付けないでください。"
)


class GeminiAI:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        on_call: Callable[[], None] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.on_call = on_call  # 利用回数の記録（上限なら例外を出す）
        self.client = client or httpx.Client(timeout=60)

    # ------------------------------------------------------------------ 共通
    def _ask(self, prompt: str, model_cls: type[T]) -> T:
        if self.on_call:
            self.on_call()
        schema = json.dumps(model_cls.model_json_schema(), ensure_ascii=False)
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{prompt}\n\n# 返す JSON の形式（JSON Schema）\n{schema}"}],
                }
            ],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
        }
        try:
            res = self.client.post(
                API_URL.format(model=self.model), json=body, headers={"x-goog-api-key": self.api_key}
            )
            res.raise_for_status()
            data = res.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise AIError(f"Gemini API の呼び出しに失敗しました: {e}") from e
        try:
            return model_cls.model_validate_json(text)
        except ValidationError as e:
            raise AIError(f"AI の回答が決まった形式ではありません: {e.error_count()}件の問題") from e

    # ------------------------------------------------------------------ 各処理
    def normalize_topic(self, text: str) -> TopicNormalization:
        prompt = (
            "次の入力は、社員が学びたいと入力した単元名です。正式な名称にそろえ、カテゴリ（言語／データベース／"
            "クラウド／インフラ／フレームワーク／その他IT）、IT技術かどうか、前提となる単元を答えてください。"
            "範囲が広すぎる場合（例：AWS）は too_broad=true とし、絞り込み候補を suggestions に3つ入れてください。\n"
            f"入力：{text}"
        )
        return self._ask(prompt, TopicNormalization)

    def select_materials(
        self, topic: str, current_level: int, target_level: int, candidates: list[SearchCandidate]
    ) -> MaterialSelection:
        listing = "\n".join(
            f"[{i}] 種類={c.type} 取得元={c.source} タイトル={c.title} URL={c.url} "
            f"動画の長さ(分)={c.duration_minutes} 抜粋={c.snippet[:300]}"
            for i, c in enumerate(candidates)
        )
        prompt = (
            f"単元「{topic}」を レベル{current_level} から レベル{target_level} に上げたい人向けに、"
            "次の候補から教材を最大3件選んでください（公式ドキュメントを必ず1件、日本語記事・動画はあれば1件ずつ）。"
            "公式ドキュメントには学ぶ節（sections）を目次に沿って提案し、各節の想定時間と対応レベルを付けてください。"
            "記事や動画に参考時間の記載・長さがあれば reference_hours と reference_basis に根拠を書いてください。"
            "最後に、学んだ内容を使う実践課題を1つ作ってください。\n"
            "レベル：1=未経験 2=概念を説明できる 3=手順どおり使える 4=自力で構成・トラブル対応できる 5=設計・他者に教えられる\n"
            f"# 候補\n{listing}"
        )
        return self._ask(prompt, MaterialSelection)

    def generate_schedule(self, ctx: ScheduleContext) -> AISchedule:
        prompt = (
            "次の学習条件と教材から、学習スケジュールを作ってください。\n"
            "1. 教材ごとに参考時間を決める（ページの記載や動画の長さがあれば使い、なければ節の数と分量から推定し、"
            "根拠を reference_basis に書く）\n"
            "2. 学ぶ順番と重点を決め、理由を order_reason と focus に書く\n"
            "3. 時間が足りない場合は、目標レベルに必須ではない節から後回しにし、dropped に理由と一緒に書く\n"
            "4. 学習・復習・予備の時間を配分する（目安：学習75%・復習10%・予備15%。単元に合わせて調整してよい）\n"
            "5. available_dates の日だけを使い、各日の合計が hours_per_day を超えないように日別のタスクを作る。"
            "復習（type=review）は学習の1〜3日後に入れる。教材ごとに material_id を付ける\n"
            "時間は 0.25 時間単位にしてください。\n"
            + _feedback(ctx.feedback)
            + f"# 学習条件と教材\n{ctx.model_dump_json()}"
        )
        return self._ask(prompt, AISchedule)

    def reschedule(self, ctx: RescheduleContext) -> AIReschedule:
        prompt = (
            "学習が遅れています。未完了のタスク（pending_tasks）を、today 以降の available_dates に組み直してください。"
            "各日の合計は hours_per_day を超えないこと。予備（buffer）は使ってよい。"
            "収まらないものは dropped に理由と一緒に書き、advice に本人へのひとことを書いてください。\n"
            + _feedback(ctx.feedback)
            + f"# 状況\n{ctx.model_dump_json()}"
        )
        return self._ask(prompt, AIReschedule)


def _feedback(items: list[str]) -> str:
    if not items:
        return ""
    joined = "\n".join(f"- {i}" for i in items)
    return f"# 前回の結果の問題点（必ず直してください）\n{joined}\n"
