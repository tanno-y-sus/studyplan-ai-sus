"""共通の依存関係：ログイン中のユーザーと権限の確認、使う AI。

ログイン状態は Cookie（画面から）または Authorization: Bearer（テストや API から）のトークンで確認する。
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.factory import get_ai
from app.db import get_db
from app.models import User
from app.services.auth import user_for_token

COOKIE_NAME = "studyplan_session"


def session_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return request.cookies.get(COOKIE_NAME)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = session_token(request)
    user = user_for_token(db, token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="ログインしてください")
    return user


def require_role(*roles: str):
    def _check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="この操作の権限がありません")
        return user

    return _check


def ai_provider(db: Session = Depends(get_db)) -> AIProvider:
    return get_ai(db)
