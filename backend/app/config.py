"""アプリ全体の設定。すべて環境変数で切り替える（キーがなければデモ用の AI・検索で動く）。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent


def load_env_files(*paths: Path) -> list[Path]:
    """.env を読み込む（backend/.env → リポジトリ直下の .env の順）。

    すでに設定されている環境変数は上書きしない。テストでは STUDYPLAN_NO_DOTENV=1 にして読み込まない
    （自分の PC の .env に入れた本物のキーでテストが外部に通信しないようにするため）。
    """
    if os.getenv("STUDYPLAN_NO_DOTENV") == "1":
        return []
    loaded = []
    for path in paths or (BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"):
        if path.is_file():
            load_dotenv(path, override=False)
            loaded.append(path)
    return loaded


ENV_FILES = load_env_files()


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

    # 認証：新規登録できるメールのドメイン（例：example.co.jp。カンマ区切り。空なら制限なし）
    allowed_email_domains: list[str] = field(
        default_factory=lambda: [d.lower().lstrip("@") for d in _list(os.getenv("ALLOWED_EMAIL_DOMAINS"), [])]
    )
    session_days: int = field(default_factory=lambda: int(os.getenv("SESSION_DAYS", "14")))
    # https で公開するときは true（Cookie を https のときだけ送る）
    cookie_secure: bool = field(default_factory=lambda: os.getenv("COOKIE_SECURE", "false").lower() == "true")

    # AI: demo | gemini
    ai_provider: str = field(default_factory=lambda: os.getenv("AI_PROVIDER", "demo"))
    gemini_api_key: str | None = field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"))
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
                "dev.java",
                "docs.spring.io",
                "spring.io",
                "cloud.google.com",
                "www.typescriptlang.org",
                "git-scm.com",
                # 資格試験（公式・過去問サイト）
                "www.ipa.go.jp",
                "www.fe-siken.com",
                "www.ap-siken.com",
                "www.sg-siken.com",
                "www3.jitec.ipa.go.jp",
                "aws.amazon.com",
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
