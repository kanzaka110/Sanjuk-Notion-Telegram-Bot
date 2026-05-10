"""
Habit Tracker — 습관 체크인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
매일 정해진 시간에 봇이 묻는 습관(약/운동 등)에 대해
사용자가 응답한 내용을 누적하고 streak/달성률을 분석.
"""

import logging
import os
import sqlite3
from datetime import datetime, date, timedelta, timezone

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_BASE_DIR, "Chat_bot", "data", "habits.db")

# 봇이 매일 물을 기본 습관 — 사용자 자유 추가도 가능
DEFAULT_HABITS = ["약", "운동"]


def _ensure_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_name TEXT NOT NULL,
                status TEXT NOT NULL,
                note TEXT,
                logged_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(habit_name, logged_date)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_habit_date ON habit_logs(logged_date)")
        conn.commit()
    finally:
        conn.close()


def log_habit(habit_name: str, status: str, note: str = "") -> bool:
    """오늘 날짜로 습관 로그. status는 'done'/'skip'/'partial' 등 자유."""
    _ensure_db()
    today = datetime.now(KST).date().isoformat()
    now = datetime.now(KST).isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO habit_logs (habit_name, status, note, logged_date, created_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(habit_name, logged_date) DO UPDATE SET status = excluded.status, note = excluded.note",
            (habit_name.strip(), status.strip(), note, today, now),
        )
        conn.commit()
        return True
    except Exception as e:
        log.error("habit log 실패: %s", e)
        return False
    finally:
        conn.close()


def get_streak(habit_name: str, max_days: int = 60) -> int:
    """오늘부터 거꾸로 'done' 연속 일수."""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    streak = 0
    try:
        cur_date = datetime.now(KST).date()
        for _ in range(max_days):
            d = cur_date.isoformat()
            cur = conn.execute(
                "SELECT status FROM habit_logs WHERE habit_name = ? AND logged_date = ?",
                (habit_name, d),
            )
            row = cur.fetchone()
            if not row or row[0] != "done":
                break
            streak += 1
            cur_date -= timedelta(days=1)
    finally:
        conn.close()
    return streak


def get_summary(habit_name: str | None = None, days: int = 7) -> str:
    """기간 내 달성률 요약."""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    today = datetime.now(KST).date()
    start = (today - timedelta(days=days - 1)).isoformat()
    try:
        if habit_name:
            cur = conn.execute(
                "SELECT habit_name, status, COUNT(*) FROM habit_logs "
                "WHERE habit_name = ? AND logged_date >= ? "
                "GROUP BY habit_name, status",
                (habit_name, start),
            )
        else:
            cur = conn.execute(
                "SELECT habit_name, status, COUNT(*) FROM habit_logs "
                "WHERE logged_date >= ? "
                "GROUP BY habit_name, status",
                (start,),
            )
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return f"지난 {days}일 습관 기록 없음."

    by_habit: dict[str, dict[str, int]] = {}
    for hname, status, cnt in rows:
        by_habit.setdefault(hname, {})[status] = cnt

    lines = [f"지난 {days}일 습관 요약:"]
    for hname, stats in by_habit.items():
        done = stats.get("done", 0)
        skip = stats.get("skip", 0)
        partial = stats.get("partial", 0)
        total = done + skip + partial
        rate = int(done * 100 / total) if total else 0
        lines.append(f"  - {hname}: {done}/{total} ({rate}%)")
    return "\n".join(lines)


def get_today_pending() -> list[str]:
    """오늘 아직 로그 안 된 기본 습관 목록."""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    today = datetime.now(KST).date().isoformat()
    try:
        cur = conn.execute(
            "SELECT habit_name FROM habit_logs WHERE logged_date = ?", (today,),
        )
        logged = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()
    return [h for h in DEFAULT_HABITS if h not in logged]


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if "--init" in sys.argv:
        _ensure_db()
        print("OK")
    elif "--summary" in sys.argv:
        print(get_summary())
