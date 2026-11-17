"""認証（新規登録・ログイン・セッション）。

- パスワードは標準ライブラリの scrypt（ソルト付き）で変換した値だけを保存する
- ログイン中の状態はランダムなトークンで表し、DB には SHA-256 の値だけを保存する
- 最初に登録した人を管理者にする。以降はメンバー（管理者がユーザー管理で変更）
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import AuthSession, User

MIN_PASSWORD = 8
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


class AuthError(ValueError):
    """登録・ログインの失敗（画面にそのまま出せる日本語の文）。"""


# ---------------------------------------------------------------- パスワード
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    b64 = base64.b64encode
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${b64(salt).decode()}${b64(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def check_password_rule(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"パスワードは{MIN_PASSWORD}文字以上にしてください")


def temporary_password() -> str:
    """管理者が発行する仮パスワード（本人がログイン後に変更する）。"""
    return secrets.token_urlsafe(9)


# ---------------------------------------------------------------- 新規登録
def normalize_email(email: str) -> str:
    return email.strip().lower()


def email_allowed(email: str, cfg: Settings | None = None) -> bool:
    cfg = cfg or settings
    if not cfg.allowed_email_domains:
        return True
    domain = email.rsplit("@", 1)[-1]
    return domain in cfg.allowed_email_domains


def has_users(db: Session) -> bool:
    return db.scalar(select(User.id).limit(1)) is not None


def register(db: Session, name: str, email: str, password: str, cfg: Settings | None = None) -> User:
    cfg = cfg or settings
    email = normalize_email(email)
    name = name.strip()
    if not name:
        raise AuthError("氏名を入力してください")
    if "@" not in email:
        raise AuthError("メールアドレスの形式が正しくありません")
    if not email_allowed(email, cfg):
        domains = "・".join(f"@{d}" for d in cfg.allowed_email_domains)
        raise AuthError(f"登録できるのは {domains} のメールアドレスだけです")
    check_password_rule(password)
    if db.scalar(select(User.id).where(func.lower(User.email) == email)) is not None:
        raise AuthError("このメールアドレスはすでに登録されています")
    role = "member" if has_users(db) else "admin"  # 最初の登録者は管理者
    user = User(name=name, email=email, role=role, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------- ログイン
class LoginLimiter:
    """同じメールアドレスでのログイン失敗を数え、続いたら一時的に止める（総当たり対策）。"""

    def __init__(self, max_failures: int = 10, window_seconds: int = 15 * 60):
        self.max_failures = max_failures
        self.window = window_seconds
        self._fails: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque[float]:
        q = self._fails[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._recent(key, time.monotonic())) >= self.max_failures

    def fail(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._recent(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)


limiter = LoginLimiter()


def authenticate(db: Session, email: str, password: str, lim: LoginLimiter = limiter) -> User:
    key = normalize_email(email)
    if lim.blocked(key):
        raise AuthError("ログインの失敗が続いたため、しばらく（15分ほど）待ってからやり直してください")
    user = db.scalar(select(User).where(func.lower(User.email) == key))
    if user is None or not verify_password(password, user.password_hash):
        lim.fail(key)
        raise AuthError("メールアドレスかパスワードが正しくありません")
    lim.reset(key)
    return user


# ---------------------------------------------------------------- セッション
def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _aware(value: dt.datetime) -> dt.datetime:
    # SQLite はタイムゾーンを保存しないので UTC とみなす
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User, cfg: Settings | None = None) -> str:
    cfg = cfg or settings
    db.execute(delete(AuthSession).where(AuthSession.expires_at < _now()))  # 期限切れの掃除
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=_token_hash(token),
            user_id=user.id,
            expires_at=_now() + dt.timedelta(days=cfg.session_days),
        )
    )
    db.flush()
    return token


def user_for_token(db: Session, token: str) -> User | None:
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
    if row is None or _aware(row.expires_at) < _now():
        return None
    return db.get(User, row.user_id)


def end_session(db: Session, token: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == _token_hash(token)))


def end_all_sessions(db: Session, user: User, keep_token: str | None = None) -> None:
    """パスワード変更時に、ほかの端末のログインを終わらせる。"""
    q = delete(AuthSession).where(AuthSession.user_id == user.id)
    if keep_token:
        q = q.where(AuthSession.token_hash != _token_hash(keep_token))
    db.execute(q)
