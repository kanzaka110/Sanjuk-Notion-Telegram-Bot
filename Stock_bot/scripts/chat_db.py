"""
SQLite 대화 기록 + 매매 기록 저장소
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
재시작 후에도 대화 맥락과 매매 논의 이력 유지.
"""

import os
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

        CREATE TABLE IF NOT EXISTS trade_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            ticker TEXT,
            action TEXT,
            price TEXT,
            reason TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_trade_chat_time
            ON trade_notes(chat_id, created_at DESC);
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
    """대화 기록 삭제 (매매 기록은 유지)."""
    conn = _get_conn()
    conn.execute("DELETE FROM conversations WHERE chat_id = ?", (chat_id,))
    conn.commit()


def save_trade_note(chat_id: int, ticker: str, action: str, price: str, reason: str):
    """매매 기록 저장."""
    now = datetime.now(KST).isoformat()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO trade_notes (chat_id, ticker, action, price, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, ticker, action, price, reason, now),
    )
    conn.commit()


def get_trade_notes(chat_id: int, limit: int = 10) -> list[dict]:
    """최근 매매 기록 조회."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT ticker, action, price, reason, created_at FROM trade_notes WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
        (chat_id, limit),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def format_trade_notes(chat_id: int) -> str:
    """매매 기록을 프롬프트에 주입할 텍스트로 포맷."""
    notes = get_trade_notes(chat_id)
    if not notes:
        return ""
    lines = ["━━━ 최근 매매 논의 이력 ━━━"]
    for n in notes:
        date = n["created_at"][:10]
        lines.append(f"  [{date}] {n['action']} {n['ticker']} @ {n['price']} — {n['reason']}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def extract_trade_from_response(response_text: str) -> dict | None:
    """AI 응답에서 매매 추천 파싱. 실패 시 None."""
    # 패턴: 매수/매도 + 종목명/티커 + 가격
    patterns = [
        r"(매수|매도|진입|손절|청산|buy|sell)\s*[:\-]?\s*([A-Z가-힣\w]+)\s*[/\s@]*\s*([\$₩\d,\.]+)",
        r"(매수|매도)\s+추천\s*[:\-]?\s*([A-Z가-힣\w]+)",
    ]
    for pat in patterns:
        m = re.search(pat, response_text, re.IGNORECASE)
        if m:
            groups = m.groups()
            return {
                "action": groups[0],
                "ticker": groups[1],
                "price": groups[2] if len(groups) > 2 else "",
                "reason": response_text[:100],
            }
    return None
