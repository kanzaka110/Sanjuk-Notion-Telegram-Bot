"""
RAG 장기 지식 베이스 — ChromaDB 기반
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
대화 요약을 벡터 DB에 저장하고, 관련 과거 대화를 검색.
"예전에 내가 뭐라 했지?" 같은 질의 지원.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_BASE_DIR, "data", "chroma_db")

_collection = None


def _get_collection():
    """ChromaDB 컬렉션을 반환한다 (싱글톤)."""
    global _collection
    if _collection is not None:
        return _collection

    try:
        import chromadb

        os.makedirs(DB_PATH, exist_ok=True)
        client = chromadb.PersistentClient(path=DB_PATH)
        _collection = client.get_or_create_collection(
            name="conversations",
            metadata={"hnsw:space": "cosine"},
        )
        log.info("ChromaDB 초기화 완료: %d건 저장됨", _collection.count())
        return _collection

    except Exception as e:
        log.error("ChromaDB 초기화 실패: %s", e)
        return None


def store_memory(text: str, metadata: dict | None = None) -> bool:
    """텍스트를 벡터 DB에 저장한다.

    Args:
        text: 저장할 텍스트 (대화 요약, 메모 등)
        metadata: 추가 메타데이터 (date, source 등)

    Returns:
        성공 여부
    """
    collection = _get_collection()
    if not collection:
        return False

    try:
        now = datetime.now(KST)
        doc_id = f"mem_{now.strftime('%Y%m%d_%H%M%S')}_{collection.count()}"

        if metadata is None:
            metadata = {}
        metadata["date"] = now.strftime("%Y-%m-%d")
        metadata["timestamp"] = now.isoformat()

        collection.add(
            documents=[text],
            ids=[doc_id],
            metadatas=[metadata],
        )
        log.info("메모리 저장: %s (%d자)", doc_id, len(text))
        return True

    except Exception as e:
        log.error("메모리 저장 실패: %s", e)
        return False


def search_memory(query: str, n_results: int = 5) -> list[dict]:
    """과거 대화/메모리를 검색한다.

    Args:
        query: 검색 쿼리
        n_results: 반환할 결과 수

    Returns:
        관련 메모리 목록 [{text, date, distance}]
    """
    collection = _get_collection()
    if not collection or collection.count() == 0:
        return []

    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count()),
        )

        memories = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0
            memories.append({
                "text": doc,
                "date": meta.get("date", ""),
                "distance": distance,
            })

        return memories

    except Exception as e:
        log.error("메모리 검색 실패: %s", e)
        return []


def get_relevant_context(query: str, max_chars: int = 1000) -> str:
    """쿼리와 관련된 과거 컨텍스트를 반환한다."""
    memories = search_memory(query, n_results=3)
    if not memories:
        return ""

    lines = []
    total = 0
    for m in memories:
        if m["distance"] > 1.5:  # 관련성 낮으면 스킵
            continue
        entry = f"[{m['date']}] {m['text']}"
        if total + len(entry) > max_chars:
            break
        lines.append(entry)
        total += len(entry)

    if not lines:
        return ""

    return (
        "━━━ 관련 과거 기억 ━━━\n"
        + "\n".join(lines)
        + "\n━━━━━━━━━━━━━━━━━━━"
    )


def get_memory_stats() -> str:
    """메모리 통계를 반환한다."""
    collection = _get_collection()
    if not collection:
        return "RAG 메모리: 미초기화"
    return f"RAG 메모리: {collection.count()}건 저장됨"
