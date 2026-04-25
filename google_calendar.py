"""
Google Calendar 연동 모듈 — 운세·수다 봇 공유
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OAuth2 인증으로 Google Calendar API에 접근하여
오늘/이번 주/이번 달 일정을 가져온다.

설정 필요:
  1. GCP Console에서 Calendar API 활성화
  2. OAuth 클라이언트 ID (데스크톱 앱) 생성 → JSON 다운로드
  3. python google_calendar.py --auth 로 최초 인증 (토큰 생성)
  4. 환경변수 (선택): GOOGLE_CALENDAR_ID (캘린더 ID, 기본값: primary)
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 경로 설정
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_PATH = os.path.join(_BASE_DIR, "client_secret.json")
TOKEN_PATH = os.path.join(_BASE_DIR, "calendar_token.json")
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

_service = None


def _get_service():
    """Google Calendar API 서비스 객체를 반환한다 (싱글톤)."""
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
            log.info("Calendar OAuth 토큰 갱신 완료")

        if not creds or not creds.valid:
            log.warning("Calendar OAuth 토큰 없음 또는 만료. 'python google_calendar.py --auth' 실행 필요")
            return None

        _service = build("calendar", "v3", credentials=creds)
        log.info("Google Calendar API 연결 성공")
        return _service

    except ImportError:
        log.warning("필요 패키지 미설치. pip install google-api-python-client google-auth-oauthlib")
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


def run_auth():
    """최초 OAuth2 인증을 수행하여 토큰을 저장한다."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not os.path.exists(CLIENT_SECRET_PATH):
        print(f"OAuth 클라이언트 시크릿 파일이 필요합니다: {CLIENT_SECRET_PATH}")
        return

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
    creds = flow.run_local_server(port=0, open_browser=False)

    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())
    print(f"토큰 저장 완료: {TOKEN_PATH}")

    # 연결 테스트
    from googleapiclient.discovery import build
    service = build("calendar", "v3", credentials=creds)
    events = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=datetime.now(KST).isoformat(),
        maxResults=5,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    items = events.get("items", [])
    print(f"연결 성공! 다가오는 일정 {len(items)}건")
    for ev in items:
        start = ev["start"].get("dateTime", ev["start"].get("date"))
        print(f"  - {start}: {ev.get('summary', '(제목 없음)')}")


if __name__ == "__main__":
    import sys
    if "--auth" in sys.argv:
        run_auth()
    elif "--test" in sys.argv:
        logging.basicConfig(level=logging.INFO)
        print(get_calendar_context("today"))
    else:
        print("사용법:")
        print("  python google_calendar.py --auth   # 최초 인증")
        print("  python google_calendar.py --test   # 오늘 일정 테스트")
