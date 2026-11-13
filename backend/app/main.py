from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.seed import seed


@asynccontextmanager
async def lifespan(_: FastAPI):
    # MVP では起動時にテーブルを作り、初期データを入れる（本番は Alembic のマイグレーションに置き換える）
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
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
