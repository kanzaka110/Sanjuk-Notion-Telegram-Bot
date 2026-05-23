"""
Google Calendar 일정 관리 모듈
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
자연어 → Claude 파싱 → Calendar 이벤트 생성/수정/삭제.
calendar.events 스코프 필요 (readonly에서 업그레이드).
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(_BASE_DIR, "calendar_token.json")
SCOPES = ["https://www.googleapis.com/auth/calendar"]

_service = None


def _get_service():
    """Calendar API 서비스 (쓰기 권한 포함)."""
    global _service
    if _service is not None:
        return _service

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = None
        if os.path.exists(TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, "w") as f:
                f.write(creds.to_json())

        if not creds or not creds.valid:
            log.warning("Calendar 쓰기 토큰 없음")
            return None

        _service = build("calendar", "v3", credentials=creds)
        return _service

    except Exception as e:
        log.error("Calendar 쓰기 API 실패: %s", e)
        return None


# ─── 일정 검색 ─────────────────────────────────────────
def find_events(query: str, days_range: int = 30) -> list[dict]:
    """키워드로 일정을 검색한다.

    Args:
        query: 검색 키워드
        days_range: 검색 범위 (오늘 기준 앞뒤 days_range일)

    Returns:
        매칭된 이벤트 목록. [{id, summary, start, end}, ...]
    """
    service = _get_service()
    if not service:
        return []

    now = datetime.now(KST)
    time_min = (now - timedelta(days=days_range)).isoformat()
    time_max = (now + timedelta(days=days_range)).isoformat()

    try:
        result = service.events().list(
            calendarId="primary",
            q=query,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=10,
        ).execute()

        events = []
        for e in result.get("items", []):
            start = e["start"].get("dateTime", e["start"].get("date", ""))
            end = e["end"].get("dateTime", e["end"].get("date", ""))
            events.append({
                "id": e["id"],
                "summary": e.get("summary", "(제목 없음)"),
                "start": start,
                "end": end,
                "location": e.get("location", ""),
            })
        return events

    except Exception as e:
        log.error("일정 검색 실패: %s", e)
        return []


# ─── 일정 수정 ─────────────────────────────────────────
def update_event(event_id: str, updates: dict) -> dict | None:
    """기존 일정을 수정한다.

    Args:
        event_id: 수정할 이벤트 ID
        updates: 수정할 필드 {summary, start_time, end_time, location}

    Returns:
        수정된 이벤트 정보. 실패 시 None.
    """
    service = _get_service()
    if not service:
        return None

    try:
        event = service.events().get(
            calendarId="primary", eventId=event_id,
        ).execute()

        if "summary" in updates and updates["summary"]:
            event["summary"] = updates["summary"]
        if "location" in updates and updates["location"]:
            event["location"] = updates["location"]

        if "start_time" in updates and updates["start_time"]:
            st = updates["start_time"]
            if len(st) == 10:
                event["start"] = {"date": st}
            else:
                event["start"] = {"dateTime": st, "timeZone": "Asia/Seoul"}

        if "end_time" in updates and updates["end_time"]:
            et = updates["end_time"]
            if len(et) == 10:
                event["end"] = {"date": et}
            else:
                event["end"] = {"dateTime": et, "timeZone": "Asia/Seoul"}

        updated = service.events().update(
            calendarId="primary", eventId=event_id, body=event,
        ).execute()

        log.info("일정 수정 완료: %s", updated.get("summary"))
        return {
            "id": updated["id"],
            "summary": updated["summary"],
            "start": updated["start"],
        }

    except Exception as e:
        log.error("일정 수정 실패: %s", e)
        return None


# ─── 일정 삭제 ─────────────────────────────────────────
def delete_event(event_id: str) -> bool:
    """일정을 삭제한다."""
    service = _get_service()
    if not service:
        return False

    try:
        service.events().delete(
            calendarId="primary", eventId=event_id,
        ).execute()
        log.info("일정 삭제 완료: %s", event_id)
        return True
    except Exception as e:
        log.error("일정 삭제 실패: %s", e)
        return False


# ─── 일정 생성 ─────────────────────────────────────────
def create_event(summary: str, start_time: str, end_time: str = "",
                 location: str = "", description: str = "") -> dict | None:
    """Google Calendar에 이벤트를 생성한다."""
    service = _get_service()
    if not service:
        return None

    try:
        if len(start_time) == 10:  # YYYY-MM-DD
            event = {
                "summary": summary,
                "start": {"date": start_time},
                "end": {"date": end_time or start_time},
            }
        else:
            if not end_time:
                start_dt = datetime.fromisoformat(start_time)
                end_time = (start_dt + timedelta(hours=1)).isoformat()
            event = {
                "summary": summary,
                "start": {"dateTime": start_time, "timeZone": "Asia/Seoul"},
                "end": {"dateTime": end_time, "timeZone": "Asia/Seoul"},
            }

        if location:
            event["location"] = location
        if description:
            event["description"] = description

        created = service.events().insert(
            calendarId="primary", body=event,
        ).execute()

        log.info("일정 생성 완료: %s", created.get("htmlLink"))
        return {
            "id": created["id"],
            "summary": created["summary"],
            "start": created["start"],
            "link": created.get("htmlLink", ""),
        }

    except Exception as e:
        log.error("일정 생성 실패: %s", e)
        return None


# ─── 자연어 파싱 + 실행 ────────────────────────────────
def _claude_parse(prompt: str) -> str:
    """Claude CLI로 파싱한다."""
    import sys
    sys.path.insert(0, _BASE_DIR)
    from shared_config import claude_cli
    return claude_cli(prompt, model="haiku", timeout=30)


def parse_and_create_event(natural_text: str) -> dict | None:
    """자연어에서 일정 정보를 파싱하여 Calendar에 등록한다."""
    now = datetime.now(KST)
    prompt = f"""다음 텍스트에서 일정 정보를 JSON으로 추출해줘.

