"""
산적 수다방 - Claude API 직접 호출 클라이언트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OAuth 토큰으로 Anthropic API 직접 호출 (API 비용 $0).
CLI 오버헤드 없이 1~4초 응답.
"""

import asyncio
import logging
import re as _re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from claude_api import chat as claude_chat

from config import SYSTEM_PROMPT
from context_loader import get_essential_context
from database import Message

log = logging.getLogger(__name__)

SESSION_NAME = "chat_bot"


SONNET_MODEL = "claude-sonnet-4-6"
OPUS_MODEL = "claude-opus-4-7"


class GeminiClient:
    """Claude API 직접 호출 대화 클라이언트 (하위 호환성을 위해 클래스명 유지)."""

    def __init__(self) -> None:
        self._deep_mode = False

    def get_status(self) -> str:
        mode = "Opus 4.7 (deep)" if self._deep_mode else "Sonnet 4.6 (기본)"
        return f"현재 모델: Claude {mode} (API 직접 호출)\n추가 API 비용: $0"

    def switch_to_pro(self) -> tuple[bool, str]:
        self._deep_mode = True
        return True, "Opus 4.7 (deep) 모드로 전환. 더 정확하지만 응답이 느려질 수 있어."

    def switch_to_flash(self) -> str:
        self._deep_mode = False
        return "Sonnet 4.6 (기본) 모드로 복귀. 빠르고 가벼운 대화."

    async def ask(
        self,
        user_message: str,
        recent_messages: list[Message],
        memory_context: str = "",
        core_memory_context: str = "",
    ) -> tuple[str, str | None]:
        """Claude API로 대화한다.

        claude_api.chat()이 멀티턴 히스토리를 관리하므로
        recent_messages를 수동으로 붙일 필요 없음.
        """
        # 시스템 프롬프트
        system_prompt = SYSTEM_PROMPT

        # 변동 컨텍스트 (캘린더, 할일)
        essential = get_essential_context()
        if essential:
            system_prompt += f"\n\n[현재 상황]\n{essential}"

        model = OPUS_MODEL if self._deep_mode else SONNET_MODEL

        try:
            answer = await asyncio.to_thread(
                claude_chat,
                user_message,
                session=SESSION_NAME,
                model=model,
                system=system_prompt,
            )

            if not answer:
                answer = "지금 응답 생성이 안 됐어. 잠시 후 다시 말해줘."

            # 괄호 독백 필터링
            answer = _re.sub(r"\([\s\S]*?\)", "", answer).strip()
            answer = _re.sub(r"\n{3,}", "\n\n", answer).strip()
            if not answer:
                answer = "응답을 생성하지 못했어."

        except Exception as e:
            log.error("Claude API 오류: %s", e)
            answer = "지금 응답 생성이 안 됐어. 잠시 후 다시 말해줘."

        return answer, None
