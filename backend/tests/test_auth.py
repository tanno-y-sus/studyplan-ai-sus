"""新規登録・ログイン・ログアウト・パスワード変更・ユーザー管理。"""

import pytest
from sqlalchemy import create_engine, text

from app.api import auth as auth_api
from app.config import Settings
from app.main import OldDatabaseError, check_database
from app.services import auth as auth_service
from app.services.auth import LoginLimiter, hash_password, verify_password
from tests.conftest import ADMIN, MEMBER, MENTOR, PASSWORD, register


def _reg(c, name="田中", email="tanaka@example.com", password=PASSWORD):
    return c.post("/api/auth/register", json={"name": name, "email": email, "password": password})


# ---------------------------------------------------------------- パスワード
def test_password_is_hashed_and_verified():
    stored = hash_password("secret-pass")
    assert "secret-pass" not in stored and stored.startswith("scrypt$")
    assert verify_password("secret-pass", stored)
    assert not verify_password("wrong-pass", stored)
    assert not verify_password("secret-pass", "broken")
    assert hash_password("secret-pass") != stored  # ソルトが毎回違う


# ---------------------------------------------------------------- 新規登録
def test_first_user_is_admin_then_members(bare_client):
    c = bare_client
    assert c.get("/api/auth/config").json()["first_user"] is True
    r = _reg(c, "最初の人", "first@example.com")
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "admin"
    assert c.get("/api/auth/config").json()["first_user"] is False
    c.cookies.clear()
    assert _reg(c, "二人目", "second@example.com").json()["user"]["role"] == "member"


def test_register_logs_in_with_cookie(bare_client):
    c = bare_client
    _reg(c)
    assert "studyplan_session" in c.cookies
    me = c.get("/api/me")  # Cookie だけで入れる
    assert me.status_code == 200 and me.json()["name"] == "田中"
    assert "email" not in me.json() and "password_hash" not in me.json()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"name": "x", "email": "a@example.com", "password": "short"}, "8文字以上"),
        ({"name": " ", "email": "a@example.com", "password": PASSWORD}, "氏名"),
        ({"name": "x", "email": "no-at-mark", "password": PASSWORD}, "形式"),
    ],
)
def test_register_validation(bare_client, body, message):
    r = bare_client.post("/api/auth/register", json=body)
    assert r.status_code == 422 and message in r.json()["detail"]


def test_duplicate_email_ignores_case(bare_client):
    _reg(bare_client, email="Tanaka@Example.com")
    bare_client.cookies.clear()
    r = _reg(bare_client, email="tanaka@example.com")
    assert r.status_code == 422 and "すでに登録" in r.json()["detail"]


def test_allowed_email_domains(bare_client, monkeypatch):
    cfg = Settings(allowed_email_domains=["corp.example.co.jp"])
    monkeypatch.setattr(auth_service, "settings", cfg)
    monkeypatch.setattr(auth_api, "settings", cfg)
    assert bare_client.get("/api/auth/config").json()["allowed_email_domains"] == ["corp.example.co.jp"]
    r = _reg(bare_client, email="someone@gmail.com")
    assert r.status_code == 422 and "@corp.example.co.jp" in r.json()["detail"]
    assert _reg(bare_client, email="someone@corp.example.co.jp").status_code == 201


