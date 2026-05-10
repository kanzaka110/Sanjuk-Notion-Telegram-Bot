"""
Google Calendar 연동 모듈 — 운세·수다 봇 공유 (멀티 계정 지원)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
여러 Google 계정의 여러 캘린더를 한꺼번에 조회한다.

설정:
  1. GCP Console에서 Calendar API 활성화 + OAuth Desktop 클라이언트
  2. client_secret.json 배치
  3. 계정별 인증:
       python google_calendar.py --auth          # 기본(gmail) 토큰
       python google_calendar.py --auth shiftup  # 추가 계정 토큰
  4. 환경변수
     GOOGLE_CALENDAR_SOURCES=gmail:primary,gmail:cal_id_2,shiftup:primary
       (account:calendar_id 콤마 구분, account 생략 시 'gmail')
     CALENDAR_EXCLUDE_PATTERNS=[AB],패턴2  (summary에 포함되면 제외)
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
DEFAULT_ACCOUNT = "gmail"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _token_path(account: str) -> str:
    """계정별 토큰 파일 경로. gmail은 기존 파일명 유지(하위 호환)."""
    if account == DEFAULT_ACCOUNT:
        return os.path.join(_BASE_DIR, "calendar_token.json")
    return os.path.join(_BASE_DIR, f"calendar_token_{account}.json")


def _parse_sources(raw: str) -> list[tuple[str, str]]:
    """'account:cal_id,cal_id2,acc2:cal_id3' 형태 파싱. account 생략 시 DEFAULT_ACCOUNT."""
    out: list[tuple[str, str]] = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            acc, cid = entry.split(":", 1)
            out.append((acc.strip() or DEFAULT_ACCOUNT, cid.strip()))
        else:
            out.append((DEFAULT_ACCOUNT, entry))
    return out


# 새 환경변수 우선, 없으면 옛 GOOGLE_CALENDAR_IDS 사용 (모두 default account로 매핑)
_raw_sources = os.environ.get("GOOGLE_CALENDAR_SOURCES")
if _raw_sources:
    CALENDAR_SOURCES: list[tuple[str, str]] = _parse_sources(_raw_sources)
else:
    _raw_ids = os.environ.get("GOOGLE_CALENDAR_IDS") or os.environ.get(
        "GOOGLE_CALENDAR_ID", "primary"
    )
    CALENDAR_SOURCES = _parse_sources(_raw_ids)

# 하위 호환: 단일 계정 코드가 import할 수 있도록 ID-only 리스트도 제공
CALENDAR_IDS = [cid for _, cid in CALENDAR_SOURCES]
CALENDAR_ID = CALENDAR_IDS[0] if CALENDAR_IDS else "primary"

# summary에 포함되면 결과에서 제외할 패턴 (콤마 구분, 대소문자 무시)
_raw_excludes = os.environ.get("CALENDAR_EXCLUDE_PATTERNS", "")
EXCLUDE_PATTERNS = [p.strip().lower() for p in _raw_excludes.split(",") if p.strip()]


def _is_excluded(event: dict) -> bool:
    """summary에 EXCLUDE_PATTERNS 중 하나라도 포함되면 True."""
    if not EXCLUDE_PATTERNS:
        return False
    summary = (event.get("summary") or "").lower()
    return any(p in summary for p in EXCLUDE_PATTERNS)


# 계정별 서비스 객체 캐시
_services: dict[str, Any] = {}


def _get_service(account: str = DEFAULT_ACCOUNT):
    """계정별 Google Calendar API 서비스 객체를 반환한다."""
    if account in _services:
        return _services[account]

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        token_path = _token_path(account)
        creds = None

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w") as f:
                f.write(creds.to_json())
            log.info("Calendar OAuth 토큰 갱신 완료 (%s)", account)

        if not creds or not creds.valid:
            log.warning(
                "Calendar OAuth 토큰 없음/만료 (%s). "
                "'python google_calendar.py --auth %s' 실행 필요",
                account,
                account if account != DEFAULT_ACCOUNT else "",
            )
            return None

        service = build("calendar", "v3", credentials=creds)
        _services[account] = service
        log.info("Google Calendar API 연결 성공 (%s)", account)
        return service

    except ImportError:
        log.warning("필요 패키지 미설치. pip install google-api-python-client google-auth-oauthlib")
        return None
    except Exception as e:
        log.error("Google Calendar API 초기화 실패 (%s): %s", account, e)
        return None


def _event_start_key(ev: dict) -> str:
    """이벤트 정렬용 시작 시간 키. dateTime 우선, 없으면 date."""
    s = ev.get("start", {})
    return s.get("dateTime") or s.get("date") or ""


def _fetch_events(time_min: datetime, time_max: datetime) -> list[dict[str, Any]]:
    """지정 기간의 이벤트를 모든 CALENDAR_SOURCES에서 가져와 시간순으로 합친다."""
    merged: list[dict[str, Any]] = []
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
                maxResults=50,
            ).execute()
        except Exception as e:
            log.error("Calendar 이벤트 조회 실패 (%s/%s): %s", account, cid, e)
            continue

        for ev in result.get("items", []):
            if _is_excluded(ev):
                continue
            ev_id = ev.get("id", "")
            # 동일 ID(여러 계정에 공유된 동일 이벤트) 중복 제거
            dedup_key = f"{ev_id}|{_event_start_key(ev)}"
            if dedup_key in seen_ids:
                continue
            seen_ids.add(dedup_key)
            ev["_calendar_id"] = cid
            ev["_account"] = account
            merged.append(ev)

    merged.sort(key=_event_start_key)
    return merged


def _format_event(event: dict) -> str:
    """이벤트 하나를 읽기 좋은 문자열로 변환한다."""
    raw_summary = event.get("summary")
    if not raw_summary:
        # 제목이 비어있으면 어느 캘린더에서 왔는지로 추정 (free/busy만 공유된 케이스)
        cid = event.get("_calendar_id", "")
        if "shiftup" in cid.lower():
            summary = "(시프트업 일정 — 비공개)"
        else:
            summary = "(제목 없음 — 비공개)"
    else:
        summary = raw_summary
    location = event.get("location", "")

    start = event.get("start", {})
    end = event.get("end", {})

    if "dateTime" in start:
        start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(KST)
        end_dt = datetime.fromisoformat(end["dateTime"]).astimezone(KST)
        time_str = f"{start_dt.strftime('%H:%M')}~{end_dt.strftime('%H:%M')}"
    elif "date" in start:
        time_str = "종일"
    else:
        time_str = ""

    parts = [f"- {time_str} {summary}"]
    if location:
        parts[0] += f" ({location})"
    return parts[0]


def _event_window(ev: dict) -> tuple[datetime, datetime] | None:
    """이벤트 시작/종료를 KST tz-aware datetime으로 반환. dateTime만 대상 (종일 제외)."""
    start = ev.get("start", {})
    end = ev.get("end", {})
    if "dateTime" not in start or "dateTime" not in end:
        return None
    s = datetime.fromisoformat(start["dateTime"]).astimezone(KST)
    e = datetime.fromisoformat(end["dateTime"]).astimezone(KST)
    return s, e


def find_conflicts(events: list[dict]) -> list[tuple[dict, dict]]:
    """겹치는 이벤트 쌍 리스트. 종일 이벤트는 제외."""
    timed = []
    for ev in events:
        win = _event_window(ev)
        if win:
            timed.append((win, ev))
    timed.sort(key=lambda x: x[0][0])

    pairs: list[tuple[dict, dict]] = []
    for i, ((a_s, a_e), a) in enumerate(timed):
        for j in range(i + 1, len(timed)):
            (b_s, b_e), b = timed[j]
            if b_s >= a_e:
                break
            if a_s < b_e and b_s < a_e:
                pairs.append((a, b))
    return pairs


def _format_day_events(date: datetime, events: list[dict]) -> str:
    """특정 날짜의 이벤트를 포맷한다. 시간 겹침 자동 감지."""
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"]
    day_name = weekday_kr[date.weekday()]
    header = f"{date.month}/{date.day}({day_name})"

    day_events = []
    for ev in events:
        start = ev.get("start", {})
        if "dateTime" in start:
            ev_date = datetime.fromisoformat(start["dateTime"]).astimezone(KST).date()
        elif "date" in start:
            ev_date = datetime.fromisoformat(start["date"]).date()
        else:
            continue
        if ev_date == date.date():
            day_events.append(ev)

    if not day_events:
        return f"{header}: 일정 없음"

    # 충돌 감지 — 같은 날 timed 이벤트들 사이
    conflicts = find_conflicts(day_events)
    conflict_ids = set()
    for a, b in conflicts:
        conflict_ids.add(a.get("id", ""))
        conflict_ids.add(b.get("id", ""))

    lines = [header + ":"]
    for ev in day_events:
        formatted = _format_event(ev)
        if ev.get("id", "") in conflict_ids:
            # _format_event는 "- 09:00..."로 시작 → 충돌일 때 "⚠"로 교체
            body = formatted[2:] if formatted.startswith("- ") else formatted
            lines.append(f"  ⚠ {body}")
        else:
            lines.append("  " + formatted)
    if conflicts:
        lines.append(f"  ⚠ 시간 겹침 {len(conflicts)}건 — 우선순위 확인 필요")
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


def get_week_schedule(days: int = 14) -> str:
    """오늘부터 days(기본 14일, 이번 주 + 다음 주) 동안의 일정을 텍스트로 반환한다."""
    now = datetime.now(KST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days)

    events = _fetch_events(start, end)
    if not events:
        return f"앞으로 {days}일간 예정된 일정 없음"

    lines = []
    for d in range(days):
        day = start + timedelta(days=d)
        day_text = _format_day_events(day, events)
        if "일정 없음" not in day_text:
            lines.append(day_text)

    if not lines:
        return f"앞으로 {days}일간 예정된 일정 없음"
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
    # 적어도 하나의 서비스가 살아있어야 의미 있음
    any_service = any(_get_service(acc) is not None for acc, _ in CALENDAR_SOURCES)
    if not any_service:
        return ""

    parts = []

    if scope in ("today", "week", "month"):
        today = get_today_schedule()
        parts.append(f"[오늘 일정]\n{today}")

    if scope in ("week", "month"):
        week = get_week_schedule()
        parts.append(f"[앞으로 2주 일정]\n{week}")

    if scope == "month":
        month = get_month_schedule()
        parts.append(f"[이번 달 남은 일정]\n{month}")

    if not parts:
        return ""

    return "━━━ Google Calendar ━━━\n" + "\n\n".join(parts) + "\n━━━━━━━━━━━━━━━━━━━━━"


def run_auth(account: str = DEFAULT_ACCOUNT):
    """최초 OAuth2 인증을 수행하여 토큰을 저장한다 (헤드리스 서버 지원)."""
    from google_auth_oauthlib.flow import Flow

    if not os.path.exists(CLIENT_SECRET_PATH):
        print(f"OAuth 클라이언트 시크릿 파일이 필요합니다: {CLIENT_SECRET_PATH}")
        return

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_PATH,
        scopes=SCOPES,
        redirect_uri="urn:ietf:wg:oauth:2.0:oob",
    )
    auth_url, _ = flow.authorization_url(prompt="consent")

    print(f"\n[{account} 계정 인증]")
    print("아래 URL을 브라우저에서 열고 해당 Google 계정으로 로그인하세요:")
    print(f"\n  {auth_url}\n")
    code = input("인증 후 표시되는 코드를 붙여넣으세요: ").strip()

    flow.fetch_token(code=code)
    creds = flow.credentials

    token_path = _token_path(account)
    with open(token_path, "w") as f:
        f.write(creds.to_json())
    print(f"토큰 저장 완료: {token_path}")

    # 연결 테스트
    from googleapiclient.discovery import build
    service = build("calendar", "v3", credentials=creds)
    cals = service.calendarList().list().execute()
    items = cals.get("items", [])
    print(f"\n연결 성공! 접근 가능한 캘린더 {len(items)}건:")
    for c in items:
        print(f"  - {c.get('summary')!r}: {c['id']}")


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if args and args[0] == "--auth":
        account = args[1] if len(args) > 1 else DEFAULT_ACCOUNT
        run_auth(account)
    elif args and args[0] == "--test":
        logging.basicConfig(level=logging.INFO)
        print("CALENDAR_SOURCES:", CALENDAR_SOURCES)
        print()
        print(get_calendar_context("week"))
    else:
        print("사용법:")
        print("  python google_calendar.py --auth            # 기본(gmail) 인증")
        print("  python google_calendar.py --auth shiftup    # shiftup 계정 인증")
        print("  python google_calendar.py --test            # 일정 출력 테스트")
