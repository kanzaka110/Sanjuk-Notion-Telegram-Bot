"""수다봇 Hevy 관련 JobQueue 콜백.

chat_bot.py의 ``app.job_queue.run_daily()``로 등록되어
정해진 시간에 텔레그램 메시지를 발송한다 (모두 KST).

스케줄:
  04:00       hevy_sync                 — Hevy API → 캐시/PR DB 갱신
  08:00       morning_workout           — 어제 운동 요약 (운동 있을 때만)
  21:00       workout_nudge             — 오늘 X & 이번주 < 3회면 독려
  Mon 08:05   weekly_workout_report     — 지난주 PR/추세 리포트
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from telegram.ext import ContextTypes

from .analytics import (
    WEEKLY_THRESHOLD,
    count_workouts_in_week,
    days_since_last_workout,
    extract_pr_candidates,
    filter_in_week,
    format_weekly_report,
    format_workout_summary,
    parse_iso,
    week_start,
)
from .sync import load_cache, run_sync

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def _chat_id() -> int:
    """ALLOWED_CHAT_ID를 lazy import (테스트 용이)."""
    from config import ALLOWED_CHAT_ID
    return ALLOWED_CHAT_ID


def _to_kst(value: str | None) -> datetime | None:
    dt = parse_iso(value)
    return dt.astimezone(KST) if dt else None


# ─── 04:00 sync ────────────────────────────────────────
async def scheduled_hevy_sync(context: ContextTypes.DEFAULT_TYPE) -> None:
    """매일 04:00 KST — Hevy API에서 데이터 가져와 캐시/PR DB 갱신."""
    log.info("hevy.sync 시작")
    try:
        summary = await run_sync()
        log.info("hevy.sync 완료: %s", summary)
    except Exception as e:
        log.error("hevy.sync 실패: %s", e)


# ─── 08:00 어제 운동 요약 ──────────────────────────────
async def scheduled_morning_workout(context: ContextTypes.DEFAULT_TYPE) -> None:
    """매일 08:00 KST — 어제(KST 자정~자정) 운동이 있으면 요약 푸시."""
    chat_id = _chat_id()
    if chat_id == 0:
        return
    try:
        workouts = load_cache().get("workouts", [])
        now_kst = datetime.now(KST)
        today_start = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
        yest_start = today_start - timedelta(days=1)

        yest_workouts = [
            w for w in workouts
            if (kst := _to_kst(w.get("start_time"))) is not None
            and yest_start <= kst < today_start
        ]
        if not yest_workouts:
            log.info("morning_workout: 어제 운동 없음, 스킵")
            return

        for w in yest_workouts:
            await context.bot.send_message(
                chat_id=chat_id,
                text=format_workout_summary(w),
            )
        log.info("morning_workout: %d건 발송", len(yest_workouts))
    except Exception as e:
        log.error("morning_workout 실패: %s", e)


# ─── 21:00 운동 안 한 날 독려 ──────────────────────────
async def scheduled_workout_nudge(context: ContextTypes.DEFAULT_TYPE) -> None:
    """매일 21:00 KST — 오늘 운동 X & 이번주 < 3회면 독려 푸시.

    이번주 3회 이상 달성했으면 휴식일로 인정하고 스킵.
    """
    chat_id = _chat_id()
    if chat_id == 0:
        return
    try:
        workouts = load_cache().get("workouts", [])
        now_kst = datetime.now(KST)
        today_start = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)

        worked_today = any(
            (kst := _to_kst(w.get("start_time"))) is not None and kst >= today_start
            for w in workouts
        )
        if worked_today:
            log.info("nudge: 오늘 운동함, 스킵")
            return

        week_count = count_workouts_in_week(workouts, now_kst, KST)
        if week_count >= WEEKLY_THRESHOLD:
            log.info("nudge: 이번주 %d회, 휴식일 인정", week_count)
            return

        days = days_since_last_workout(workouts, now_kst)
        lines = ["💪 오늘은 아직 운동 안 했네"]
        if days < 999:
            lines.append(f"마지막 운동: {days}일 전")
        lines.append(f"이번주 {week_count}/{WEEKLY_THRESHOLD}회 — 한 번만 더 가자")
        await context.bot.send_message(chat_id=chat_id, text="\n".join(lines))
        log.info("nudge: 발송 (이번주 %d회)", week_count)
    except Exception as e:
        log.error("nudge 실패: %s", e)


# ─── 월요일 08:05 주간 리포트 ──────────────────────────
async def scheduled_weekly_workout_report(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """매주 월요일 08:05 KST — 지난주(월~일) 운동/PR 리포트 발송."""
    chat_id = _chat_id()
    if chat_id == 0:
        return
    try:
        workouts = load_cache().get("workouts", [])
        now_kst = datetime.now(KST)
        last_week_mon = week_start(now_kst, KST) - timedelta(days=7)
        last_week_workouts = filter_in_week(workouts, last_week_mon)

        prev_workouts = [
            w for w in workouts
            if (kst := _to_kst(w.get("start_time"))) is not None
            and kst < last_week_mon
        ]
        prev_prs = extract_pr_candidates(prev_workouts)
        last_week_prs = extract_pr_candidates(last_week_workouts)

        updates = []
        for ex, new in last_week_prs.items():
            old = prev_prs.get(ex)
            if old is None:
                updates.append({
                    "exercise": ex,
                    "old_weight": 0.0, "old_reps": 0,
                    "new_weight": new["weight_kg"], "new_reps": new["reps"],
                })
            elif new["weight_kg"] > old["weight_kg"] or (
                new["weight_kg"] == old["weight_kg"]
                and new["reps"] > old["reps"]
            ):
                updates.append({
                    "exercise": ex,
                    "old_weight": old["weight_kg"], "old_reps": old["reps"],
                    "new_weight": new["weight_kg"], "new_reps": new["reps"],
                })

        text = format_weekly_report(last_week_workouts, updates)
        await context.bot.send_message(chat_id=chat_id, text=text)
        log.info(
            "weekly_report: 운동 %d회, PR 갱신 %d개 발송",
            len(last_week_workouts), len(updates),
        )
    except Exception as e:
        log.error("weekly_report 실패: %s", e)
