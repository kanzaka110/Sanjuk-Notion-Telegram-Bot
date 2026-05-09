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
_notified_travel: set[str] = set()


def get_upcoming_meetings(minutes_ahead: int = 35) -> list[dict]:
    """30~35분 이내 시작하는 미팅을 모든 CALENDAR_SOURCES에서 가져온다."""
    try:
        from google_calendar import CALENDAR_SOURCES, _get_service, _is_excluded

        now = datetime.now(KST)
        time_min = now + timedelta(minutes=25)
        time_max = now + timedelta(minutes=minutes_ahead)

        events = []
        seen_ids: set[str] = set()
        for account, cid in CALENDAR_SOURCES:
            service = _get_service(account)
            if not service:
                continue
            try:
                result = service.events().list(
                    calendarId=cid,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                ).execute()
            except Exception as e:
                log.error("미팅 조회 실패 (%s/%s): %s", account, cid, e)
                continue

            for ev in result.get("items", []):
                if "dateTime" not in ev.get("start", {}):
                    continue
                if _is_excluded(ev):
                    continue
                event_id = ev["id"]
                if event_id in _notified_events or event_id in seen_ids:
                    continue
                seen_ids.add(event_id)
                ev["_calendar_id"] = cid
                ev["_account"] = account
                events.append(ev)

        events.sort(key=lambda e: e["start"].get("dateTime", ""))
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


def get_travel_alerts(window_min: int = 55, window_max: int = 65) -> list[dict]:
    """위치 있는 이벤트 중 ~1시간 후 시작하는 것 (출발 알림 대상)."""
    try:
        from google_calendar import CALENDAR_SOURCES, _get_service, _is_excluded

        now = datetime.now(KST)
        time_min = now + timedelta(minutes=window_min)
        time_max = now + timedelta(minutes=window_max)

        events = []
        seen_ids: set[str] = set()
        for account, cid in CALENDAR_SOURCES:
            service = _get_service(account)
            if not service:
                continue
            try:
                result = service.events().list(
                    calendarId=cid,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                ).execute()
            except Exception as e:
                log.error("출발 알림 조회 실패 (%s/%s): %s", account, cid, e)
                continue

            for ev in result.get("items", []):
                if "dateTime" not in ev.get("start", {}):
                    continue
                if _is_excluded(ev):
                    continue
                if not ev.get("location"):
                    continue  # 위치 없는 이벤트는 출발 알림 대상 아님
                event_id = ev["id"]
                if event_id in _notified_travel or event_id in seen_ids:
                    continue
                seen_ids.add(event_id)
                events.append(ev)
        return events
    except Exception as e:
        log.error("출발 알림 조회 실패: %s", e)
        return []


def generate_travel_brief(event: dict) -> str:
    """위치 기반 출발 알림 메시지."""
    summary = event.get("summary", "(제목 없음)")
    location = event.get("location", "")
    start = event["start"].get("dateTime", "")
    try:
        start_dt = datetime.fromisoformat(start).astimezone(KST)
        time_str = start_dt.strftime("%H:%M")
    except Exception:
        time_str = "?"
    return (
        f"[출발 알림] 약 1시간 뒤 {time_str} '{summary}'.\n"
        f"위치: {location}\n"
        f"이동시간 + 준비 챙기고 슬슬 나설 시간."
    )


async def check_and_notify(bot, chat_id: int):
    """다가오는 미팅을 체크하고 브리핑을 전송한다."""
    events = await asyncio.to_thread(get_upcoming_meetings)
    for ev in events:
        brief = await asyncio.to_thread(generate_brief, ev)
        if brief:
            await bot.send_message(chat_id=chat_id, text=brief)
            log.info("미팅 브리핑 전송: %s", ev.get("summary", ""))
