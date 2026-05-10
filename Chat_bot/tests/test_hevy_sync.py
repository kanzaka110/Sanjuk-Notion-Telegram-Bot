"""hevy/sync.py 단위 테스트."""

import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hevy.sync import (
    ensure_db,
    load_cache,
    load_prev_prs,
    record_pr_updates,
    run_sync,
    save_cache,
)


# ─── DB ─────────────────────────────────────────────────
def test_ensure_db_creates_table(tmp_path: Path):
    db = tmp_path / "test.sqlite"
    ensure_db(db)
    assert db.exists()
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = [r[0] for r in rows]
    assert "pr_history" in names


def test_load_prev_prs_empty(tmp_path: Path):
    db = tmp_path / "test.sqlite"
    assert load_prev_prs(db) == {}


def test_record_pr_updates_inserts_new(tmp_path: Path):
    db = tmp_path / "test.sqlite"
    curr = {
        "벤치": {"weight_kg": 60.0, "reps": 8, "workout_id": "w1", "when": "2026-05-01"},
    }
    n = record_pr_updates(db, curr, detected_at="2026-05-01T00:00:00Z")
    assert n == 1
    prev = load_prev_prs(db)
    assert prev["벤치"]["weight_kg"] == 60.0


def test_record_pr_updates_skips_unchanged(tmp_path: Path):
    db = tmp_path / "test.sqlite"
    curr = {
        "벤치": {"weight_kg": 60.0, "reps": 8, "workout_id": "w1", "when": "2026-05-01"},
    }
    record_pr_updates(db, curr, "2026-05-01T00:00:00Z")
    n2 = record_pr_updates(db, curr, "2026-05-02T00:00:00Z")  # 동일 PR
    assert n2 == 0  # 신규 row 없음


def test_record_pr_updates_records_progression(tmp_path: Path):
    db = tmp_path / "test.sqlite"
    record_pr_updates(
        db,
        {"벤치": {"weight_kg": 60.0, "reps": 8, "workout_id": "w1", "when": "x"}},
        "2026-05-01T00:00:00Z",
    )
    n2 = record_pr_updates(
        db,
        {"벤치": {"weight_kg": 65.0, "reps": 5, "workout_id": "w2", "when": "y"}},
        "2026-05-08T00:00:00Z",
    )
    assert n2 == 1
    prev = load_prev_prs(db)
    assert prev["벤치"]["weight_kg"] == 65.0


# ─── 캐시 ───────────────────────────────────────────────
def test_save_and_load_cache_roundtrip(tmp_path: Path):
    cache = tmp_path / "cache.json"
    payload = {"workouts": [{"id": "1"}], "synced_at": "ts", "days": 7}
    save_cache(cache, payload)
    loaded = load_cache(cache)
    assert loaded == payload


def test_load_cache_missing_file(tmp_path: Path):
    cache = tmp_path / "missing.json"
    assert load_cache(cache) == {"workouts": [], "synced_at": None, "days": 0}


def test_load_cache_corrupted_file(tmp_path: Path):
    cache = tmp_path / "bad.json"
    cache.write_text("not json {{", encoding="utf-8")
    result = load_cache(cache)
    assert result["workouts"] == []


# ─── run_sync (통합) ───────────────────────────────────
@pytest.mark.asyncio
async def test_run_sync_happy_path(tmp_path: Path):
    """HevyClient mock → 캐시 저장 + PR 기록 동시 검증."""
    cache = tmp_path / "cache.json"
    db = tmp_path / "prs.sqlite"

    fake_workouts = [
        {
            "id": "w1",
            "title": "Push",
            "start_time": "2026-05-08T19:00:00Z",
            "end_time": "2026-05-08T19:45:00Z",
            "exercises": [
                {"title": "벤치", "sets": [{"weight_kg": 60, "reps": 8, "type": "normal"}]},
            ],
        },
    ]

    class _FakeClient:
        async def iter_recent_workouts(self, days):
            return fake_workouts
        async def aclose(self):
            pass

    summary = await run_sync(cache, db, days=7, client=_FakeClient())

    assert summary["workout_count"] == 1
    assert summary["new_pr_rows"] == 1
    assert summary["pr_tracked"] == 1

    # 캐시 검증
    saved = json.loads(cache.read_text(encoding="utf-8"))
    assert saved["workouts"][0]["id"] == "w1"
    assert saved["days"] == 7

    # PR DB 검증
    prev = load_prev_prs(db)
    assert prev["벤치"]["weight_kg"] == 60.0
