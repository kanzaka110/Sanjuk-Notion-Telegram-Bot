"""
웹 검색 모듈 — DuckDuckGo 무료 검색
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Claude CLI의 --allowedTools WebSearch 기능을 활용.
별도 API 키 불필요.
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

log = logging.getLogger(__name__)


def search_web(query: str, timeout: int = 30) -> str:
    """Claude CLI의 웹 검색 기능으로 검색한다.

    Args:
        query: 검색 쿼리
        timeout: 타임아웃 (초)

    Returns:
        검색 결과 텍스트
    """
    from shared_config import claude_cli

    prompt = f"""다음 질문에 대해 웹 검색해서 최신 정보를 알려줘.
질문: {query}

규칙:
- 검색 결과를 바탕으로 핵심만 간결하게 정리
- 출처 URL이 있으면 포함
- 한국어로 답변"""

    result = claude_cli(
        prompt, model="haiku",
        web_search=True,
        timeout=timeout,
    )
    return result if result else "검색 결과를 가져오지 못했어."


async def search_web_async(query: str) -> str:
    """비동기 웹 검색."""
    return await asyncio.to_thread(search_web, query)
