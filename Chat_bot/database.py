"""
산적 수다방 - SQLite 대화 저장소
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
aiosqlite 기반 비동기 대화 CRUD.
"""

import os
from dataclasses import dataclass
from datetime import datetime, date

import aiosqlite

from config import DB_PATH, KST


@dataclass(frozen=True)
class Message:
    id: int
    chat_id: int
    role: str
    content: str
    model_used: str
    created_at: datetime


async def init_db() -> None:
    """데이터베이스 테이블 생성."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                model_used TEXT NOT NULL DEFAULT 'flash',
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_date
            ON conversations (chat_id, created_at)
        """)
        await db.commit()


async def save_message(
    chat_id: int,
    role: str,
    content: str,
    model_used: str = "flash",
) -> None:
    """새 메시지를 저장한다 (불변 삽입)."""
    now = datetime.now(KST).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (chat_id, role, content, model_used, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, role, content, model_used, now),
        )
        await db.commit()


async def get_recent_messages(chat_id: int, limit: int = 20) -> list[Message]:
    """최근 N개 메시지를 조회한다 (컨텍스트용)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, chat_id, role, content, model_used, created_at "
            "FROM conversations WHERE chat_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        )
        rows = await cursor.fetchall()

    return [
        Message(
            id=row[0],
            chat_id=row[1],
            role=row[2],
            content=row[3],
            model_used=row[4],
            created_at=datetime.fromisoformat(row[5]),
        )
        for row in reversed(rows)
    ]


async def get_messages_by_date(chat_id: int, target_date: date) -> list[Message]:
    """특정 날짜의 메시지를 조회한다."""
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=KST)
    end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=KST)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, chat_id, role, content, model_used, created_at "
            "FROM conversations WHERE chat_id = ? "
            "AND created_at >= ? AND created_at <= ? "
            "ORDER BY id",
            (chat_id, start.isoformat(), end.isoformat()),
        )
        rows = await cursor.fetchall()

    return [
        Message(
            id=row[0],
            chat_id=row[1],
            role=row[2],
            content=row[3],
            model_used=row[4],
            created_at=datetime.fromisoformat(row[5]),
        )
        for row in rows
    ]


async def get_today_messages(chat_id: int) -> list[Message]:
    """오늘 대화를 조회한다."""
    today = datetime.now(KST).date()
    return await get_messages_by_date(chat_id, today)


async def get_daily_stats(chat_id: int) -> dict[str, int]:
    """오늘 대화 통계를 반환한다."""
    messages = await get_today_messages(chat_id)
    total = len(messages)
    flash_count = sum(1 for m in messages if m.model_used == "flash")
    pro_count = sum(1 for m in messages if m.model_used == "pro")
    return {"total": total, "flash": flash_count, "pro": pro_count}


async def get_messages_since(chat_id: int, since: datetime) -> list[Message]:
    """특정 시점 이후 메시지를 조회한다."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, chat_id, role, content, model_used, created_at "
            "FROM conversations WHERE chat_id = ? AND created_at > ? "
            "ORDER BY id",
            (chat_id, since.isoformat()),
        )
        rows = await cursor.fetchall()

    return [
        Message(
            id=row[0],
            chat_id=row[1],
            role=row[2],
            content=row[3],
            model_used=row[4],
            created_at=datetime.fromisoformat(row[5]),
        )
        for row in rows
    ]


async def get_last_message(chat_id: int) -> Message | None:
    """마지막 메시지를 조회한다."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, chat_id, role, content, model_used, created_at "
            "FROM conversations WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
            (chat_id,),
        )
        row = await cursor.fetchone()

    if row:
        return Message(
            id=row[0], chat_id=row[1], role=row[2],
            content=row[3], model_used=row[4],
            created_at=datetime.fromisoformat(row[5]),
        )
    return None
