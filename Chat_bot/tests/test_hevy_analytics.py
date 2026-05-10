"""hevy/analytics.py 단위 테스트."""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hevy.analytics import (
    count_workouts_in_week,
    days_since_last_workout,
    diff_prs,
    extract_pr_candidates,
    format_weekly_report,
    format_workout_summary,
    parse_iso,
    week_start,
    workout_duration_minutes,
    workout_set_count,
    workout_volume,
)

KST = timezone(timedelta(hours=9))


def _make_set(weight: float, reps: int, type_: str = "normal") -> dict:
    return {"weight_kg": weight, "reps": reps, "type": type_}


def _make_workout(
    wid: str,
    start_iso: str,
    exercises: list[dict],
    end_iso: str | None = None,
    title: str = "Test",
) -> dict:
    return {
        "id": wid,
        "title": title,
        "start_time": start_iso,
        "end_time": end_iso,
        "exercises": exercises,
    }


# ─── workout_volume ─────────────────────────────────────
def test_volume_excludes_warmup():
    """warmup 세트는 볼륨에서 제외."""
    w = _make_workout("a", "2026-05-09T19:30:00Z", [
        {"title": "벤치", "sets": [
            _make_set(40, 10, "warmup"),
            _make_set(60, 8),
            _make_set(60, 8),
        ]},
    ])
    assert workout_volume(w) == 60 * 8 + 60 * 8


def test_volume_empty_workout():
    w = _make_workout("a", "2026-05-09T19:30:00Z", [])
    assert workout_volume(w) == 0


def test_volume_handles_missing_fields():
    """weight_kg/reps None 또는 0이면 스킵."""
    w = _make_workout("a", "2026-05-09T19:30:00Z", [
        {"title": "x", "sets": [
            {"weight_kg": None, "reps": 5, "type": "normal"},
            {"weight_kg": 50, "reps": None, "type": "normal"},
            _make_set(50, 5),
        ]},
    ])
    assert workout_volume(w) == 50 * 5


# ─── set_count ──────────────────────────────────────────
def test_set_count_excludes_warmup():
    w = _make_workout("a", "2026-05-09T19:30:00Z", [
        {"title": "x", "sets": [
            _make_set(40, 10, "warmup"),
            _make_set(60, 8),
            _make_set(60, 8),
        ]},
    ])
    assert workout_set_count(w) == 2


# ─── duration ──────────────────────────────────────────
def test_duration_minutes():
    w = _make_workout(
        "a", "2026-05-09T19:00:00Z", [],
        end_iso="2026-05-09T19:45:00Z",
    )
    assert workout_duration_minutes(w) == 45


def test_duration_no_end_time():
    w = _make_workout("a", "2026-05-09T19:00:00Z", [])
    assert workout_duration_minutes(w) is None


# ─── week_start ──────────────────────────────────────────
def test_week_start_monday():
    """월요일은 그대로 자정."""
    mon = datetime(2026, 5, 4, 14, 30, tzinfo=timezone.utc)  # 월요일
    ws = week_start(mon, timezone.utc)
    assert ws.weekday() == 0
    assert ws.hour == 0


def test_week_start_sunday_returns_previous_monday():
    """일요일이면 6일 전 월요일."""
    sun = datetime(2026, 5, 10, 14, 30, tzinfo=timezone.utc)
    ws = week_start(sun, timezone.utc)
    assert ws.weekday() == 0
    assert ws.day == 4


# ─── count_workouts_in_week ────────────────────────────
def test_count_workouts_this_week_kst():
    """KST 기준 이번주(2026-05-04 월 ~ 05-10 일)."""
    now = datetime(2026, 5, 10, 22, 0, tzinfo=KST)
    workouts = [
        {"id": "1", "start_time": "2026-05-05T10:00:00+09:00"},  # 화 (이번주)
        {"id": "2", "start_time": "2026-05-08T20:00:00+09:00"},  # 금 (이번주)
        {"id": "3", "start_time": "2026-05-03T20:00:00+09:00"},  # 일 (지난주)
    ]
    assert count_workouts_in_week(workouts, now, KST) == 2


# ─── days_since_last_workout ────────────────────────────
def test_days_since_last_workout():
    now = datetime(2026, 5, 10, 21, 0, tzinfo=KST)
    workouts = [
        {"start_time": "2026-05-08T20:00:00+09:00"},
        {"start_time": "2026-05-07T20:00:00+09:00"},
    ]
    assert days_since_last_workout(workouts, now) == 2


