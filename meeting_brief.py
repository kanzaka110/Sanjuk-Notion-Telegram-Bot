"""
미팅 사전 브리핑 모듈 — 캘린더 일정 30분 전 자동 브리핑
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared_config import claude_cli

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

_notified_events: set[str] = set()


def get_upcoming_meetings(minutes_ahead: int = 35) -> list[dict]:
    """30~35분 이내 시작하는 미팅을 반환한다."""
    try:
        from google_calendar import _get_service
        service = _get_service()
        if not service:
            return []

        now = datetime.now(KST)
        time_min = now + timedelta(minutes=25)
        time_max = now + timedelta(minutes=minutes_ahead)

        result = service.events().list(
            calendarId="primary",
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = []
        for ev in result.get("items", []):
            if "dateTime" not in ev.get("start", {}):
                continue  # 종일 이벤트 스킵
            event_id = ev["id"]
            if event_id in _notified_events:
                continue
            events.append(ev)
        return events

    except Exception as e:
        log.error("미팅 조회 실패: %s", e)
        return []


def generate_brief(event: dict) -> str:
    """미팅 브리핑을 생성한다."""
    summary = event.get("summary", "(제목 없음)")
    start = event["start"].get("dateTime", "")
    location = event.get("location", "")
    description = event.get("description", "")
    attendees = event.get("attendees", [])

    attendee_list = ", ".join(
        a.get("email", "").split("@")[0] for a in attendees[:10]
    ) if attendees else "참석자 정보 없음"

    start_dt = datetime.fromisoformat(start)
    time_str = start_dt.strftime("%H:%M")

    # RAG에서 관련 컨텍스트 검색
    rag_context = ""
    try:
        from rag_memory import get_relevant_context
        rag_context = get_relevant_context(summary)
    except Exception:
        pass

    prompt = f"""30분 후 미팅이 있어. 비서로서 간단한 사전 브리핑을 해줘.

미팅 정보:
- 제목: {summary}
- 시간: {time_str}
- 장소: {location or '미지정'}
- 참석자: {attendee_list}
- 설명: {description[:300] if description else '없음'}

{rag_context}

브리핑 형식:
1. 미팅 요약 (제목, 시간, 장소)
2. 준비사항 (있으면)
3. 관련 과거 메모 (RAG에서 찾은 것)
4. 한 줄 팁

짧고 실용적으로. 이모지 쓰지 마. 편한 비서 톤으로."""

    result = claude_cli(prompt, model="haiku", timeout=30)
    if result:
        _notified_events.add(event["id"])
    return result or f"[미팅 알림] {time_str} {summary}"


async def check_and_notify(bot, chat_id: int):
    """다가오는 미팅을 체크하고 브리핑을 전송한다."""
    events = await asyncio.to_thread(get_upcoming_meetings)
    for ev in events:
        brief = await asyncio.to_thread(generate_brief, ev)
        if brief:
            await bot.send_message(chat_id=chat_id, text=brief)
            log.info("미팅 브리핑 전송: %s", ev.get("summary", ""))
