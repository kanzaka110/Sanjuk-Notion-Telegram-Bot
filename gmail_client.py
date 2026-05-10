"""
Gmail 연동 모듈 — 미확인 메일 요약, 중요 메일 알림
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OAuth2 토큰 재사용 (Calendar와 동일 인증 흐름).
Gmail readonly 스코프 필요 — 재인증 시 추가.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(_BASE_DIR, "gmail_token.json")
CLIENT_SECRET_PATH = os.path.join(_BASE_DIR, "client_secret.json")
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

_service = None


def _get_service():
    """Gmail API 서비스 객체를 반환한다."""
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
            log.warning("Gmail OAuth 토큰 없음. gmail_client.py --auth 실행 필요")
            return None

        _service = build("gmail", "v1", credentials=creds)
        log.info("Gmail API 연결 성공")
        return _service

    except Exception as e:
        log.error("Gmail API 초기화 실패: %s", e)
        return None


def get_unread_count() -> int:
    """미확인 메일 수를 반환한다."""
    service = _get_service()
    if not service:
        return -1
    try:
        results = service.users().messages().list(
            userId="me", q="is:unread", maxResults=1,
        ).execute()
        return results.get("resultSizeEstimate", 0)
    except Exception as e:
        log.error("미확인 메일 조회 실패: %s", e)
        return -1


def get_recent_unread(max_results: int = 5) -> list[dict]:
    """최근 미확인 메일 목록을 반환한다."""
    service = _get_service()
    if not service:
        return []

    try:
        results = service.users().messages().list(
            userId="me", q="is:unread", maxResults=max_results,
        ).execute()
        messages = results.get("messages", [])

        summaries = []
        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()

            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            summaries.append({
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", "(제목 없음)"),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", "")[:100],
            })

        return summaries

    except Exception as e:
        log.error("미확인 메일 목록 조회 실패: %s", e)
        return []


def get_gmail_context() -> str:
    """봇 프롬프트에 삽입할 Gmail 컨텍스트."""
    service = _get_service()
    if not service:
        return ""

    unread = get_unread_count()
    if unread <= 0:
        return ""

    mails = get_recent_unread(3)
    lines = [f"미확인 메일 {unread}건:"]
    for m in mails:
        sender = m["from"].split("<")[0].strip()
        lines.append(f"- {sender}: {m['subject']}")

    return (
        "━━━ Gmail ━━━\n"
        + "\n".join(lines)
        + "\n━━━━━━━━━━━━━"
    )


if __name__ == "__main__":
    import sys
    if "--auth" in sys.argv:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_PATH,
            scopes=SCOPES,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
        )
        auth_url, _ = flow.authorization_url(prompt="consent")
        print(f"\nURL: {auth_url}\n")
        code = input("코드: ").strip()
        flow.fetch_token(code=code)
        with open(TOKEN_PATH, "w") as f:
            f.write(flow.credentials.to_json())
        print(f"토큰 저장: {TOKEN_PATH}")
    elif "--test" in sys.argv:
        logging.basicConfig(level=logging.INFO)
        print(get_gmail_context())