텍스트: "{natural_text}"

현재 시각: {now.strftime('%Y-%m-%d %H:%M')} (KST)
현재 요일: {['월','화','수','목','금','토','일'][now.weekday()]}요일

JSON 형식 (이것만 출력):
{{"summary": "제목", "start_time": "YYYY-MM-DDTHH:MM:SS+09:00 또는 YYYY-MM-DD", "end_time": "같은형식 또는 빈문자열", "location": "장소 또는 빈문자열"}}

- "다음 주 화요일" 같은 상대 날짜는 절대 날짜로 변환
- 시간 없으면 종일 이벤트 (YYYY-MM-DD 형식)
- JSON만 출력. 다른 텍스트 금지"""

    result = _claude_parse(prompt)
    if not result:
        return None

    try:
        json_match = re.search(r'\{[^}]+\}', result)
        if not json_match:
            return None
        data = json.loads(json_match.group())

        return create_event(
            summary=data["summary"],
            start_time=data["start_time"],
            end_time=data.get("end_time", ""),
            location=data.get("location", ""),
        )

    except (json.JSONDecodeError, KeyError) as e:
        log.error("일정 파싱 실패: %s / 원본: %s", e, result[:200])
        return None


def parse_and_update_event(natural_text: str) -> str:
    """자연어로 기존 일정을 검색 → 수정한다.

    Returns:
        실행 결과 메시지
    """
    now = datetime.now(KST)
    prompt = f"""사용자가 기존 일정을 수정하려고 해. 텍스트에서 정보를 추출해줘.

텍스트: "{natural_text}"

현재 시각: {now.strftime('%Y-%m-%d %H:%M')} (KST)

JSON 형식 (이것만 출력):
{{"search_keyword": "기존 일정을 찾기 위한 핵심 키워드", "new_start_time": "수정할 시작 시간 (YYYY-MM-DDTHH:MM:SS+09:00 또는 빈문자열)", "new_end_time": "수정할 종료 시간 (같은형식 또는 빈문자열)", "new_summary": "수정할 제목 (변경 없으면 빈문자열)", "new_location": "수정할 장소 (변경 없으면 빈문자열)"}}

- 상대 날짜는 절대 날짜로 변환
- search_keyword는 기존 일정 제목에서 찾을 핵심 단어 (예: "SRT", "미팅", "치과")
- JSON만 출력"""

    result = _claude_parse(prompt)
    if not result:
        return "일정 수정 파싱 실패"

    try:
        json_match = re.search(r'\{[^}]+\}', result)
        if not json_match:
            return "일정 정보 파싱 실패"
        data = json.loads(json_match.group())
    except (json.JSONDecodeError, KeyError):
        return "일정 정보 파싱 실패"

    keyword = data.get("search_keyword", "")
    if not keyword:
        return "검색할 키워드를 파악하지 못했어"

    # 기존 일정 검색
    events = find_events(keyword)
    if not events:
        return f"'{keyword}' 관련 일정을 찾지 못했어"

    # 여러 개면 가장 가까운 미래 일정 선택
    target = events[0]
    for e in events:
        e_start = e["start"]
        if e_start > now.isoformat():
            target = e
            break

    # 수정 적용
    updates = {}
    if data.get("new_start_time"):
        updates["start_time"] = data["new_start_time"]
    if data.get("new_end_time"):
        updates["end_time"] = data["new_end_time"]
    if data.get("new_summary"):
        updates["summary"] = data["new_summary"]
    if data.get("new_location"):
        updates["location"] = data["new_location"]

    if not updates:
        return f"'{target['summary']}' 일정에서 변경할 내용이 없어"

    updated = update_event(target["id"], updates)
    if updated:
        return f"'{target['summary']}' 일정 수정 완료"
    return "일정 수정 실패"


def parse_and_delete_event(natural_text: str) -> str:
    """자연어로 기존 일정을 검색 → 삭제한다.

    Returns:
        실행 결과 메시지
    """
    now = datetime.now(KST)
    prompt = f"""사용자가 일정을 삭제하려고 해. 어떤 일정인지 키워드를 추출해줘.

텍스트: "{natural_text}"

JSON 형식 (이것만 출력):
{{"search_keyword": "삭제할 일정의 핵심 키워드"}}

- JSON만 출력"""

    result = _claude_parse(prompt)
    if not result:
        return "일정 삭제 파싱 실패"

    try:
        json_match = re.search(r'\{[^}]+\}', result)
        if not json_match:
            return "일정 정보 파싱 실패"
        data = json.loads(json_match.group())
    except (json.JSONDecodeError, KeyError):
        return "일정 정보 파싱 실패"

    keyword = data.get("search_keyword", "")
    if not keyword:
        return "검색할 키워드를 파악하지 못했어"

    events = find_events(keyword)
    if not events:
        return f"'{keyword}' 관련 일정을 찾지 못했어"

    # 가장 가까운 미래 일정 삭제
    target = events[0]
    for e in events:
        if e["start"] > now.isoformat():
            target = e
            break

    if delete_event(target["id"]):
        return f"'{target['summary']}' ({target['start'][:10]}) 일정 삭제 완료"
    return "일정 삭제 실패"
