from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.base import AIUnavailable
from app.ai.factory import choose_ai
from app.api.routes import router
from app.config import ENV_FILES, settings
from app.db import Base, SessionLocal, engine
from app.search.router import search_status
from app.seed import seed


@asynccontextmanager
async def lifespan(_: FastAPI):
    # MVP では起動時にテーブルを作り、初期データを入れる（本番は Alembic のマイグレーションに置き換える）
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
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
app.include_router(router, prefix="/api")


@app.exception_handler(AIUnavailable)
async def ai_unavailable(_: Request, exc: AIUnavailable) -> JSONResponse:
    """Gemini を使えないとき（キー・無料枠・通信・障害）は 503 で理由を返す。デモ AI には切り替えない。"""
    return JSONResponse(status_code=503, content={"detail": {"message": str(exc), "suggestions": []}})
