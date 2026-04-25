"""
Google Calendar 일정 생성 모듈
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
자연어 → Claude 파싱 → Calendar 이벤트 생성.
calendar.events 스코프 필요 (readonly에서 업그레이드).
"""

import json
import logging
import os
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


def create_event(summary: str, start_time: str, end_time: str = "",
                 location: str = "", description: str = "") -> dict | None:
    """Google Calendar에 이벤트를 생성한다.

    Args:
        summary: 일정 제목
        start_time: 시작 시간 (ISO 형식 또는 YYYY-MM-DD)
        end_time: 종료 시간 (없으면 1시간 후)
        location: 장소
        description: 설명

    Returns:
        생성된 이벤트 정보. 실패 시 None.
    """
    service = _get_service()
    if not service:
        return None

    try:
        # 종일 이벤트인지 시간 이벤트인지 판단
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


def parse_and_create_event(natural_text: str) -> dict | None:
    """자연어에서 일정 정보를 파싱하여 Calendar에 등록한다.

    Claude CLI로 자연어를 파싱한 후 create_event 호출.
    """
    import sys
    sys.path.insert(0, _BASE_DIR)
    from shared_config import claude_cli

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

    result = claude_cli(
        prompt, model="haiku",
        timeout=30,
    )

    if not result:
        return None

    try:
        # JSON 추출
        import re
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