def test_days_since_no_workouts():
    now = datetime(2026, 5, 10, 21, 0, tzinfo=KST)
    assert days_since_last_workout([], now) == 999


# ─── extract_pr_candidates ─────────────────────────────
def test_extract_pr_picks_max_weight():
    workouts = [
        _make_workout("w1", "2026-05-01T10:00:00Z", [
            {"title": "벤치", "sets": [_make_set(60, 8), _make_set(65, 5)]},
        ]),
        _make_workout("w2", "2026-05-08T10:00:00Z", [
            {"title": "벤치", "sets": [_make_set(70, 3)]},
        ]),
    ]
    prs = extract_pr_candidates(workouts)
    assert prs["벤치"]["weight_kg"] == 70
    assert prs["벤치"]["reps"] == 3
    assert prs["벤치"]["workout_id"] == "w2"


def test_extract_pr_tiebreak_by_reps():
    """동일 무게면 reps 많은 게 PR."""
    workouts = [
        _make_workout("w1", "2026-05-01T10:00:00Z", [
            {"title": "스쿼트", "sets": [_make_set(80, 5)]},
        ]),
        _make_workout("w2", "2026-05-08T10:00:00Z", [
            {"title": "스쿼트", "sets": [_make_set(80, 8)]},
        ]),
    ]
    prs = extract_pr_candidates(workouts)
    assert prs["스쿼트"]["reps"] == 8


def test_extract_pr_skips_warmup():
    workouts = [
        _make_workout("w1", "2026-05-01T10:00:00Z", [
            {"title": "벤치", "sets": [
                _make_set(100, 5, "warmup"),  # 워밍업이라 PR 후보 X
                _make_set(60, 5),
            ]},
        ]),
    ]
    prs = extract_pr_candidates(workouts)
    assert prs["벤치"]["weight_kg"] == 60


# ─── diff_prs ──────────────────────────────────────────
def test_diff_prs_new_exercise():
    prev = {}
    curr = {"벤치": {"weight_kg": 60, "reps": 8, "workout_id": "x", "when": "..."}}
    updates = diff_prs(prev, curr)
    assert len(updates) == 1
    assert updates[0]["old_weight"] == 0


def test_diff_prs_weight_increased():
    prev = {"벤치": {"weight_kg": 60, "reps": 8, "workout_id": "x", "when": "..."}}
    curr = {"벤치": {"weight_kg": 65, "reps": 5, "workout_id": "y", "when": "..."}}
    updates = diff_prs(prev, curr)
    assert len(updates) == 1
    assert updates[0]["new_weight"] == 65


def test_diff_prs_no_change():
    prev = {"벤치": {"weight_kg": 60, "reps": 8, "workout_id": "x", "when": "..."}}
    curr = {"벤치": {"weight_kg": 60, "reps": 8, "workout_id": "x", "when": "..."}}
    assert diff_prs(prev, curr) == []


# ─── format_workout_summary ────────────────────────────
def test_format_summary_contains_title_and_volume():
    w = _make_workout(
        "a", "2026-05-09T19:00:00Z",
        [{"title": "벤치프레스", "sets": [_make_set(60, 8), _make_set(60, 7)]}],
        end_iso="2026-05-09T19:45:00Z",
        title="가슴/삼두",
    )
    text = format_workout_summary(w)
    assert "가슴/삼두" in text
    assert "벤치프레스" in text
    assert "60kg" in text
    assert "총 볼륨" in text


# ─── format_weekly_report ──────────────────────────────
def test_format_weekly_report_zero_workouts():
    text = format_weekly_report([], [])
    assert "0회" in text


def test_format_weekly_report_with_pr():
    w = _make_workout("a", "2026-05-08T10:00:00Z", [
        {"title": "벤치", "sets": [_make_set(60, 8), _make_set(60, 8)]},
    ])
    pr_updates = [{
        "exercise": "벤치",
        "old_weight": 55, "old_reps": 8,
        "new_weight": 60, "new_reps": 8,
    }]
    text = format_weekly_report([w], pr_updates)
    assert "1회" in text
    assert "신기록" in text
    assert "벤치" in text
