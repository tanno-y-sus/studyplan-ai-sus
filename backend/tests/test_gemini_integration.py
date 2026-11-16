"""Gemini 連携：.env の読み込み、エラーの種類分け、失敗したら止める、使用中の AI の表示、接続確認コマンド。

通信はすべて httpx.MockTransport で置き換える（本物の Gemini には接続しない）。
"""

import datetime as dt
import json
import os

import httpx
import pytest

from app.ai.base import AIError, AIUnavailable
from app.ai.check import run as run_check
from app.ai.demo import DemoAI
from app.ai.factory import choose_ai
from app.ai.gemini import GeminiAI
from app.api.deps import ai_provider
from app.config import Settings, load_env_files
from app.main import app
from app.models import Plan
from app.services.schedule import generate_with_checks
from tests.conftest import MEMBER, MENTOR
from tests.test_api import PLAN
from tests.test_schedule_flow import _ctx


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _ok(payload: dict, **extra) -> httpx.Response:
    return httpx.Response(
        200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}, **extra}]}
    )


# ---------------------------------------------------------------- .env の読み込み
def test_env_file_is_loaded_without_overriding(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("STUDYPLAN_T_A=from_file\nSTUDYPLAN_T_B=from_file\n", encoding="utf-8")
    monkeypatch.delenv("STUDYPLAN_NO_DOTENV")
    monkeypatch.delenv("STUDYPLAN_T_A", raising=False)
    monkeypatch.setenv("STUDYPLAN_T_B", "already_set")
    try:
        assert load_env_files(env, tmp_path / "missing.env") == [env]
        assert os.environ["STUDYPLAN_T_A"] == "from_file"
        assert os.environ["STUDYPLAN_T_B"] == "already_set"  # すでにある値は上書きしない
    finally:
        os.environ.pop("STUDYPLAN_T_A", None)


def test_env_file_is_skipped_in_tests(tmp_path):
    env = tmp_path / ".env"
    env.write_text("STUDYPLAN_T_C=x\n", encoding="utf-8")
    assert load_env_files(env) == []
    assert "STUDYPLAN_T_C" not in os.environ


# ---------------------------------------------------------------- エラーの種類分け
@pytest.mark.parametrize(
    ("status", "words"),
    [
        (429, "無料枠"),
        (403, "GEMINI_API_KEY"),
        (400, "GEMINI_API_KEY"),
        (404, "GEMINI_MODEL"),
        (503, "一時的"),
    ],
)
def test_http_errors_become_unavailable_with_japanese_message(status, words):
    ai = GeminiAI("k", "m", client=_client(lambda r: httpx.Response(status, json={"error": {"status": "X"}})))
    with pytest.raises(AIUnavailable) as e:
        ai.normalize_topic("x")
    assert words in str(e.value)
    assert f"（{status}：X）" in str(e.value)


def test_network_error_becomes_unavailable():
    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(AIUnavailable, match="接続できません"):
        GeminiAI("k", "m", client=_client(handler)).normalize_topic("x")


def test_thought_parts_are_ignored():
    payload = {"name": "Docker", "category": "インフラ", "is_it": True}
    res = httpx.Response(
        200,
        json={
            "candidates": [
                {"content": {"parts": [{"text": "考え中…", "thought": True}, {"text": json.dumps(payload)}]}}
            ]
        },
    )
    out = GeminiAI("k", "m", client=_client(lambda r: res)).normalize_topic("docker")
    assert out.name == "Docker"


def test_blocked_and_truncated_answers_are_format_errors():
    blocked = GeminiAI(
        "k",
        "m",
        client=_client(lambda r: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})),
    )
    with pytest.raises(AIError, match="止めました") as e:
        blocked.normalize_topic("x")
    assert not isinstance(e.value, AIUnavailable)  # 作り直しの対象（通信の問題ではない）

    cut = GeminiAI("k", "m", client=_client(lambda r: _ok({"name": "x"}, finishReason="MAX_TOKENS")))
    with pytest.raises(AIError, match="途中で切れました"):
        cut.normalize_topic("x")


# ---------------------------------------------------------------- 失敗したら止める
class DownAI(DemoAI):
    name = "down"

    def __init__(self):
        self.calls = 0

    def generate_schedule(self, ctx):
        self.calls += 1
        raise AIUnavailable("無料枠の上限です")


def test_unavailable_stops_without_retrying():
    ai = DownAI()
    with pytest.raises(AIUnavailable):
        generate_with_checks(ai, _ctx(dt.date(2026, 12, 1), dt.date(2026, 12, 19), 3))
    assert ai.calls == 1  # 作り直しで無料枠を無駄にしない


