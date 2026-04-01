"""
산적 수다방 - 벡터 메모리
━━━━━━━━━━━━━━━━━━━━━━━━━
Gemini Embedding API + SQLite로 장기 기억 시맨틱 검색.
최근 20개 한계를 넘어 과거 대화를 의미 기반으로 검색.
"""

import asyncio
import json
import logging
import math
import os
from datetime import datetime

import aiosqlite

from config import DB_PATH, GEMINI_API_KEY, KST

log = logging.getLogger(__name__)

# Gemini 임베딩 클라이언트 (지연 초기화)
_embed_client = None


def _get_embed_client():
    global _embed_client
    if _embed_client is None:
        from google import genai
        _embed_client = genai.Client(api_key=GEMINI_API_KEY)
    return _embed_client


async def init_vector_db() -> None:
    """벡터 메모리 테이블 생성."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS memory_vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT NOT NULL,
                recall_count INTEGER DEFAULT 0,
                importance REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                last_recalled TEXT
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_memvec_chat
            ON memory_vectors (chat_id)
        """)
        # 코어 메모리 테이블 (항상 프롬프트에 포함)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS core_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(chat_id, category, content)
            )
        """)
        # 대화 세그먼트 테이블
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversation_segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                summary TEXT NOT NULL,
                embedding TEXT,
                msg_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def embed_text(text: str) -> list[float] | None:
    """Gemini Embedding API로 텍스트를 벡터로 변환한다."""
    try:
        client = _get_embed_client()
        result = await asyncio.to_thread(
            client.models.embed_content,
            model="gemini-embedding-exp-03-07",
            contents=text[:500],  # 임베딩 입력 제한
        )
        return result.embeddings[0].values
    except Exception as e:
        log.error("임베딩 생성 실패: %s", e)
        return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """코사인 유사도 계산 (numpy 없이)."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _decay_factor(created_at: str, recall_count: int) -> float:
    """시간 감쇠 + 재호출 강화 팩터."""
    try:
        created = datetime.fromisoformat(created_at)
        now = datetime.now(KST)
        days_old = (now - created).total_seconds() / 86400
        decay = math.exp(-days_old / 30)  # 30일 반감기
        recall_boost = 1 + 0.1 * recall_count
        return decay * recall_boost
    except Exception:
        return 0.5


async def store_memory(chat_id: int, content: str, importance: float = 0.5) -> None:
    """메시지를 임베딩하여 벡터 메모리에 저장한다."""
    # 너무 짧은 메시지는 저장하지 않음
    if len(content) < 10:
        return

    embedding = await embed_text(content)
    if not embedding:
        return

    now = datetime.now(KST).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO memory_vectors (chat_id, content, embedding, importance, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, content, json.dumps(embedding), importance, now),
        )
        await db.commit()


async def search_memory(chat_id: int, query: str, top_k: int = 5) -> list[dict]:
    """쿼리와 가장 관련 있는 과거 기억을 검색한다."""
    query_embedding = await embed_text(query)
    if not query_embedding:
        return []

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, content, embedding, recall_count, importance, created_at "
            "FROM memory_vectors WHERE chat_id = ? "
            "ORDER BY id DESC LIMIT 500",  # 최근 500개 내에서 검색
            (chat_id,),
        )
        rows = await cursor.fetchall()

    scored = []
    for row in rows:
        try:
            stored_embedding = json.loads(row[2])
            similarity = _cosine_similarity(query_embedding, stored_embedding)
            decay = _decay_factor(row[5], row[3])
            final_score = similarity * decay * (0.5 + row[4])
            scored.append({
                "id": row[0],
                "content": row[1],
                "score": final_score,
                "created_at": row[5],
            })
        except Exception:
            continue

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_results = scored[:top_k]

    # 검색된 메모리의 recall_count 증가
    if top_results:
        now = datetime.now(KST).isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            for r in top_results:
                await db.execute(
                    "UPDATE memory_vectors SET recall_count = recall_count + 1, last_recalled = ? WHERE id = ?",
                    (now, r["id"]),
                )
            await db.commit()

    return top_results


def format_memory_context(memories: list[dict]) -> str:
    """검색된 기억을 프롬프트에 주입할 텍스트로 포맷."""
    if not memories:
        return ""
    lines = ["━━━ 관련 과거 대화 기억 ━━━"]
    for m in memories:
        date_str = m["created_at"][:10] if m.get("created_at") else ""
        lines.append(f"  [{date_str}] {m['content'][:200]}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ─── 코어 메모리 (항상 프롬프트에 포함) ──────────────────

async def update_core_memory(chat_id: int, category: str, content: str) -> None:
    """코어 메모리 항목을 추가/갱신한다."""
    now = datetime.now(KST).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO core_memory (chat_id, category, content, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(chat_id, category, content) DO UPDATE SET updated_at = ?""",
            (chat_id, category, content, now, now),
        )
        await db.commit()


async def get_core_memory(chat_id: int) -> dict[str, list[str]]:
    """코어 메모리를 카테고리별로 조회한다."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT category, content FROM core_memory WHERE chat_id = ? ORDER BY updated_at DESC",
            (chat_id,),
        )
        rows = await cursor.fetchall()

    result: dict[str, list[str]] = {}
    for cat, content in rows:
        result.setdefault(cat, []).append(content)
    return result


def format_core_memory(core: dict[str, list[str]]) -> str:
    """코어 메모리를 프롬프트 텍스트로 포맷."""
    if not core:
        return ""
    lines = ["━━━ 승호에 대해 기억하고 있는 것 ━━━"]
    category_labels = {
        "fact": "사실",
        "preference": "선호",
        "opinion": "의견",
        "plan": "계획",
        "mood": "상태",
    }
    for cat, items in core.items():
        label = category_labels.get(cat, cat)
        for item in items[:5]:  # 카테고리당 최대 5개
            lines.append(f"  [{label}] {item}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ─── 대화 세그먼트 ──────────────────────────────────────

async def save_segment(chat_id: int, summary: str, msg_count: int) -> None:
    """대화 세그먼트 요약을 저장한다."""
    now = datetime.now(KST).isoformat()
    embedding = await embed_text(summary)
    embedding_json = json.dumps(embedding) if embedding else None

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversation_segments (chat_id, summary, embedding, msg_count, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, summary, embedding_json, msg_count, now),
        )
        await db.commit()


async def get_last_message_time(chat_id: int) -> datetime | None:
    """마지막 메시지 시간을 조회한다."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT created_at FROM conversations WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
            (chat_id,),
        )
        row = await cursor.fetchone()
    if row:
        return datetime.fromisoformat(row[0])
    return None


async def get_user_active_hours(chat_id: int) -> list[tuple[int, int]]:
    """유저의 활동 시간대를 분석한다. (시간, 메시지수) 리스트 반환."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT CAST(strftime('%H', created_at) AS INTEGER) as hour, COUNT(*) as cnt
               FROM conversations WHERE chat_id = ? AND role = 'user'
               GROUP BY hour ORDER BY cnt DESC""",
            (chat_id,),
        )
        rows = await cursor.fetchall()
    return [(r[0], r[1]) for r in rows]
