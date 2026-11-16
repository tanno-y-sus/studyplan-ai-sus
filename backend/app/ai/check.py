"""Gemini API の接続確認。backend フォルダで `python -m app.ai.check` を実行する。

1. 設定（.env）を表示する（キーは先頭4文字だけ）
2. キーとモデル名が正しいかを確かめる（モデル情報の取得。回数の消費はほぼなし）
3. 小さな質問を1回送り、決まった形式（JSON）で答えが返るかを確かめる
"""

from __future__ import annotations

import sys
from collections.abc import Callable

import httpx

from app.ai.base import AIError
from app.ai.gemini import GeminiAI, http_error_message
from app.config import ENV_FILES, Settings, settings

MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def mask(key: str | None) -> str:
    if not key:
        return "（未設定）"
    return f"{key[:4]}…（{len(key)}文字）"


def run(
    cfg: Settings = settings, client: httpx.Client | None = None, out: Callable[[str], None] = print
) -> bool:
    out("== Gemini API の接続確認 ==")
    out(f"読み込んだ .env : {', '.join(str(p) for p in ENV_FILES) or 'なし'}")
    out(f"AI_PROVIDER     : {cfg.ai_provider}")
    out(f"GEMINI_MODEL    : {cfg.gemini_model}")
    out(f"GEMINI_API_KEY  : {mask(cfg.gemini_api_key)}")
    if not cfg.gemini_api_key:
        out("NG: GEMINI_API_KEY が未設定です。.env に GEMINI_API_KEY=（取得したキー）を書いてください")
        return False
    if cfg.ai_provider != "gemini":
        out("注意: AI_PROVIDER が gemini ではないため、アプリはデモ AI で動きます（確認は続けます）")

    client = client or httpx.Client(timeout=60)
    headers = {"x-goog-api-key": cfg.gemini_api_key}

    # 2. キーとモデル
    try:
        res = client.get(f"{MODELS_URL}/{cfg.gemini_model}", headers=headers)
    except httpx.HTTPError as e:
        out(
            f"NG: Gemini API に接続できません（{type(e).__name__}）。ネットワークやプロキシを確認してください"
        )
        return False
    if res.status_code == 404:
        out(f"NG: モデル「{cfg.gemini_model}」が見つかりません")
        names = _model_names(client, headers)
        if names:
            out("このキーで使えるモデル（GEMINI_MODEL に設定できる名前）:")
            for n in names:
                out(f"  - {n}")
        return False
    if res.status_code >= 400:
        out(f"NG: {http_error_message(res.status_code, cfg.gemini_model)}")
        return False
    out(f"OK: キーとモデルを確認しました（{res.json().get('displayName', cfg.gemini_model)}）")

    # 3. 小さな質問
    ai = GeminiAI(cfg.gemini_api_key, cfg.gemini_model, client=client)
    try:
        norm = ai.normalize_topic("パイソン")
    except AIError as e:
        out(f"NG: 質問への回答を確認できませんでした: {e}")
        return False
    out(f"OK: 回答を受け取りました（「パイソン」→「{norm.name}」、カテゴリ：{norm.category}）")
    if cfg.ai_provider == "gemini":
        out("準備完了です。サーバーを起動（または再起動）すると Gemini でプランを作ります")
    else:
        out("Gemini を使うには .env に AI_PROVIDER=gemini を書いて、サーバーを再起動してください")
    return True


def _model_names(client: httpx.Client, headers: dict) -> list[str]:
    try:
        res = client.get(MODELS_URL, headers=headers, params={"pageSize": 100})
        res.raise_for_status()
        models = res.json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return []
    return sorted(
        m["name"].removeprefix("models/")
        for m in models
        if "generateContent" in m.get("supportedGenerationMethods", []) and "name" in m
    )


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
