"""設定（AI_PROVIDER）に応じて使う AI を選ぶ。キーがなければデモ AI で動く。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.base import AILimitReached, AIProvider
from app.ai.demo import DemoAI
from app.ai.gemini import GeminiAI
from app.config import Settings, settings
from app.services.usage import LimitReached, consume, period_key


def get_ai(db: Session, cfg: Settings = settings) -> AIProvider:
    if cfg.ai_provider == "gemini" and cfg.gemini_api_key:

        def on_call() -> None:
            try:
                consume(db, "gemini", period_key("day"), cfg.gemini_daily_limit)
            except LimitReached as e:
                raise AILimitReached(str(e)) from e

        return GeminiAI(cfg.gemini_api_key, cfg.gemini_model, on_call=on_call)
    return DemoAI()
