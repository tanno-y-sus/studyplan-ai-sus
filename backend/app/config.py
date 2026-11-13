"""アプリ全体の設定。すべて環境変数で切り替える（キーがなければデモ用の AI・検索で動く）。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _list(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./studyplan.db"))
    cors_origins: list[str] = field(
        default_factory=lambda: _list(os.getenv("CORS_ORIGINS"), ["http://localhost:3000"])
    )

    # AI: demo | gemini
    ai_provider: str = field(default_factory=lambda: os.getenv("AI_PROVIDER", "demo"))
    gemini_api_key: str | None = field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"))
    gemini_daily_limit: int = field(default_factory=lambda: int(os.getenv("GEMINI_DAILY_LIMIT", "500")))

    # 検索: demo / tavily / qiita / youtube を優先順に並べる
    search_providers: list[str] = field(
        default_factory=lambda: _list(os.getenv("SEARCH_PROVIDERS"), ["demo"])
    )
    tavily_api_key: str | None = field(default_factory=lambda: os.getenv("TAVILY_API_KEY"))
    tavily_monthly_limit: int = field(default_factory=lambda: int(os.getenv("TAVILY_MONTHLY_LIMIT", "1000")))
    qiita_token: str | None = field(default_factory=lambda: os.getenv("QIITA_TOKEN"))
    qiita_hourly_limit: int = field(default_factory=lambda: int(os.getenv("QIITA_HOURLY_LIMIT", "1000")))
    youtube_api_key: str | None = field(default_factory=lambda: os.getenv("YOUTUBE_API_KEY"))
    youtube_daily_search_limit: int = field(
        default_factory=lambda: int(os.getenv("YOUTUBE_DAILY_SEARCH_LIMIT", "100"))
    )

    # 教材探しで検索してよいドメイン（公式ドキュメント系）
    allowed_domains: list[str] = field(
        default_factory=lambda: _list(
            os.getenv("ALLOWED_DOMAINS"),
            [
                "docs.python.org",
                "docs.aws.amazon.com",
                "learn.microsoft.com",
                "developer.mozilla.org",
                "www.postgresql.org",
                "dev.mysql.com",
                "docs.docker.com",
                "kubernetes.io",
                "react.dev",
                "nextjs.org",
                "go.dev",
                "docs.oracle.com",
                "roadmap.sh",
                "qiita.com",
                "zenn.dev",
                "www.youtube.com",
            ],
        )
    )

    # URL の実在チェック（デモ時は外部に接続しないので既定で無効）
    url_check: bool = field(default_factory=lambda: os.getenv("URL_CHECK", "false").lower() == "true")

    # AI の作り直しの最大回数（02-4：最大2回）
    max_ai_retries: int = 2

    # デモ・テスト用に「今日」を固定する（例：2026-12-10）。未設定なら実際の日付
    today_override: str | None = field(default_factory=lambda: os.getenv("TODAY"))

    def today(self):
        import datetime as dt

        if self.today_override:
            return dt.date.fromisoformat(self.today_override)
        return dt.date.today()


settings = Settings()
