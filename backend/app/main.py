from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect

from app.ai.base import AIUnavailable
from app.ai.factory import choose_ai
from app.api.auth import router as auth_router
from app.api.routes import router
from app.config import ENV_FILES, settings
from app.db import Base, engine
from app.search.router import search_status


class OldDatabaseError(RuntimeError):
    pass


def check_database(eng=engine) -> None:
    """以前の版の DB のままなら、作り直しを案内して止める（Alembic は未導入のため、形が変わったら作り直す）。"""
    insp = inspect(eng)
    tables = set(insp.get_table_names())
    old = False
    if "users" in tables and "password_hash" not in {c["name"] for c in insp.get_columns("users")}:
        old = True  # 仮のメンバーを選んでログインしていた版
    if "plans" in tables and "topic_id" in {c["name"] for c in insp.get_columns("plans")}:
        old = True  # 1つのプランに単元が1つだった版
    if old:
        raise OldDatabaseError(
            "以前の版のデータベースです（データの形が変わりました）。"
            "サーバーを止めて backend/studyplan.db を削除し、起動し直してください（データは消えます）"
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 起動時にテーブルを作る（本番は Alembic のマイグレーションに置き換える）。初期データは入れない
    check_database()
    Base.metadata.create_all(engine)
    log = logging.getLogger("uvicorn.error")
    log.info("設定ファイル: %s", ", ".join(str(p) for p in ENV_FILES) or "なし（.env は読み込んでいません）")
    log.info("AI: %s", choose_ai(settings).reason)
    search, missing = search_status(settings)
    log.info("教材の検索: %s", ", ".join(search))
    if "demo" in search:
        log.info(
            "  デモ検索の教材は実在しない URL（example.com）です。.env の SEARCH_PROVIDERS で本物に切り替えられます"
        )
    for m in missing:
        log.info("  使えない検索: %s", m)
    yield


app = FastAPI(title="StudyPlan AI API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api")
app.include_router(router, prefix="/api")


@app.exception_handler(AIUnavailable)
async def ai_unavailable(_: Request, exc: AIUnavailable) -> JSONResponse:
    """Gemini を使えないとき（キー・無料枠・通信・障害）は 503 で理由を返す。デモ AI には切り替えない。"""
    return JSONResponse(status_code=503, content={"detail": {"message": str(exc), "suggestions": []}})
