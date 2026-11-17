"""無料検索 API（04-7）。Tavily（公式ドキュメント中心）・Qiita（日本語記事）・YouTube（動画）・デモ。"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from app.schemas import SearchCandidate
from app.services.reference_time import parse_iso8601_duration


class SearchError(Exception):
    pass


def classify(url: str) -> str:
    host = urlparse(url).netloc
    if "youtube.com" in host or "youtu.be" in host:
        return "video"
    if host.endswith("qiita.com") or host.endswith("zenn.dev"):
        return "article"
    if "roadmap.sh" in host:
        return "roadmap"
    return "official_doc"


class DemoSearch:
    """キーなしで動くデモ検索。URL は example.com のダミー（実在しない）。"""

    name = "demo"
    period_kind = "day"

    def search(self, topic: str, exam: bool = False) -> list[SearchCandidate]:
        slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-") or "topic"
        base = f"https://example.com/demo/{slug}"
        if exam:
            return [
                SearchCandidate(
                    title=f"{topic} 公式シラバス（デモ）",
                    url=f"{base}/syllabus",
                    source="demo",
                    type="official_doc",
                    snippet="出題範囲（シラバス）のデモ候補",
                ),
                SearchCandidate(
                    title=f"{topic} 過去問解説（デモ記事）",
                    url=f"{base}/kakomon",
                    source="demo",
                    type="article",
                    snippet="過去問1回分の解説。所要時間 約60分",
                ),
                SearchCandidate(
                    title=f"{topic} 試験対策講座（デモ動画）",
                    url=f"{base}/video",
                    source="demo",
                    type="video",
                    duration_minutes=60,
                ),
            ]
        return [
            SearchCandidate(
                title=f"{topic} 公式ドキュメント（デモ）",
                url=f"{base}/official",
                source="demo",
                type="official_doc",
                snippet="公式ドキュメントのデモ候補",
            ),
            SearchCandidate(
                title=f"{topic} 入門ハンズオン（デモ記事）",
                url=f"{base}/article",
                source="demo",
                type="article",
                snippet="この記事の所要時間 約40分。手順に沿って環境を作ります",
            ),
            SearchCandidate(
                title=f"{topic} 入門（デモ動画）",
                url=f"{base}/video",
                source="demo",
                type="video",
                duration_minutes=45,
            ),
        ]


class TavilySearch:
    name = "tavily"
    period_kind = "month"
    URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str, allowed_domains: list[str], client: httpx.Client | None = None):
        self.api_key = api_key
        self.domains = [d for d in allowed_domains if "youtube" not in d]
        self.client = client or httpx.Client(timeout=30)

    def search(self, topic: str, exam: bool = False) -> list[SearchCandidate]:
        body = {
            "query": f"{topic} シラバス 出題範囲 過去問 解説"
            if exam
            else f"{topic} 公式ドキュメント チュートリアル 入門",
            "search_depth": "basic",
            "max_results": 8,
            "include_domains": self.domains,
        }
        try:
            res = self.client.post(self.URL, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
            res.raise_for_status()
            results = res.json().get("results", [])
        except (httpx.HTTPError, ValueError) as e:
            raise SearchError(f"Tavily: {e}") from e
        return [
            SearchCandidate(
                title=r.get("title", ""),
                url=r["url"],
                snippet=r.get("content", "")[:500],
                source="tavily",
                type=classify(r["url"]),
            )
            for r in results
            if r.get("url")
        ]


class QiitaSearch:
    name = "qiita"
    period_kind = "hour"
    URL = "https://qiita.com/api/v2/items"

    def __init__(self, token: str | None, client: httpx.Client | None = None):
        self.token = token
        self.client = client or httpx.Client(timeout=30)

    def search(self, topic: str, exam: bool = False) -> list[SearchCandidate]:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        query = f"title:{topic} 対策 stocks:>10" if exam else f"title:{topic} stocks:>20"
        params = {"query": query, "per_page": 5}
        try:
            res = self.client.get(self.URL, params=params, headers=headers)
            res.raise_for_status()
            items = res.json()
        except (httpx.HTTPError, ValueError) as e:
            raise SearchError(f"Qiita: {e}") from e
        return [
            SearchCandidate(
                title=it.get("title", ""),
                url=it["url"],
                snippet=(it.get("body") or "")[:800],
                source="qiita",
                type="article",
            )
            for it in items
            if it.get("url")
        ]


class YouTubeSearch:
    name = "youtube"
    period_kind = "day"
    SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
    VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=30)

    def search(self, topic: str, exam: bool = False) -> list[SearchCandidate]:
        try:
            res = self.client.get(
                self.SEARCH_URL,
                params={
                    "part": "snippet",
                    "type": "video",
                    "q": f"{topic} 解説 対策" if exam else f"{topic} 入門",
                    "maxResults": 5,
                    "relevanceLanguage": "ja",
                    "videoDuration": "medium",
                    "key": self.api_key,
                },
            )
            res.raise_for_status()
            items = res.json().get("items", [])
            ids = [it["id"]["videoId"] for it in items if it.get("id", {}).get("videoId")]
            durations: dict[str, float] = {}
            if ids:
                det = self.client.get(
                    self.VIDEOS_URL,
                    params={"part": "contentDetails", "id": ",".join(ids), "key": self.api_key},
                )
                det.raise_for_status()
                for v in det.json().get("items", []):
                    minutes = parse_iso8601_duration(v.get("contentDetails", {}).get("duration", ""))
                    if minutes:
                        durations[v["id"]] = round(minutes)
        except (httpx.HTTPError, ValueError, KeyError) as e:
            raise SearchError(f"YouTube: {e}") from e
        return [
            SearchCandidate(
                title=it["snippet"]["title"],
                url=f"https://www.youtube.com/watch?v={it['id']['videoId']}",
                snippet=it["snippet"].get("description", "")[:300],
                source="youtube",
                type="video",
                duration_minutes=durations.get(it["id"]["videoId"]),
            )
            for it in items
            if it.get("id", {}).get("videoId")
        ]
