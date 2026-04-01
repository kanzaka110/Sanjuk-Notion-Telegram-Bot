"""
산적 수다방 - Gemini 하이브리드 클라이언트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
기본 Flash + /deep 시 Pro 전환, RPD 카운터, 자동 폴백.
"""

import logging
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import TYPE_CHECKING

from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    INNER_MONOLOGUE_PROMPT,
    KST,
    MODEL_FLASH,
    MODEL_PRO,
    PERSONA_ANCHOR,
    PRO_DAILY_LIMIT,
    PRO_WARNING_THRESHOLD,
    SYSTEM_PROMPT,
)
from context_loader import get_full_context
from database import Message
from mood import analyze_mood

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelState:
    current_model: str = MODEL_FLASH
    pro_used_today: int = 0
    last_reset_date: date | None = None


class GeminiClient:
    """Gemini Flash/Pro 하이브리드 클라이언트."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=GEMINI_API_KEY)
        self._state = ModelState()

    @property
    def state(self) -> ModelState:
        return self._state

    def _reset_if_new_day(self) -> None:
        """날짜가 바뀌면 Pro 카운터를 리셋한다."""
        today = datetime.now(KST).date()
        if self._state.last_reset_date != today:
            self._state = replace(
                self._state,
                pro_used_today=0,
                last_reset_date=today,
            )

    def switch_to_pro(self) -> tuple[bool, str]:
        """Pro 모델로 전환을 시도한다."""
        self._reset_if_new_day()
        remaining = PRO_DAILY_LIMIT - self._state.pro_used_today

        if remaining <= 0:
            return False, f"Pro 일일 한도({PRO_DAILY_LIMIT}회) 소진! Flash로 유지할게."

        self._state = replace(self._state, current_model=MODEL_PRO)
        return True, f"Pro 모드로 전환! (오늘 남은 횟수: {remaining}회)"

    def switch_to_flash(self) -> str:
        """Flash 모델로 복귀한다."""
        self._state = replace(self._state, current_model=MODEL_FLASH)
        return "Flash 모드로 복귀!"

    def get_status(self) -> str:
        """현재 상태를 반환한다."""
        self._reset_if_new_day()
        model_name = "Pro" if self._state.current_model == MODEL_PRO else "Flash"
        remaining = PRO_DAILY_LIMIT - self._state.pro_used_today
        return (
            f"현재 모델: Gemini 2.5 {model_name}\n"
            f"Pro 남은 횟수: {remaining}/{PRO_DAILY_LIMIT}회"
        )

    def _check_auto_fallback(self) -> str | None:
        """Pro 80% 도달 시 자동 Flash 전환."""
        if (
            self._state.current_model == MODEL_PRO
            and self._state.pro_used_today >= PRO_WARNING_THRESHOLD
        ):
            self._state = replace(self._state, current_model=MODEL_FLASH)
            return (
                f"Pro {PRO_WARNING_THRESHOLD}회 도달! "
                f"자동으로 Flash 모드로 전환했어."
            )
        return None

    def _build_contents(
        self, user_message: str, recent_messages: list[Message]
    ) -> list[types.Content]:
        """대화 히스토리를 Gemini API 형식으로 변환한다.

        날짜가 바뀌는 지점에 시간 마커를 삽입하여 시간 맥락을 제공한다.
        """
        contents: list[types.Content] = []
        prev_date: date | None = None

        for msg in recent_messages:
            # 날짜가 바뀌면 시간 마커 삽입
            msg_date = msg.created_at.date()
            if prev_date is not None and msg_date != prev_date:
                marker = f"[{msg_date.strftime('%m/%d')} 대화]"
                contents.append(
                    types.Content(role="user", parts=[types.Part(text=marker)])
                )
                contents.append(
                    types.Content(role="model", parts=[types.Part(text="응")])
                )
            prev_date = msg_date

            role = "user" if msg.role == "user" else "model"
            contents.append(
                types.Content(role=role, parts=[types.Part(text=msg.content)])
            )

        contents.append(
            types.Content(role="user", parts=[types.Part(text=user_message)])
        )
        return contents

    _turn_count: int = 0  # 페르소나 앵커링용 턴 카운터

    async def _inner_monologue(self, user_message: str) -> str:
        """응답 전 내면 독백을 생성한다 (Flash, 저비용)."""
        try:
            prompt = INNER_MONOLOGUE_PROMPT.format(user_message=user_message[:200])
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=MODEL_FLASH,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.5,
                    max_output_tokens=128,
                ),
            )
            return response.text or ""
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
        """Gemini에 질문하고 응답을 반환한다.

        Args:
            user_message: 유저 메시지
            recent_messages: 최근 대화 기록
            memory_context: 벡터 메모리 검색 결과
            core_memory_context: 코어 메모리

        Returns:
            (응답 텍스트, 폴백 알림 또는 None)
        """
        self._reset_if_new_day()
        GeminiClient._turn_count += 1

        model = self._state.current_model
        contents = self._build_contents(user_message, recent_messages)

        # 1. 분위기 감지
        mood = analyze_mood(user_message, recent_messages)
        mood_hint = f"\n\n[분위기 감지: {mood['mood_hint']}]" if mood["mood_hint"] else ""

        # 2. 내면 독백 (Flash로 빠르게)
        inner_thought = await self._inner_monologue(user_message)
        thought_context = f"\n\n[내부 분석 (사용자에게 보이지 않음): {inner_thought}]" if inner_thought else ""

        # 3. 페르소나 앵커 (10턴마다)
        anchor = ""
        if GeminiClient._turn_count % 10 == 0:
            anchor = f"\n\n{PERSONA_ANCHOR}"

        # 4. 시스템 인스트럭션 조합
        system_instruction = (
            SYSTEM_PROMPT
            + mood_hint
            + thought_context
            + anchor
            + ("\n\n" + core_memory_context if core_memory_context else "")
            + ("\n\n" + memory_context if memory_context else "")
            + "\n\n" + get_full_context()
        )

        try:
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.85,
                    max_output_tokens=2048,
                ),
            )

            answer = response.text or "응답을 생성하지 못했어."

            # 괄호 독백 필터링 — Gemini가 내면 독백을 응답에 넣는 경우 제거
            import re as _re
            answer = _re.sub(r"\([\s\S]*?\)", "", answer).strip()
            # 빈 줄 정리
            answer = _re.sub(r"\n{3,}", "\n\n", answer).strip()
            if not answer:
                answer = "응답을 생성하지 못했어."

        except Exception as e:
            log.error("Gemini API 오류 (%s): %s", model, e)
            if model == MODEL_PRO:
                self._state = replace(self._state, current_model=MODEL_FLASH)
                return await self.ask(user_message, recent_messages, memory_context, core_memory_context)
            answer = "지금 응답 생성이 안 됐어. 잠시 후 다시 말해줘."

        # Pro 사용 카운터 증가
        if model == MODEL_PRO:
            self._state = replace(
                self._state,
                pro_used_today=self._state.pro_used_today + 1,
            )

        fallback_notice = self._check_auto_fallback()
        return answer, fallback_notice


# asyncio import (ask 메서드에서 사용)
import asyncio  # noqa: E402