# ---------------------------------------------------------------- ログイン
def test_login_logout(client):
    client.cookies.clear()
    bad = client.post("/api/auth/login", json={"email": "yamada@example.com", "password": "wrong-pass"})
    assert bad.status_code == 401 and "正しくありません" in bad.json()["detail"]
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert unknown.json()["detail"] == bad.json()["detail"]  # 登録の有無が分からない文にする

    ok = client.post("/api/auth/login", json={"email": "YAMADA@example.com", "password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["user"]["name"] == "山田 太郎"
    assert client.get("/api/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/me").status_code == 401


def test_logout_invalidates_token(client):
    r = client.post("/api/auth/login", json={"email": "yamada@example.com", "password": PASSWORD})
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    client.cookies.clear()
    assert client.get("/api/me", headers=headers).status_code == 200
    client.post("/api/auth/logout", headers=headers)
    assert client.get("/api/me", headers=headers).status_code == 401


def test_old_user_id_header_no_longer_works(client):
    client.cookies.clear()
    assert client.get("/api/me", headers={"X-User-Id": "1"}).status_code == 401
    assert client.get("/api/users").status_code == 404  # 全員の一覧は廃止


def test_login_limiter_blocks_after_failures(client):
    client.cookies.clear()
    for _ in range(10):
        client.post("/api/auth/login", json={"email": "yamada@example.com", "password": "wrong-pass"})
    r = client.post("/api/auth/login", json={"email": "yamada@example.com", "password": PASSWORD})
    assert r.status_code == 401 and "しばらく" in r.json()["detail"]


def test_limiter_window():
    lim = LoginLimiter(max_failures=2, window_seconds=0)
    lim.fail("a")
    lim.fail("a")
    assert not lim.blocked("a")  # 時間が過ぎた失敗は数えない
    lim = LoginLimiter(max_failures=2, window_seconds=60)
    lim.fail("a")
    lim.fail("a")
    assert lim.blocked("a") and not lim.blocked("b")
    lim.reset("a")
    assert not lim.blocked("a")


# ---------------------------------------------------------------- パスワード変更
def test_change_password(client):
    client.cookies.clear()
    wrong = client.post(
        "/api/auth/password",
        json={"current_password": "nope", "new_password": "new-password-1"},
        headers=MEMBER,
    )
    assert wrong.status_code == 422
    short = client.post(
        "/api/auth/password", json={"current_password": PASSWORD, "new_password": "short"}, headers=MEMBER
    )
    assert short.status_code == 422
    ok = client.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "new-password-1"},
        headers=MEMBER,
    )
    assert ok.status_code == 204
    assert client.get("/api/me", headers=MEMBER).status_code == 200  # 変更した端末はそのまま
    old = client.post("/api/auth/login", json={"email": "yamada@example.com", "password": PASSWORD})
    assert old.status_code == 401
    new = client.post("/api/auth/login", json={"email": "yamada@example.com", "password": "new-password-1"})
    assert new.status_code == 200


# ---------------------------------------------------------------- ユーザー管理
def test_admin_user_management(client):
    client.cookies.clear()
    assert client.get("/api/admin/users", headers=MEMBER).status_code == 403
    assert client.get("/api/admin/users", headers=MENTOR).status_code == 403
    users = client.get("/api/admin/users", headers=ADMIN).json()
    assert [u["role"] for u in users] == ["admin", "member", "member", "mentor"]
    assert all("password_hash" not in u for u in users)

    yamada = users[1]["id"]
    r = client.patch(f"/api/admin/users/{yamada}", json={"role": "mentor"}, headers=ADMIN)
    assert r.json()["role"] == "mentor"
    assert client.get("/api/review/materials", headers=MEMBER).status_code == 200  # 育成担当になった
    assert client.patch(f"/api/admin/users/{yamada}", json={"role": "boss"}, headers=ADMIN).status_code == 422


def test_last_admin_cannot_be_demoted(client):
    client.cookies.clear()
    admin_id = client.get("/api/me", headers=ADMIN).json()["id"]
    r = client.patch(f"/api/admin/users/{admin_id}", json={"role": "member"}, headers=ADMIN)
    assert r.status_code == 422 and "管理者が1人もいなくなる" in r.json()["detail"]


def test_temporary_password(client):
    client.cookies.clear()
    yamada = client.get("/api/me", headers=MEMBER).json()["id"]
    assert client.post(f"/api/admin/users/{yamada}/temporary-password", headers=MEMBER).status_code == 403
    temp = client.post(f"/api/admin/users/{yamada}/temporary-password", headers=ADMIN).json()["password"]
    assert client.get("/api/me", headers=MEMBER).status_code == 401  # 今のログインは終わる
    r = client.post("/api/auth/login", json={"email": "yamada@example.com", "password": temp})
    assert r.status_code == 200


def test_new_member_after_admin(client):
    client.cookies.clear()
    headers = register(client, "新人", "newbie@example.com")
    assert client.get("/api/me", headers=headers).json()["role"] == "member"


# ---------------------------------------------------------------- 古い DB
def test_old_database_is_detected(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, role TEXT)"))
    with pytest.raises(OldDatabaseError, match="studyplan.db を削除"):
        check_database(eng)
    check_database(create_engine(f"sqlite:///{tmp_path / 'new.db'}"))  # 空の DB は問題なし
