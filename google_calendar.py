"""
Google Calendar 연동 모듈 — 운세·수다 봇 공유
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GCP 서비스 계정으로 Google Calendar API에 접근하여
오늘/이번 주/이번 달 일정을 가져온다.

설정 필요:
  1. GCP Console에서 Calendar API 활성화
  2. 서비스 계정 생성 → JSON 키 다운로드
  3. Google Calendar 설정에서 서비스 계정 이메일에 캘린더 공유
  4. 환경변수: GOOGLE_CALENDAR_CREDENTIALS (JSON 키 경로)
             GOOGLE_CALENDAR_ID (캘린더 ID, 기본값: primary)
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 환경변수
CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_CALENDAR_CREDENTIALS",
    os.path.join(os.path.dirname(__file__), "calendar_credentials.json"),
)
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")

_service = None


def _get_service():
    """Google Calendar API 서비스 객체를 반환한다 (싱글톤)."""
    global _service
    if _service is not None:
        return _service

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        if not os.path.exists(CREDENTIALS_PATH):
            log.warning("Calendar 인증 파일 없음: %s", CREDENTIALS_PATH)
            return None

        creds = Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        _service = build("calendar", "v3", credentials=creds)
        log.info("Google Calendar API 연결 성공")
        return _service

    except ImportError:
        log.warning("google-api-python-client 미설치. pip install google-api-python-client")
        return None
    except Exception as e:
        log.error("Google Calendar API 초기화 실패: %s", e)
        return None


def _fetch_events(time_min: datetime, time_max: datetime) -> list[dict[str, Any]]:
    """지정 기간의 이벤트를 가져온다."""
    service = _get_service()
    if not service:
        return []

    try:
        result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        ).execute()
        return result.get("items", [])
    except Exception as e:
        log.error("Calendar 이벤트 조회 실패: %s", e)
        return []


def _format_event(event: dict) -> str:
    """이벤트 하나를 읽기 좋은 문자열로 변환한다."""
    summary = event.get("summary", "(제목 없음)")
    location = event.get("location", "")

    start = event.get("start", {})
    end = event.get("end", {})

    if "dateTime" in start:
        start_dt = datetime.fromisoformat(start["dateTime"])
        end_dt = datetime.fromisoformat(end["dateTime"])
        time_str = f"{start_dt.strftime('%H:%M')}~{end_dt.strftime('%H:%M')}"
    elif "date" in start:
        time_str = "종일"
    else:
        time_str = ""

    parts = [f"- {time_str} {summary}"]
    if location:
        parts[0] += f" ({location})"
    return parts[0]


def _format_day_events(date: datetime, events: list[dict]) -> str:
    """특정 날짜의 이벤트를 포맷한다."""
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"]
    day_name = weekday_kr[date.weekday()]
    header = f"{date.month}/{date.day}({day_name})"

    day_events = []
    for ev in events:
        start = ev.get("start", {})
        if "dateTime" in start:
            ev_date = datetime.fromisoformat(start["dateTime"]).date()
        elif "date" in start:
            ev_date = datetime.fromisoformat(start["date"]).date()
        else:
            continue
        if ev_date == date.date():
            day_events.append(ev)

    if not day_events:
        return f"{header}: 일정 없음"
    lines = [header + ":"]
    for ev in day_events:
        lines.append("  " + _format_event(ev))
    return "\n".join(lines)


def get_today_schedule() -> str:
    """오늘 일정을 텍스트로 반환한다."""
    now = datetime.now(KST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    events = _fetch_events(start, end)
    if not events:
        return "오늘 예정된 일정 없음"

    lines = [_format_event(ev) for ev in events]
    return "\n".join(lines)


def get_week_schedule() -> str:
    """이번 주 일정을 텍스트로 반환한다 (오늘 ~ 일요일)."""
    now = datetime.now(KST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days_until_sunday = 6 - now.weekday()
    if days_until_sunday <= 0:
        days_until_sunday = 7
    end = start + timedelta(days=days_until_sunday + 1)

    events = _fetch_events(start, end)
    if not events:
        return "이번 주 예정된 일정 없음"

    lines = []
    for d in range(days_until_sunday + 1):
        day = start + timedelta(days=d)
        lines.append(_format_day_events(day, events))
    return "\n".join(lines)


def get_month_schedule() -> str:
    """이번 달 남은 일정을 텍스트로 반환한다."""
    now = datetime.now(KST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if now.month == 12:
        end = start.replace(year=now.year + 1, month=1, day=1)
    else:
        end = start.replace(month=now.month + 1, day=1)

    events = _fetch_events(start, end)
    if not events:
        return "이번 달 남은 일정 없음"

    lines = []
    current = start
    while current < end:
        day_text = _format_day_events(current, events)
        if "일정 없음" not in day_text:
            lines.append(day_text)
        current += timedelta(days=1)

    if not lines:
        return "이번 달 남은 일정 없음"
    return "\n".join(lines)


def get_calendar_context(scope: str = "today") -> str:
    """봇 프롬프트에 삽입할 캘린더 컨텍스트를 반환한다.

    Args:
        scope: "today", "week", "month"

    Returns:
        캘린더 정보 텍스트. 실패 시 빈 문자열.
    """
    service = _get_service()
    if not service:
        return ""

    parts = []

    if scope in ("today", "week", "month"):
        today = get_today_schedule()
        parts.append(f"[오늘 일정]\n{today}")

    if scope in ("week", "month"):
        week = get_week_schedule()
        parts.append(f"[이번 주 일정]\n{week}")

    if scope == "month":
        month = get_month_schedule()
        parts.append(f"[이번 달 남은 일정]\n{month}")

    if not parts:
        return ""

    return "━━━ Google Calendar ━━━\n" + "\n\n".join(parts) + "\n━━━━━━━━━━━━━━━━━━━━━"
