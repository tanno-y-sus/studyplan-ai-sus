"""教材探しの検索：デモ教材を本物の検索に切り替えたときの扱いと、使用中の検索の表示。"""

from sqlalchemy import select

from app.ai.demo import DemoAI
from app.config import Settings
from app.models import Material, Topic
from app.schemas import SearchCandidate
from app.search.router import SearchOutcome, search_status
from app.services import materials as materials_service
from app.services.materials import DEMO_RETIRED_COMMENT, materials_for_topic
from tests.conftest import MEMBER
from tests.test_api import PLAN

REAL = [
    SearchCandidate(
        title="Learn Java",
        url="https://dev.java/learn/",
        source="tavily",
        type="official_doc",
        snippet="Java の公式チュートリアル",
    ),
    SearchCandidate(
        title="Java 入門",
        url="https://qiita.com/someone/items/abc",
        source="qiita",
        type="article",
        snippet="所要時間 約30分",
    ),
    SearchCandidate(
        title="Java 入門講座",
        url="https://www.youtube.com/watch?v=xyz",
        source="youtube",
        type="video",
        duration_minutes=40,
    ),
]


def _make_demo_plan(client) -> None:
    """デモ検索（既定）で Java のプランを作り、デモ教材を ai_pending で残す。"""
    r = client.post("/api/plans", json={**PLAN, "topic": "Java"}, headers=MEMBER)
    assert r.status_code == 201, r.text
    assert all(m["source"] in ("demo", "ai") for m in r.json()["materials"])


def test_real_search_replaces_old_demo_materials(client, db_session, monkeypatch):
    _make_demo_plan(client)
    calls = []

    def fake_search(db, topic, providers=None, cfg=None):
        calls.append(topic)
        return SearchOutcome(candidates=REAL, used=["tavily", "qiita", "youtube"])

    monkeypatch.setattr(materials_service, "search_materials", fake_search)
    cfg = Settings(search_providers=["tavily", "qiita", "youtube"], tavily_api_key="k", youtube_api_key="k")
    with db_session() as db:
        topic = db.scalar(select(Topic).where(Topic.name == "Java"))
        chosen, _ = materials_for_topic(db, topic, 2, 4, DemoAI(), cfg=cfg)
        db.commit()

        assert calls == ["Java"]  # デモ教材を使い回さずに検索し直した
        urls = {m.url for m in chosen if m.url}
        assert urls and all("example.com" not in u for u in urls)
        old = db.scalars(
            select(Material).where(Material.topic_id == topic.id, Material.status == "rejected")
        ).all()
        assert old and all(m.source in ("demo", "ai") for m in old)
        assert all(m.review_comment == DEMO_RETIRED_COMMENT for m in old)


def test_demo_search_still_reuses_demo_materials(client, db_session, monkeypatch):
    _make_demo_plan(client)

    def fail(*args, **kwargs):
        raise AssertionError("デモのままなら検索し直さない")

    monkeypatch.setattr(materials_service, "search_materials", fail)
    with db_session() as db:
        topic = db.scalar(select(Topic).where(Topic.name == "Java"))
        chosen, _ = materials_for_topic(db, topic, 2, 4, DemoAI(), cfg=Settings(search_providers=["demo"]))
        assert chosen and all(m.status == "ai_pending" for m in chosen)


def test_search_status():
    assert search_status(Settings(search_providers=["demo"])) == (["demo"], [])
    used, missing = search_status(Settings(search_providers=["tavily", "qiita", "youtube"]))
    assert used == ["qiita"]  # Qiita はキーなしで使える
    assert missing == ["tavily：TAVILY_API_KEY が未設定", "youtube：YOUTUBE_API_KEY が未設定"]
    # すべて使えないときはデモに戻る
    assert search_status(Settings(search_providers=["tavily"]))[0] == ["demo"]


def test_ai_status_includes_search(client):
    body = client.get("/api/ai/status", headers=MEMBER).json()
    assert body["search"] == ["demo"] and body["search_missing"] == []
