"""
산적 수다방 - Claude CLI 클라이언트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Claude CLI subprocess 호출로 대화 응답 생성 (API 비용 $0).
"""

import asyncio
import logging
import re as _re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# shared_config에서 Claude CLI 유틸리티 로드
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared_config import claude_cli

from config import (
    INNER_MONOLOGUE_PROMPT,
    KST,
    PERSONA_ANCHOR,
    SYSTEM_PROMPT,
)
from context_loader import get_full_context
from database import Message
from mood import analyze_mood

log = logging.getLogger(__name__)


class GeminiClient:
    """Claude CLI 기반 대화 클라이언트 (하위 호환성을 위해 클래스명 유지)."""

    def __init__(self) -> None:
        pass

    def get_status(self) -> str:
        """현재 상태를 반환한다."""
        return "현재 모델: Claude Sonnet (CLI)\n추가 API 비용: $0"

    def switch_to_pro(self) -> tuple[bool, str]:
        return True, "Claude CLI 모드에서는 항상 동일한 품질을 제공해!"

    def switch_to_flash(self) -> str:
        return "Claude CLI 모드에서는 항상 동일한 품질을 제공해!"

    def _build_conversation_text(
        self, user_message: str, recent_messages: list[Message]
    ) -> str:
        """대화 히스토리를 텍스트로 변환한다."""
        lines: list[str] = []
        for msg in recent_messages:
            speaker = "승호" if msg.role == "user" else "나"
            lines.append(f"{speaker}: {msg.content}")
        lines.append(f"승호: {user_message}")
        return "\n".join(lines)

    _turn_count: int = 0

    async def _inner_monologue(self, user_message: str) -> str:
        """응답 전 내면 독백을 생성한다 (haiku, 빠른 응답)."""
        try:
            prompt = INNER_MONOLOGUE_PROMPT.format(user_message=user_message[:200])
            result = await asyncio.to_thread(
                claude_cli, prompt, model="haiku", timeout=30,
            )
            return result
        except Exception as e:
            log.debug("내면 독백 생성 실패 (무시): %s", e)
            return ""

    async def ask(
        self,
        user_message: str,
        recent_messages: list[Message],
        memory_context: str = "",
        core_memory_context: str = "",
    ) -> tuple[str, str | None]:
        """Claude CLI로 질문하고 응답을 반환한다.

        Args:
            user_message: 유저 메시지
            recent_messages: 최근 대화 기록
            memory_context: (미사용, 하위 호환성)
            core_memory_context: 코어 메모리

        Returns:
            (응답 텍스트, None)
        """
        GeminiClient._turn_count += 1

        # 1. 분위기 감지
        mood = analyze_mood(user_message, recent_messages)
        mood_hint = f"\n\n[분위기 감지: {mood['mood_hint']}]" if mood["mood_hint"] else ""

        # 2. 내면 독백
        inner_thought = await self._inner_monologue(user_message)
        thought_context = f"\n\n[내부 분석 (사용자에게 보이지 않음): {inner_thought}]" if inner_thought else ""

        # 3. 페르소나 앵커 (10턴마다)
        anchor = ""
        if GeminiClient._turn_count % 10 == 0:
            anchor = f"\n\n{PERSONA_ANCHOR}"

        # 4. 시스템 프롬프트 조합
        system_prompt = (
            SYSTEM_PROMPT
            + mood_hint
            + thought_context
            + anchor
            + ("\n\n" + core_memory_context if core_memory_context else "")
            + "\n\n" + get_full_context()
        )

        # 5. 대화 히스토리 + 현재 메시지를 프롬프트로 구성
        conversation = self._build_conversation_text(user_message, recent_messages)
        prompt = f"""아래는 최근 대화 기록이야. 마지막 승호의 말에 대답해줘.

{conversation}

위 대화의 마지막 승호 메시지에 대한 답변만 써줘. 다른 설명 없이."""

        try:
            answer = await asyncio.to_thread(
                claude_cli, prompt,
                model="sonnet",
                system_prompt=system_prompt,
                timeout=60,
            )

            if not answer:
                answer = "지금 응답 생성이 안 됐어. 잠시 후 다시 말해줘."

            # 괄호 독백 필터링
            answer = _re.sub(r"\([\s\S]*?\)", "", answer).strip()
            answer = _re.sub(r"\n{3,}", "\n\n", answer).strip()
            if not answer:
                answer = "응답을 생성하지 못했어."

        except Exception as e:
            log.error("Claude CLI 오류: %s", e)
            answer = "지금 응답 생성이 안 됐어. 잠시 후 다시 말해줘."

        return answer, None
