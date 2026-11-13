"""教材の「参考時間」の読み取り。ページの記載・動画の長さを優先し、分からなければ AI の推定に任せる。"""

from __future__ import annotations

import math
import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"所要時間[^0-9０-９]{0,6}約?\s*([0-9０-９]+(?:\.[0-9]+)?)\s*(分|時間)"), "ja"),
    (re.compile(r"(?:読了|学習)時間[^0-9]{0,6}約?\s*([0-9]+(?:\.[0-9]+)?)\s*(分|時間)"), "ja"),
    (re.compile(r"([0-9]+)\s*(min(?:ute)?s?)\s*read", re.IGNORECASE), "en"),
    (
        re.compile(
            r"(?:takes|duration)[^0-9]{0,10}([0-9]+(?:\.[0-9]+)?)\s*(hours?|minutes?|mins?)", re.IGNORECASE
        ),
        "en",
    ),
]

_ZEN = str.maketrans("０１２３４５６７８９", "0123456789")


def extract_hours(text: str | None) -> tuple[float, str] | None:
    """ページ本文から参考時間を探す。見つかれば（時間, 根拠の文）を返す。

    記事の参考時間は「読む時間」なので、手を動かす時間を足して 1.5 倍にする（最低 0.5 時間）。
    """
    if not text:
        return None
    for pattern, _ in _PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        value = float(m.group(1).translate(_ZEN))
        unit = m.group(2).lower()
        minutes = value * 60 if unit in ("時間", "hour", "hours") else value
        hours = round_half_up(minutes * 1.5 / 60)
        return hours, f"ページに記載「{m.group(0).strip()}」→ 手を動かす時間を足して {hours:g}h"
    return None


def video_hours(minutes: float) -> float:
    """動画は止めながら手を動かすので、長さの 1.5 倍を学習時間とする（0.5 時間単位で切り上げ）。"""
    return round_half_up(minutes * 1.5 / 60)


def round_half_up(hours: float) -> float:
    return max(0.5, math.ceil(hours * 2 - 1e-9) / 2)


def parse_iso8601_duration(value: str) -> float | None:
    """YouTube の長さ（例：PT1H2M30S）を分に変換する。"""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not m:
        return None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 1440 + h * 60 + mi + s / 60
