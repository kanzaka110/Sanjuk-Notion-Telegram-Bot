"""
Automations — 자연어 자동화 규칙
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
사용자가 자연어로 정의한 규칙을 SQLite에 저장,
백그라운드 폴러가 평가하여 조건이 맞으면 액션 실행.

Trigger 타입:
  - daily_at: HH:MM 매일
  - weekly_at: "Mon HH:MM"
  - on_calendar_keyword: "다가오는 N분 이내 캘린더 이벤트 제목에 키워드 X 포함"

Action 타입:
  - send_message: 단순 텍스트 전송
  - prompt_claude: 주어진 프롬프트로 Claude 호출 후 결과 전송
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_BASE_DIR, "Chat_bot", "data", "automations.db")


def _ensure_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS automations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                trigger_config TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_config TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_run TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def add_automation(
    name: str,
    trigger_type: str,
    trigger_config: dict,
    action_type: str,
    action_config: dict,
) -> int:
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO automations (name, trigger_type, trigger_config, action_type, action_config, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                name,
                trigger_type,
                json.dumps(trigger_config, ensure_ascii=False),
                action_type,
                json.dumps(action_config, ensure_ascii=False),
                datetime.now(KST).isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_automations() -> list[dict]:
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "SELECT id, name, trigger_type, trigger_config, action_type, action_config, "
            "enabled, last_run, created_at FROM automations ORDER BY id"
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": r[0], "name": r[1],
            "trigger_type": r[2], "trigger_config": json.loads(r[3]),
            "action_type": r[4], "action_config": json.loads(r[5]),
            "enabled": bool(r[6]), "last_run": r[7], "created_at": r[8],
        }
        for r in rows
    ]


def delete_automation(automation_id: int) -> bool:
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute("DELETE FROM automations WHERE id = ?", (automation_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def toggle_automation(automation_id: int, enabled: bool) -> bool:
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "UPDATE automations SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, automation_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def _mark_run(automation_id: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE automations SET last_run = ? WHERE id = ?",
            (datetime.now(KST).isoformat(), automation_id),
        )
        conn.commit()
    finally:
        conn.close()


def _should_fire(rule: dict, now: datetime) -> bool:
    """이 규칙이 지금 실행돼야 하는지 판정."""
    if not rule["enabled"]:
        return False
    last_run = rule.get("last_run")
    if last_run:
        try:
            last = datetime.fromisoformat(last_run)
            # 같은 분 내 중복 실행 방지
            if (now - last).total_seconds() < 60:
                return False
        except Exception:
            pass

    ttype = rule["trigger_type"]
    cfg = rule["trigger_config"]

    if ttype == "daily_at":
        # cfg = {"time": "HH:MM"}
        target = cfg.get("time", "")
        try:
            hh, mm = target.split(":")
            if now.hour == int(hh) and now.minute == int(mm):
                if last_run:
                    last = datetime.fromisoformat(last_run)
                    if last.date() == now.date():
                        return False
                return True
        except Exception:
            return False
        return False

    if ttype == "weekly_at":
        # cfg = {"weekday": 0~6, "time": "HH:MM"}
        try:
            wd = int(cfg.get("weekday", 0))
            hh, mm = cfg.get("time", "0:0").split(":")
            if now.weekday() == wd and now.hour == int(hh) and now.minute == int(mm):
                if last_run:
                    last = datetime.fromisoformat(last_run)
                    if (now - last).total_seconds() < 3600:
                        return False
                return True
        except Exception:
            return False
        return False

    if ttype == "on_calendar_keyword":
        # cfg = {"keyword": "...", "minutes_before": 30}
        try:
            keyword = cfg.get("keyword", "")
            mins = int(cfg.get("minutes_before", 30))
            from google_calendar import CALENDAR_SOURCES, _get_service
            time_min = now + timedelta(minutes=mins - 5)
            time_max = now + timedelta(minutes=mins + 5)
            for account, cid in CALENDAR_SOURCES:
                svc = _get_service(account)
                if not svc:
                    continue
                try:
                    res = svc.events().list(
                        calendarId=cid,
                        timeMin=time_min.isoformat(),
                        timeMax=time_max.isoformat(),
                        singleEvents=True,
                    ).execute()
                    for ev in res.get("items", []):
                        title = ev.get("summary", "")
                        if keyword.lower() in title.lower():
                            return True
                except Exception:
                    continue
        except Exception:
            return False
        return False

    return False


async def run_due_automations(send_message_async, claude_chat_async) -> list[dict]:
    """현재 시각에 맞는 자동화 규칙을 실행. 실행된 규칙 목록 반환.

    send_message_async(text) -> coroutine
    claude_chat_async(prompt) -> str (coroutine)
    """
    now = datetime.now(KST)
    rules = list_automations()
    fired = []
    for rule in rules:
        if not _should_fire(rule, now):
            continue
        try:
            atype = rule["action_type"]
            acfg = rule["action_config"]
            if atype == "send_message":
                text = acfg.get("text", "")
                if text:
                    await send_message_async(text)
                    fired.append(rule)
            elif atype == "prompt_claude":
                prompt = acfg.get("prompt", "")
                if prompt:
                    text = await claude_chat_async(prompt)
                    if text:
                        await send_message_async(text)
                        fired.append(rule)
            _mark_run(rule["id"])
        except Exception as e:
            log.error("automation %s 실행 실패: %s", rule["name"], e)
    return fired


def format_rule_list(rules: list[dict]) -> str:
    if not rules:
        return "등록된 자동화 없음."
    lines = ["등록 자동화:"]
    for r in rules:
        flag = "✓" if r["enabled"] else "✗"
        tt = r["trigger_type"]
        tc = r["trigger_config"]
        if tt == "daily_at":
            when = f"매일 {tc.get('time')}"
        elif tt == "weekly_at":
            wd_kr = ["월", "화", "수", "목", "금", "토", "일"][int(tc.get("weekday", 0))]
            when = f"매주 {wd_kr} {tc.get('time')}"
        elif tt == "on_calendar_keyword":
            when = f"'{tc.get('keyword')}' 일정 {tc.get('minutes_before', 30)}분 전"
        else:
            when = tt
        lines.append(f"  [{flag}] #{r['id']} {r['name']} — {when}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if "--list" in sys.argv:
        print(format_rule_list(list_automations()))
    elif "--init" in sys.argv:
        _ensure_db()
        print(f"DB 초기화: {DB_PATH}")
