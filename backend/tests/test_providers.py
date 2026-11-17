"""外部 API（Gemini・Tavily・Qiita・YouTube）のアダプタ。通信は httpx.MockTransport で置き換える。"""

import datetime as dt
import json

import httpx
import pytest

from app.ai.base import AIError
from app.ai.demo import DemoAI
from app.ai.gemini import GeminiAI
from app.config import Settings
from app.schemas import TopicNormalization
from app.search.providers import QiitaSearch, TavilySearch, YouTubeSearch
from app.search.router import search_materials
from app.services.usage import LimitReached, consume


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_gemini_parses_json_response_and_counts_usage():
    calls = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        assert request.headers["x-goog-api-key"] == "k"
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        payload = {"name": "Docker", "category": "インフラ", "is_it": True}
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}
        )

    ai = GeminiAI("k", "m", on_call=lambda: calls.append(1), client=_client(handler))
    out = ai.normalize_topic("docker")
    assert out == TopicNormalization(name="Docker", category="インフラ", is_it=True)
    assert calls == [1]


def test_gemini_raises_on_bad_format_and_http_error():
    bad = GeminiAI(
        "k",
        "m",
        client=_client(
            lambda r: httpx.Response(
                200, json={"candidates": [{"content": {"parts": [{"text": '{"oops": 1}'}]}}]}
            )
        ),
    )
    with pytest.raises(AIError):
        bad.normalize_topic("x")
    down = GeminiAI("k", "m", client=_client(lambda r: httpx.Response(429, json={})))
    with pytest.raises(AIError):
        down.normalize_topic("x")


def test_tavily_qiita_youtube_parsing():
    tavily = TavilySearch(
        "k",
        ["docs.docker.com"],
        client=_client(
            lambda r: httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "Docker docs",
                            "url": "https://docs.docker.com/get-started/",
                            "content": "...",
                        }
                    ]
                },
            )
        ),
    )
    assert tavily.search("Docker")[0].type == "official_doc"

    qiita = QiitaSearch(
        None,
        client=_client(
            lambda r: httpx.Response(
                200,
                json=[
                    {"title": "Docker 入門", "url": "https://qiita.com/x/items/1", "body": "所要時間 約30分"}
                ],
            )
        ),
    )
    assert qiita.search("Docker")[0].type == "article"

    def yt(request: httpx.Request):
        if request.url.path.endswith("/search"):
            return httpx.Response(
                200, json={"items": [{"id": {"videoId": "abc"}, "snippet": {"title": "Docker 入門"}}]}
            )
        return httpx.Response(200, json={"items": [{"id": "abc", "contentDetails": {"duration": "PT42M"}}]})

    video = YouTubeSearch("k", client=_client(yt)).search("Docker")[0]
    assert video.duration_minutes == 42 and video.url.endswith("v=abc")


class _Stub:
    period_kind = "day"

    def __init__(self, name, results):
        self.name, self.results = name, results

    def search(self, topic):
        return self.results


def test_router_filters_domains_and_skips_when_limit_reached(db_session):
    from app.schemas import SearchCandidate

    cfg = Settings(allowed_domains=["docs.docker.com"])
    ok = SearchCandidate(title="a", url="https://docs.docker.com/x", source="s1", type="official_doc")
    ng = SearchCandidate(title="b", url="https://evil.example.org/x", source="s1", type="article")
    with db_session() as db:
        out = search_materials(
            db, "Docker", providers=[(_Stub("s1", [ok, ng]), 5), (_Stub("s2", [ok]), 0)], cfg=cfg
        )
        assert [c.url for c in out.candidates] == ["https://docs.docker.com/x"]
        assert out.used == ["s1"]
        assert any("許可ドメイン外" in s for s in out.skipped)
        assert any("s2" in s for s in out.skipped)  # 上限0なので飛ばされる


def test_usage_limit(db_session):
    with db_session() as db:
        consume(db, "x", "2026-11-13", 2)
        consume(db, "x", "2026-11-13", 2)
        with pytest.raises(LimitReached):
            consume(db, "x", "2026-11-13", 2)


def test_demo_normalize():
    ai = DemoAI()
    assert ai.normalize_topic("aws").too_broad
    assert not ai.normalize_topic("TOEIC 対策").is_it
    assert ai.normalize_topic("docker").category == "インフラ"
    assert dt.date  # noqa: B018


def test_gemini_skill_checklist():
    items = [{"text": f"できること{i}", "level": lv} for i, lv in enumerate([1, 2, 3, 4, 5, 3])]

    def handler(request: httpx.Request):
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        assert "Java" in prompt and "できる" in prompt
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": json.dumps({"items": items})}]}}]}
        )

    out = GeminiAI("k", "m", client=_client(handler)).skill_checklist("Java", "言語")
    assert [i.level for i in out.items] == [1, 2, 3, 4, 5, 3]
