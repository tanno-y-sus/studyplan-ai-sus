"""検索 API の切り替え。設定順に呼び、無料枠の上限や失敗のときは飛ばして次へ進む（04-7）。"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.schemas import SearchCandidate
from app.search.providers import DemoSearch, QiitaSearch, SearchError, TavilySearch, YouTubeSearch
from app.services.usage import LimitReached, consume, period_key


@dataclass
class SearchOutcome:
    candidates: list[SearchCandidate] = field(default_factory=list)
    used: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def build_providers(cfg: Settings = settings) -> list[tuple[object, int]]:
    """（検索プロバイダ, 無料枠の上限）のリスト。キーがないものは入れない。"""
    out: list[tuple[object, int]] = []
    for name in cfg.search_providers:
        if name == "tavily" and cfg.tavily_api_key:
            out.append((TavilySearch(cfg.tavily_api_key, cfg.allowed_domains), cfg.tavily_monthly_limit))
        elif name == "qiita":
            out.append((QiitaSearch(cfg.qiita_token), cfg.qiita_hourly_limit))
        elif name == "youtube" and cfg.youtube_api_key:
            out.append((YouTubeSearch(cfg.youtube_api_key), cfg.youtube_daily_search_limit))
        elif name == "demo":
            out.append((DemoSearch(), 10_000))
    if not out:
        out.append((DemoSearch(), 10_000))
    return out


def search_materials(
    db: Session, topic: str, providers: list[tuple[object, int]] | None = None, cfg: Settings = settings
) -> SearchOutcome:
    outcome = SearchOutcome()
    allowed = set(cfg.allowed_domains)
    for provider, limit in providers or build_providers(cfg):
        name = provider.name  # type: ignore[attr-defined]
        try:
            consume(db, name, period_key(provider.period_kind), limit)  # type: ignore[attr-defined]
            results = provider.search(topic)  # type: ignore[attr-defined]
        except (LimitReached, SearchError) as e:
            outcome.skipped.append(f"{name}: {e}")
            continue
        for c in results:
            host = c.url.split("/")[2] if "://" in c.url else ""
            if name != "demo" and host not in allowed:
                outcome.skipped.append(f"{name}: 許可ドメイン外のため除外 {host}")
                continue
            outcome.candidates.append(c)
        outcome.used.append(name)
    return outcome
