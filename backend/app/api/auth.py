"""新規登録・ログイン・ログアウト・パスワード変更（/api/auth）と、ユーザー管理（/api/admin、管理者のみ）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import COOKIE_NAME, current_user, require_role, session_token
from app.config import settings
from app.db import get_db
from app.models import User
from app.schemas import (
    AdminUserOut,
    AuthConfigOut,
    LoginIn,
    PasswordChangeIn,
    RegisterIn,
    RoleUpdateIn,
    TemporaryPasswordOut,
    UserOut,
)
from app.services import auth as auth_service
from app.services.auth import AuthError

router = APIRouter()


def _login_response(response: Response, db: Session, user: User) -> dict:
    token = auth_service.create_session(db, user)
    db.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_days * 24 * 3600,
        httponly=True,  # 画面の JavaScript から読めないようにする
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    # 画面は Cookie を使う。token はテストや API から使う場合のため
    return {"user": UserOut.model_validate(user).model_dump(), "token": token}


# ---------------------------------------------------------------- 認証
@router.get("/auth/config", response_model=AuthConfigOut)
def auth_config(db: Session = Depends(get_db)):
    return AuthConfigOut(
        allowed_email_domains=settings.allowed_email_domains,
        first_user=not auth_service.has_users(db),
        min_password=auth_service.MIN_PASSWORD,
    )


@router.post("/auth/register", status_code=201)
def register(data: RegisterIn, response: Response, db: Session = Depends(get_db)):
    try:
        user = auth_service.register(db, data.name, data.email, data.password)
    except AuthError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from e
    return _login_response(response, db, user)


@router.post("/auth/login")
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    try:
        user = auth_service.authenticate(db, data.email, data.password)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    return _login_response(response, db, user)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = session_token(request)
    if token:
        auth_service.end_session(db, token)
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


@router.post("/auth/password", status_code=204)
def change_password(
    data: PasswordChangeIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if not auth_service.verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=422, detail="今のパスワードが正しくありません")
    try:
        auth_service.check_password_rule(data.new_password)
    except AuthError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    user.password_hash = auth_service.hash_password(data.new_password)
    auth_service.end_all_sessions(db, user, keep_token=session_token(request))  # ほかの端末はログアウト
    db.commit()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


# ---------------------------------------------------------------- ユーザー管理（管理者）
@router.get("/admin/users", response_model=list[AdminUserOut])
def admin_users(db: Session = Depends(get_db), _: User = Depends(require_role("admin"))):
    return db.scalars(select(User).order_by(User.id)).all()


@router.patch("/admin/users/{user_id}", response_model=AdminUserOut)
def admin_update_role(
    user_id: int,
    data: RoleUpdateIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    if target.role == "admin" and data.role != "admin":
        admins = db.scalar(select(func.count()).select_from(User).where(User.role == "admin"))
        if admins <= 1:
            raise HTTPException(status_code=422, detail="管理者が1人もいなくなるため、変更できません")
    target.role = data.role
    db.commit()
    return target


@router.post("/admin/users/{user_id}/temporary-password", response_model=TemporaryPasswordOut)
def admin_temporary_password(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    password = auth_service.temporary_password()
    target.password_hash = auth_service.hash_password(password)
    auth_service.end_all_sessions(db, target)
    db.commit()
    return TemporaryPasswordOut(password=password)
