"""
작업 시간 로깅 — 시작/종료 기록 + 일별 리포트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_LOG_PATH = os.path.join(_BASE_DIR, "data", "work_log.json")

_active_task: dict | None = None


def _load() -> list[dict]:
    if not os.path.exists(WORK_LOG_PATH):
        return []
    with open(WORK_LOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(logs: list[dict]):
    os.makedirs(os.path.dirname(WORK_LOG_PATH), exist_ok=True)
    with open(WORK_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def start_work(task_name: str) -> str:
    """작업 시작."""
    global _active_task
    if _active_task:
        # 이전 작업 자동 종료
        stop_work()
    _active_task = {
        "task": task_name,
        "start": datetime.now(KST).isoformat(),
    }
    return f"작업 시작: {task_name} ({datetime.now(KST).strftime('%H:%M')})"


def stop_work() -> str:
    """작업 종료."""
    global _active_task
    if not _active_task:
        return "진행 중인 작업 없음"

    now = datetime.now(KST)
    start_dt = datetime.fromisoformat(_active_task["start"])
    duration = (now - start_dt).total_seconds() / 60

    entry = {
        "task": _active_task["task"],
        "start": _active_task["start"],
        "end": now.isoformat(),
        "duration_min": round(duration),
        "date": now.strftime("%Y-%m-%d"),
    }
    logs = _load()
    logs.append(entry)
    _save(logs)

    task_name = _active_task["task"]
    _active_task = None

    hours = int(duration // 60)
    mins = int(duration % 60)
    time_str = f"{hours}시간 {mins}분" if hours > 0 else f"{mins}분"
    return f"작업 종료: {task_name} ({time_str})"


def get_today_report() -> str:
    """오늘 작업 시간 리포트."""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    logs = [l for l in _load() if l["date"] == today]

    if not logs:
        return "오늘 기록된 작업 없음"

    lines = ["[오늘 작업 로그]"]
    total = 0
    for l in logs:
        hours = l["duration_min"] // 60
        mins = l["duration_min"] % 60
        time_str = f"{hours}h{mins}m" if hours > 0 else f"{mins}m"
        lines.append(f"- {l['task']}: {time_str}")
        total += l["duration_min"]

    total_h = total // 60
    total_m = total % 60
    lines.append(f"\n총 {total_h}시간 {total_m}분")

    if _active_task:
        lines.append(f"(진행 중: {_active_task['task']})")

    return "\n".join(lines)


def get_week_report() -> str:
    """이번 주 작업 시간 리포트."""
    now = datetime.now(KST)
    week_start = now - timedelta(days=now.weekday())
    week_start_str = week_start.strftime("%Y-%m-%d")

    logs = [l for l in _load() if l["date"] >= week_start_str]
    if not logs:
        return "이번 주 기록된 작업 없음"

    # 태스크별 집계
    task_totals: dict[str, int] = {}
    for l in logs:
        task_totals[l["task"]] = task_totals.get(l["task"], 0) + l["duration_min"]

    lines = ["[이번 주 작업 요약]"]
    for task, mins in sorted(task_totals.items(), key=lambda x: -x[1]):
        hours = mins // 60
        m = mins % 60
        lines.append(f"- {task}: {hours}h{m}m")

    total = sum(task_totals.values())
    lines.append(f"\n총 {total // 60}시간 {total % 60}분")
    return "\n".join(lines)
