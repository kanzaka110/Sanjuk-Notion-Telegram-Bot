"""
SQLite 대화 기록 + 사용자 설정 저장소
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
재시작 후에도 대화 맥락과 UE 버전 등 사용자 설정 유지.
"""

import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
DB_PATH = Path(__file__).parent / "data" / "conversations.db"

_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def init_db():
    """테이블 생성 및 data/ 디렉토리 자동 생성."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_conv_chat_time
            ON conversations(chat_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(chat_id, key)
        );
    """)
    conn.commit()


def save_message(chat_id: int, role: str, content: str):
    """메시지 저장 (role: 'user' | 'ai')."""
    now = datetime.now(KST).isoformat()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO conversations (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (chat_id, role, content, now),
    )
    conn.commit()


def get_recent_messages(chat_id: int, limit: int = 20) -> list[str]:
    """최근 N개 메시지를 '사용자: ...' / 'AI: ...' 형태로 반환."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, content FROM conversations WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
        (chat_id, limit),
    ).fetchall()
    result = []
    for row in reversed(rows):
        prefix = "사용자" if row["role"] == "user" else "AI"
        result.append(f"{prefix}: {row['content']}")
    return result


def clear_history(chat_id: int):
    """대화 기록 삭제 (사용자 설정은 유지)."""
    conn = _get_conn()
    conn.execute("DELETE FROM conversations WHERE chat_id = ?", (chat_id,))
    conn.commit()


def set_preference(chat_id: int, key: str, value: str):
    """사용자 설정 저장/갱신 (UPSERT)."""
    now = datetime.now(KST).isoformat()
    conn = _get_conn()
    conn.execute(
        """INSERT INTO user_preferences (chat_id, key, value, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(chat_id, key) DO UPDATE SET value = ?, updated_at = ?""",
        (chat_id, key, value, now, value, now),
    )
    conn.commit()


def get_preference(chat_id: int, key: str) -> str | None:
    """사용자 설정 조회."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT value FROM user_preferences WHERE chat_id = ? AND key = ?",
        (chat_id, key),
    ).fetchone()
    return row["value"] if row else None


def get_all_preferences(chat_id: int) -> dict[str, str]:
    """전체 사용자 설정 조회."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT key, value FROM user_preferences WHERE chat_id = ?",
        (chat_id,),
    ).fetchall()
    return {r["key"]: r["value"] for r in rows}


def detect_ue_version(text: str) -> str | None:
    """메시지에서 UE 버전을 자동 감지. 실패 시 None."""
    patterns = [
        r"(?:UE|언리얼)\s*(\d\.\d+)",
        r"(\d\.\d+)\s*(?:버전|version)",
        r"(?:UE|언리얼 엔진)\s+(\d\.\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def format_user_context(chat_id: int) -> str:
    """사용자 설정을 프롬프트에 주입할 텍스트로 포맷."""
    prefs = get_all_preferences(chat_id)
    if not prefs:
        return ""
    lines = ["━━━ 사용자 컨텍스트 ━━━"]
    if "ue_version" in prefs:
        lines.append(f"  사용 중인 UE 버전: {prefs['ue_version']}")
    for k, v in prefs.items():
        if k != "ue_version":
            lines.append(f"  {k}: {v}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
