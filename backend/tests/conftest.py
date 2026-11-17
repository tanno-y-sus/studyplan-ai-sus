from __future__ import annotations

import os

# 自分の PC の .env（本物の API キー）をテストで読み込まない。app を import する前に設定する
os.environ["STUDYPLAN_NO_DOTENV"] = "1"
# 起動時のテーブル作成が自分の PC の studyplan.db に触れないよう、メモリ上の DB にする
os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db, make_engine
from app.main import app
from app.services.auth import limiter
from tests.catalog import load_catalog

# テストで使うユーザーの Authorization ヘッダー。client fixture が登録・ログインして中身を入れる
ADMIN: dict[str, str] = {}
MEMBER: dict[str, str] = {}
MEMBER2: dict[str, str] = {}
MENTOR: dict[str, str] = {}

PASSWORD = "password-123"


def register(client: TestClient, name: str, email: str, password: str = PASSWORD) -> dict[str, str]:
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert r.status_code == 201, r.text
    client.cookies.clear()  # テストはヘッダーで切り替える（Cookie が残ると混ざる）
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def db_session(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield Session
    engine.dispose()


@pytest.fixture()
def bare_client(db_session):
    """ユーザーも教材カタログもない、空のアプリ。"""

    def _get_db():
        db = db_session()
        try:
            yield db
        finally:
            db.close()

    limiter._fails.clear()
    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def client(bare_client, db_session):
    """テスト用の教材カタログと、管理者・メンバー2人・育成担当を登録したアプリ。"""
    with db_session() as s:
        load_catalog(s)
    ADMIN.clear()
    ADMIN.update(register(bare_client, "管理者", "admin@example.com"))  # 最初の登録者＝管理者
    MEMBER.clear()
    MEMBER.update(register(bare_client, "山田 太郎", "yamada@example.com"))
    MEMBER2.clear()
    MEMBER2.update(register(bare_client, "鈴木 一郎", "suzuki@example.com"))
    MENTOR.clear()
    MENTOR.update(register(bare_client, "佐藤 花子", "sato@example.com"))
    mentor_id = bare_client.get("/api/me", headers=MENTOR).json()["id"]
    r = bare_client.patch(f"/api/admin/users/{mentor_id}", json={"role": "mentor"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    return bare_client
