"""
지식 그래프 메모리 — 관계 기반 사실 저장
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SQLite에 (subject, predicate, object) triplet 저장.
RAG 벡터 검색이 못 잡는 "관계" 기반 회상 담당.

예:
  add_fact("광호", "친구이며", "5/23 부산 SRT 동행")
  add_fact("MAHA", "프로젝트", "시프트업 페이셜팀")
  query_related("광호") → 광호와 연결된 모든 사실
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KG_DB_PATH = os.path.join(_BASE_DIR, "Chat_bot", "data", "knowledge_graph.db")


def _ensure_db() -> None:
    """DB/테이블 초기화 (멱등)."""
    os.makedirs(os.path.dirname(KG_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(KG_DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(subject, predicate, object)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_object ON facts(object)")
        conn.commit()
    finally:
        conn.close()


def add_fact(
    subject: str,
    predicate: str,
    obj: str,
    metadata: dict | None = None,
) -> bool:
    """관계 사실을 추가한다. (subject, predicate, object) 동일 조합은 무시(UNIQUE)."""
    if not subject or not predicate or not obj:
        return False
    _ensure_db()
    conn = sqlite3.connect(KG_DB_PATH)
    try:
        meta_str = json.dumps(metadata, ensure_ascii=False) if metadata else None
        now = datetime.now(KST).isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO facts (subject, predicate, object, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (subject.strip(), predicate.strip(), obj.strip(), meta_str, now),
        )
        conn.commit()
        return conn.total_changes > 0
    except Exception as e:
        log.error("KG add_fact 실패: %s", e)
        return False
    finally:
        conn.close()


def query_related(entity: str, limit: int = 30) -> list[dict]:
    """entity가 subject 또는 object로 등장한 사실을 모두 반환."""
    _ensure_db()
    conn = sqlite3.connect(KG_DB_PATH)
    try:
        cur = conn.execute(
            "SELECT subject, predicate, object, metadata, created_at FROM facts "
            "WHERE subject = ? OR object = ? "
            "ORDER BY id DESC LIMIT ?",
            (entity.strip(), entity.strip(), limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "subject": r[0],
            "predicate": r[1],
            "object": r[2],
            "metadata": json.loads(r[3]) if r[3] else None,
            "created_at": r[4],
        }
        for r in rows
    ]


def query_search(keyword: str, limit: int = 20) -> list[dict]:
    """subject/predicate/object 어디든 keyword 부분일치 검색."""
    _ensure_db()
    conn = sqlite3.connect(KG_DB_PATH)
    try:
        like = f"%{keyword.strip()}%"
        cur = conn.execute(
            "SELECT subject, predicate, object, metadata, created_at FROM facts "
            "WHERE subject LIKE ? OR predicate LIKE ? OR object LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (like, like, like, limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "subject": r[0],
            "predicate": r[1],
            "object": r[2],
            "metadata": json.loads(r[3]) if r[3] else None,
            "created_at": r[4],
        }
        for r in rows
    ]


def format_facts(facts: list[dict]) -> str:
    """사실 리스트를 사람이 읽기 좋게 포맷."""
    if not facts:
        return "(관련 사실 없음)"
    lines = []
    for f in facts:
        lines.append(f"  - {f['subject']} —{f['predicate']}— {f['object']}")
    return "\n".join(lines)


def get_kg_stats() -> dict:
    """그래프 통계."""
    _ensure_db()
    conn = sqlite3.connect(KG_DB_PATH)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM facts")
        total = cur.fetchone()[0]
        cur = conn.execute("SELECT COUNT(DISTINCT subject) FROM facts")
        subjects = cur.fetchone()[0]
    finally:
        conn.close()
    return {"total_facts": total, "distinct_subjects": subjects}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if "--init" in sys.argv:
        _ensure_db()
        print(f"DB 초기화: {KG_DB_PATH}")
    elif "--add" in sys.argv:
        # python knowledge_graph.py --add subject predicate object
        idx = sys.argv.index("--add")
        s, p, o = sys.argv[idx + 1], sys.argv[idx + 2], sys.argv[idx + 3]
        ok = add_fact(s, p, o)
        print("추가 완료" if ok else "이미 존재 또는 실패")
    elif "--query" in sys.argv:
        idx = sys.argv.index("--query")
        entity = sys.argv[idx + 1]
        results = query_related(entity)
        print(format_facts(results))
    elif "--stats" in sys.argv:
        print(get_kg_stats())
    else:
        print("사용법:")
        print("  python knowledge_graph.py --init")
        print("  python knowledge_graph.py --add <subject> <predicate> <object>")
        print("  python knowledge_graph.py --query <entity>")
        print("  python knowledge_graph.py --stats")
