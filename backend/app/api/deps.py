"""共通の依存関係。MVP の認証は簡易（ログイン画面で選んだユーザーの ID を X-User-Id ヘッダーで送る）。

本番では社内 SSO（OIDC）に置き換える前提（Notion 03_付随機能）。
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.factory import get_ai
from app.db import get_db
from app.models import User


def current_user(x_user_id: int | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="ログインしてください")
    user = db.get(User, x_user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="ユーザーが見つかりません")
    return user


def require_role(*roles: str):
    def _check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="この操作の権限がありません")
        return user

    return _check


def ai_provider(db: Session = Depends(get_db)) -> AIProvider:
    return get_ai(db)
