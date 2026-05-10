"""hevy/jobs.py 단위 테스트.

context.bot.send_message는 mock으로 대체. 캐시는 monkeypatch로 우회.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hevy import jobs

KST = timezone(timedelta(hours=9))


def _ctx_with_mock_bot() -> MagicMock:
    """context.bot.send_message가 AsyncMock인 ContextTypes 모방."""
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    return ctx


def _set_cache(monkeypatch, workouts: list[dict]):
    """jobs.load_cache → 주어진 워크아웃 반환."""
    monkeypatch.setattr(
        jobs, "load_cache",
        lambda *a, **k: {"workouts": workouts, "synced_at": "x", "days": 30},
    )


def _set_chat_id(monkeypatch, chat_id: int = 12345):
    monkeypatch.setattr(jobs, "_chat_id", lambda: chat_id)


def _kst_iso(dt: datetime) -> str:
    return dt.isoformat()


# ─── morning_workout ───────────────────────────────────
@pytest.mark.asyncio
async def test_morning_skips_when_no_yesterday_workout(monkeypatch):
    _set_chat_id(monkeypatch)
    _set_cache(monkeypatch, [])
    ctx = _ctx_with_mock_bot()
    await jobs.scheduled_morning_workout(ctx)
    ctx.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_morning_sends_yesterday_workout(monkeypatch):
    _set_chat_id(monkeypatch)
    now_kst = datetime.now(KST)
    yesterday = now_kst.replace(hour=20, minute=0, second=0, microsecond=0) - timedelta(days=1)
    _set_cache(monkeypatch, [{
        "id": "w1",
        "title": "Push",
        "start_time": _kst_iso(yesterday),
        "end_time": _kst_iso(yesterday + timedelta(minutes=45)),
        "exercises": [
            {"title": "벤치", "sets": [{"weight_kg": 60, "reps": 8, "type": "normal"}]},
        ],
    }])
    ctx = _ctx_with_mock_bot()
    await jobs.scheduled_morning_workout(ctx)
    ctx.bot.send_message.assert_called_once()
    sent_text = ctx.bot.send_message.call_args.kwargs["text"]
    assert "벤치" in sent_text


@pytest.mark.asyncio
async def test_morning_skips_workout_from_3_days_ago(monkeypatch):
    """3일 전 운동은 어제가 아니므로 스킵."""
    _set_chat_id(monkeypatch)
    now_kst = datetime.now(KST)
    three_days_ago = now_kst - timedelta(days=3)
    _set_cache(monkeypatch, [{
        "id": "w1",
        "title": "Old",
        "start_time": _kst_iso(three_days_ago),
        "exercises": [],
    }])
    ctx = _ctx_with_mock_bot()
    await jobs.scheduled_morning_workout(ctx)
    ctx.bot.send_message.assert_not_called()


# ─── workout_nudge ─────────────────────────────────────
@pytest.mark.asyncio
async def test_nudge_skips_when_worked_today(monkeypatch):
    """오늘 이미 운동했으면 스킵."""
    _set_chat_id(monkeypatch)
    now_kst = datetime.now(KST)
    today_morning = now_kst.replace(hour=7, minute=0, second=0, microsecond=0)
    _set_cache(monkeypatch, [{
        "id": "w1",
        "start_time": _kst_iso(today_morning),
        "exercises": [],
    }])
    ctx = _ctx_with_mock_bot()
    await jobs.scheduled_workout_nudge(ctx)
    ctx.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_nudge_skips_when_week_threshold_met(monkeypatch):
    """이번주 3회 달성했으면 휴식일로 인정 (스킵)."""
    _set_chat_id(monkeypatch)
    now_kst = datetime.now(KST)
    monday = now_kst - timedelta(days=now_kst.weekday())
    monday = monday.replace(hour=20, minute=0, second=0, microsecond=0)
    _set_cache(monkeypatch, [
        {"id": "1", "start_time": _kst_iso(monday), "exercises": []},
        {"id": "2", "start_time": _kst_iso(monday + timedelta(days=1)), "exercises": []},
        {"id": "3", "start_time": _kst_iso(monday + timedelta(days=2)), "exercises": []},
    ])
    ctx = _ctx_with_mock_bot()
    await jobs.scheduled_workout_nudge(ctx)
    ctx.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_nudge_sends_when_under_threshold(monkeypatch):
    """이번주 < 3회이고 오늘 운동 X면 발송."""
    _set_chat_id(monkeypatch)
    now_kst = datetime.now(KST)
    # 이번주 1회만 (월요일)
    monday = now_kst - timedelta(days=now_kst.weekday())
    monday = monday.replace(hour=20, minute=0, second=0, microsecond=0)
    _set_cache(monkeypatch, [
        {"id": "1", "start_time": _kst_iso(monday), "exercises": []},
    ])
    ctx = _ctx_with_mock_bot()
    await jobs.scheduled_workout_nudge(ctx)
    ctx.bot.send_message.assert_called_once()
    sent = ctx.bot.send_message.call_args.kwargs["text"]
    assert "운동" in sent


@pytest.mark.asyncio
async def test_nudge_skips_when_chat_id_zero(monkeypatch):
    """chat_id=0이면 스킵."""
    _set_chat_id(monkeypatch, chat_id=0)
    _set_cache(monkeypatch, [])
    ctx = _ctx_with_mock_bot()
    await jobs.scheduled_workout_nudge(ctx)
    ctx.bot.send_message.assert_not_called()


# ─── weekly_workout_report ─────────────────────────────
@pytest.mark.asyncio
async def test_weekly_report_includes_count(monkeypatch):
    """지난주 워크아웃 수 + 메시지 발송."""
    _set_chat_id(monkeypatch)
    now_kst = datetime.now(KST)
    last_week_mon = (now_kst - timedelta(days=now_kst.weekday()+7)).replace(
        hour=20, minute=0, second=0, microsecond=0
    )
    _set_cache(monkeypatch, [
        {
            "id": "w1",
            "start_time": _kst_iso(last_week_mon),
            "exercises": [
                {"title": "벤치", "sets": [{"weight_kg": 60, "reps": 8, "type": "normal"}]},
            ],
        },
    ])
    ctx = _ctx_with_mock_bot()
    await jobs.scheduled_weekly_workout_report(ctx)
    ctx.bot.send_message.assert_called_once()
    text = ctx.bot.send_message.call_args.kwargs["text"]
    assert "1회" in text