def test_create_plan_returns_503_and_saves_nothing(client, db_session):
    app.dependency_overrides[ai_provider] = DownAI
    r = client.post("/api/plans", json=PLAN, headers=MEMBER)
    assert r.status_code == 503
    assert r.json()["detail"]["message"] == "無料枠の上限です"
    with db_session() as db:
        assert db.query(Plan).count() == 0


def test_gemini_429_through_api(client):
    gemini = GeminiAI("k", "m", client=_client(lambda r: httpx.Response(429, json={})))
    app.dependency_overrides[ai_provider] = lambda: gemini
    r = client.post("/api/plans", json=PLAN, headers=MEMBER)
    assert r.status_code == 503
    assert "無料枠" in r.json()["detail"]["message"]


# ---------------------------------------------------------------- 使用中の AI
def test_choose_ai():
    assert choose_ai(Settings(ai_provider="demo")).provider == "demo"
    no_key = choose_ai(Settings(ai_provider="gemini", gemini_api_key=None))
    assert no_key.provider == "demo" and "GEMINI_API_KEY が未設定" in no_key.reason
    ok = choose_ai(Settings(ai_provider="gemini", gemini_api_key="k", gemini_model="gemini-x"))
    assert (ok.provider, ok.model) == ("gemini", "gemini-x")
    assert choose_ai(Settings(ai_provider="claude")).provider == "demo"


def test_ai_status_endpoint(client):
    assert client.get("/api/ai/status").status_code == 401
    body = client.get("/api/ai/status", headers=MEMBER).json()
    assert body["provider"] == "demo" and body["configured"] == "demo"
    assert client.get("/api/ai/status", headers=MENTOR).status_code == 200


# ---------------------------------------------------------------- 接続確認コマンド
def test_check_command_success():
    def handler(request: httpx.Request):
        if request.method == "GET":
            return httpx.Response(200, json={"name": "models/m", "displayName": "Gemini M"})
        return _ok({"name": "Python", "category": "言語", "is_it": True})

    lines: list[str] = []
    cfg = Settings(ai_provider="gemini", gemini_api_key="AIzaSecret123", gemini_model="m")
    assert run_check(cfg, client=_client(handler), out=lines.append) is True
    text = "\n".join(lines)
    assert "AIza…（13文字）" in text and "AIzaSecret123" not in text  # キーは全部表示しない
    assert "「パイソン」→「Python」" in text and "準備完了" in text


def test_check_command_lists_models_when_model_is_wrong():
    def handler(request: httpx.Request):
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "models/gemini-ok", "supportedGenerationMethods": ["generateContent"]},
                        {"name": "models/embed", "supportedGenerationMethods": ["embedContent"]},
                    ]
                },
            )
        return httpx.Response(404, json={})

    lines: list[str] = []
    cfg = Settings(ai_provider="gemini", gemini_api_key="k", gemini_model="old-model")
    assert run_check(cfg, client=_client(handler), out=lines.append) is False
    text = "\n".join(lines)
    assert "old-model" in text and "gemini-ok" in text and "embed" not in text


def test_check_command_without_key():
    lines: list[str] = []
    assert run_check(Settings(gemini_api_key=None), out=lines.append) is False
    assert any("未設定" in line for line in lines)


def test_check_command_old_model_is_listed_but_cannot_generate():
    """新しいキーで古いモデルを使うと、モデル情報は取れるのに質問が 404 になる（実際に起きたケース）。"""
    google_msg = "This model models/gemini-2.5-flash-lite is no longer available to new users."

    def handler(request: httpx.Request):
        if request.method == "GET":
            return httpx.Response(200, json={"name": "models/gemini-2.5-flash-lite", "displayName": "Old"})
        return httpx.Response(404, json={"error": {"status": "NOT_FOUND", "message": google_msg}})

    lines: list[str] = []
    cfg = Settings(ai_provider="gemini", gemini_api_key="k", gemini_model="gemini-2.5-flash-lite")
    assert run_check(cfg, client=_client(handler), out=lines.append) is False
    text = "\n".join(lines)
    assert "no longer available to new users" in text  # Google の説明文をそのまま見せる
    assert "gemini-3.1-flash-lite" in text  # 変更先の例
    assert "準備完了" not in text


def test_default_model_is_available_to_new_projects():
    assert Settings().gemini_model == "gemini-3.1-flash-lite"
