"""
딥워크 집중 모드 — 알림 큐잉 + 작업 로그
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

_focus_until: datetime | None = None
_queued_messages: list[str] = []


def start_focus(minutes: int = 90) -> str:
    """집중 모드 시작."""
    global _focus_until
    _focus_until = datetime.now(KST) + timedelta(minutes=minutes)
    _queued_messages.clear()
    return f"집중 모드 시작 ({minutes}분). {_focus_until.strftime('%H:%M')}에 끝나."


def stop_focus() -> str:
    """집중 모드 종료."""
    global _focus_until
    _focus_until = None
    queued = len(_queued_messages)
    summary = ""
    if _queued_messages:
        summary = "\n\n쌓인 알림:\n" + "\n".join(f"- {m}" for m in _queued_messages)
        _queued_messages.clear()
    return f"집중 모드 종료. 대기 알림 {queued}건." + summary


def is_focus_active() -> bool:
    """집중 모드 활성 여부."""
    global _focus_until
    if _focus_until is None:
        return False
    if datetime.now(KST) >= _focus_until:
        _focus_until = None
        return False
    return True


def queue_message(msg: str):
    """집중 모드 중 메시지를 큐에 추가."""
    _queued_messages.append(msg)


def get_focus_status() -> str:
    if not is_focus_active():
        return ""
    remaining = (_focus_until - datetime.now(KST)).total_seconds() / 60
    return f"집중 모드 {int(remaining)}분 남음"


def get_queued_count() -> int:
    return len(_queued_messages)
