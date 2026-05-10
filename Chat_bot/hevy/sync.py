"""Hevy 데이터 동기화.

매일 한 번 호출되어:
  1. 최근 N일 워크아웃을 Hevy API에서 받아 hevy_cache.json에 저장
  2. PR 후보 추출 → 이전과 비교 → 갱신된 항목만 hevy_prs.sqlite에 누적

cron 또는 봇 JobQueue 어느 쪽에서도 호출 가능:
  - CLI: ``python -m hevy.sync``
  - 코드: ``await run_sync()``
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .analytics import extract_pr_candidates
from .client import HevyClient

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent / "data"
DEFAULT_CACHE_PATH = _DATA_DIR / "hevy_cache.json"
DEFAULT_DB_PATH = _DATA_DIR / "hevy_prs.sqlite"

# 캐시 윈도우 (주간 리포트는 7일, PR 추적은 더 길게 보존)
CACHE_DAYS = 30

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS pr_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at TEXT NOT NULL,
    exercise TEXT NOT NULL,
    weight_kg REAL NOT NULL,
    reps INTEGER NOT NULL,
    workout_id TEXT,
    workout_when TEXT
);
CREATE INDEX IF NOT EXISTS idx_pr_exercise ON pr_history(exercise);
CREATE INDEX IF NOT EXISTS idx_pr_detected ON pr_history(detected_at);
"""


# ─── DB 헬퍼 ───────────────────────────────────────────
def ensure_db(db_path: Path) -> None:
    """sqlite 스키마 보장."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_DB_SCHEMA)


def load_prev_prs(db_path: Path) -> dict[str, dict]:
    """종목별 가장 최근 PR row → {exercise: {...}}."""
    if not db_path.exists():
        return {}
    out: dict[str, dict] = {}
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT exercise, weight_kg, reps, workout_id, workout_when
              FROM pr_history
             WHERE id IN (SELECT MAX(id) FROM pr_history GROUP BY exercise)
            """
        ).fetchall()
    for ex, w, r, wid, when in rows:
        out[ex] = {
            "weight_kg": float(w),
            "reps": int(r),
            "workout_id": wid,
            "when": when,
        }
    return out


def record_pr_updates(
    db_path: Path,
    curr: dict[str, dict],
    detected_at: str,
) -> int:
    """이전과 다른 PR만 신규 row로 기록. 반환: 추가 row 수."""
    ensure_db(db_path)
    prev = load_prev_prs(db_path)
    rows = []
    for ex, new in curr.items():
        old = prev.get(ex)
        if (
            old
            and old["weight_kg"] == new["weight_kg"]
            and old["reps"] == new["reps"]
        ):
            continue
        rows.append((
            detected_at,
            ex,
            float(new["weight_kg"]),
            int(new["reps"]),
            new.get("workout_id"),
            new.get("when"),
        ))
    if rows:
        with sqlite3.connect(db_path) as conn:
            conn.executemany(
                """
                INSERT INTO pr_history
                  (detected_at, exercise, weight_kg, reps, workout_id, workout_when)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
    return len(rows)


# ─── 캐시 헬퍼 ──────────────────────────────────────────
def save_cache(cache_path: Path, payload: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_cache(cache_path: Path = DEFAULT_CACHE_PATH) -> dict:
    """캐시 로드. 파일 없거나 깨지면 빈 구조."""
    if not cache_path.exists():
        return {"workouts": [], "synced_at": None, "days": 0}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("hevy_cache.json 파싱 실패, 빈 캐시 반환")
        return {"workouts": [], "synced_at": None, "days": 0}


# ─── 메인 sync ──────────────────────────────────────────
async def run_sync(
    cache_path: Path = DEFAULT_CACHE_PATH,
    db_path: Path = DEFAULT_DB_PATH,
    days: int = CACHE_DAYS,
    client: HevyClient | None = None,
) -> dict:
    """Hevy API에서 데이터 가져와 캐시/PR DB 갱신."""
    detected_at = datetime.now(timezone.utc).isoformat()

    own_client = client is None
    if client is None:
        client = HevyClient()

    try:
        workouts = await client.iter_recent_workouts(days=days)
    finally:
        if own_client:
            await client.aclose()

    save_cache(cache_path, {
        "workouts": workouts,
        "synced_at": detected_at,
        "days": days,
    })

    curr_prs = extract_pr_candidates(workouts)
    new_rows = record_pr_updates(db_path, curr_prs, detected_at)

    return {
        "synced_at": detected_at,
        "workout_count": len(workouts),
        "pr_tracked": len(curr_prs),
        "new_pr_rows": new_rows,
    }


# ─── CLI 엔트리 ────────────────────────────────────────
async def _amain() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    summary = await run_sync()
    log.info("hevy.sync 완료: %s", summary)


def main() -> None:
    """``python -m hevy.sync`` 엔트리."""
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
