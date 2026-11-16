"""設定（AI_PROVIDER）に応じて使う AI を選ぶ。キーがなければデモ AI で動く。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.base import AILimitReached, AIProvider
from app.ai.demo import DemoAI
from app.ai.gemini import GeminiAI
from app.config import Settings, settings
from app.services.usage import LimitReached, consume, period_key


@dataclass(frozen=True)
class AIChoice:
    provider: str  # 実際に使う AI（gemini / demo）
    model: str | None
    reason: str  # 画面やログに出す説明


def choose_ai(cfg: Settings = settings) -> AIChoice:
    """設定から、実際にどの AI を使うかを決める（get_ai と状態表示で同じ判定を使う）。"""
    if cfg.ai_provider == "gemini":
        if cfg.gemini_api_key:
            return AIChoice("gemini", cfg.gemini_model, f"Gemini API（{cfg.gemini_model}）を使っています")
        return AIChoice(
            "demo", None, "AI_PROVIDER=gemini ですが GEMINI_API_KEY が未設定のため、デモ AI で動いています"
        )
    if cfg.ai_provider != "demo":
        return AIChoice(
            "demo", None, f"AI_PROVIDER={cfg.ai_provider} には対応していないため、デモ AI で動いています"
        )
    return AIChoice("demo", None, "デモ AI で動いています（API キー不要・外部に通信しません）")


def get_ai(db: Session, cfg: Settings = settings) -> AIProvider:
    choice = choose_ai(cfg)
    if choice.provider == "gemini" and cfg.gemini_api_key:

        def on_call() -> None:
            try:
                consume(db, "gemini", period_key("day"), cfg.gemini_daily_limit)
            except LimitReached as e:
                raise AILimitReached(
                    f"Gemini の1日の利用上限（GEMINI_DAILY_LIMIT={cfg.gemini_daily_limit}回）に達しました。明日以降にやり直してください"
                ) from e

        return GeminiAI(cfg.gemini_api_key, cfg.gemini_model, on_call=on_call)
    return DemoAI()
