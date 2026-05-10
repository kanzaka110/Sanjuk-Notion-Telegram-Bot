"""
수면/컨디션 트래커 — 일별 기록 + 월간 분석
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONDITION_PATH = os.path.join(_BASE_DIR, "data", "condition.json")


def _load() -> list[dict]:
    if not os.path.exists(CONDITION_PATH):
        return []
    with open(CONDITION_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: list[dict]):
    os.makedirs(os.path.dirname(CONDITION_PATH), exist_ok=True)
    with open(CONDITION_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def log_condition(sleep_hours: float, score: int, note: str = "") -> dict:
    """오늘 컨디션 기록.

    Args:
        sleep_hours: 수면 시간
        score: 컨디션 점수 (1-10)
        note: 메모
    """
    data = _load()
    today = datetime.now(KST).strftime("%Y-%m-%d")

    # 오늘 기록이 있으면 덮어쓰기
    data = [d for d in data if d["date"] != today]

    entry = {
        "date": today,
        "sleep": sleep_hours,
        "score": score,
        "note": note,
    }
    data.append(entry)
    _save(data)
    return entry


def get_recent(days: int = 7) -> list[dict]:
    """최근 N일 기록."""
    cutoff = (datetime.now(KST) - timedelta(days=days)).strftime("%Y-%m-%d")
    return [d for d in _load() if d["date"] >= cutoff]


def get_summary(days: int = 30) -> str:
    """기간 요약."""
    records = get_recent(days)
    if not records:
        return "기록 없음"

    avg_sleep = sum(r["sleep"] for r in records) / len(records)
    avg_score = sum(r["score"] for r in records) / len(records)

    lines = [
        f"[최근 {days}일 컨디션]",
        f"평균 수면: {avg_sleep:.1f}시간",
        f"평균 컨디션: {avg_score:.1f}/10",
        f"기록 {len(records)}일",
    ]

    # 최고/최저
    best = max(records, key=lambda r: r["score"])
    worst = min(records, key=lambda r: r["score"])
    lines.append(f"최고: {best['date']} ({best['score']}점, {best['sleep']}h)")
    lines.append(f"최저: {worst['date']} ({worst['score']}점, {worst['sleep']}h)")

    return "\n".join(lines)
