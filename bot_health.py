"""
봇 헬스 인터랙티브 알림 — 다운 감지 시 텔레그램 즉시 알림
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
import subprocess

log = logging.getLogger(__name__)

SERVICES = ["luck-bot", "chatbot", "stock-bot", "ue-bot", "game-news-bot"]
_last_status: dict[str, str] = {}


def _check_service(name: str) -> str:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def check_all_services() -> list[dict]:
    """모든 봇 서비스 상태를 체크하고 변경된 것만 반환."""
    global _last_status
    changed = []
    for svc in SERVICES:
        status = _check_service(svc)
        prev = _last_status.get(svc, "active")
        if status != "active" and prev == "active":
            changed.append({"service": svc, "status": status, "action": "down"})
        elif status == "active" and prev != "active":
            changed.append({"service": svc, "status": status, "action": "recovered"})
        _last_status[svc] = status
    return changed


def restart_service(name: str) -> bool:
    """서비스를 재시작한다."""
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "restart", name],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


async def health_check_and_notify(bot, chat_id: int):
    """헬스 체크 후 알림 발송."""
    changes = await asyncio.to_thread(check_all_services)
    for c in changes:
        if c["action"] == "down":
            # 자동 재시작 시도
            restarted = await asyncio.to_thread(restart_service, c["service"])
            if restarted:
                msg = f"[봇 알림] {c['service']} 다운 감지 → 자동 재시작 완료"
            else:
                msg = f"[봇 알림] {c['service']} 다운! 자동 재시작 실패. 수동 확인 필요"
            await bot.send_message(chat_id=chat_id, text=msg)
            log.warning(msg)
        elif c["action"] == "recovered":
            msg = f"[봇 알림] {c['service']} 정상 복구됨"
            await bot.send_message(chat_id=chat_id, text=msg)
            log.info(msg)
