"""Hevy 워크아웃 데이터 분석.

워크아웃 dict는 Hevy API 응답 형식:
- start_time, end_time (ISO8601 문자열, Z suffix)
- exercises: [{ title, sets: [{ weight_kg, reps, type }] }]

이 모듈은 외부 의존성 없이 dict만 다룬다 (테스트 용이).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

# 이번주 운동 충분 임계값 (이상이면 휴식일 푸시 스킵)
WEEKLY_THRESHOLD = 3


def parse_iso(value: str | None) -> datetime | None:
    """Hevy ISO8601 문자열 → timezone-aware datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def workout_volume(workout: dict) -> float:
    """한 워크아웃의 총 볼륨 (kg × reps 합, 워밍업 제외)."""
    total = 0.0
    for ex in workout.get("exercises") or []:
        for s in ex.get("sets") or []:
            if s.get("type") == "warmup":
                continue
            w = s.get("weight_kg") or 0
            r = s.get("reps") or 0
            total += float(w) * int(r)
    return total


def workout_set_count(workout: dict) -> int:
    """워밍업 제외한 작업 세트 수."""
    n = 0
    for ex in workout.get("exercises") or []:
        for s in ex.get("sets") or []:
            if s.get("type") != "warmup":
                n += 1
    return n


def workout_duration_minutes(workout: dict) -> int | None:
    """end_time - start_time (분). 시간 정보 없으면 None."""
    start = parse_iso(workout.get("start_time"))
    end = parse_iso(workout.get("end_time"))
    if not start or not end:
        return None
    return max(0, int((end - start).total_seconds() / 60))


def week_start(now: datetime, tz: timezone = timezone.utc) -> datetime:
    """now가 속한 주의 월요일 00:00 (해당 tz 기준)."""
    local = now.astimezone(tz)
    monday = local - timedelta(days=local.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def filter_in_week(
    workouts: Iterable[dict],
    week_start_dt: datetime,
) -> list[dict]:
    """week_start_dt 이후 7일 내 워크아웃."""
    week_end = week_start_dt + timedelta(days=7)
    out = []
    for w in workouts:
        st = parse_iso(w.get("start_time"))
        if st is None:
            continue
        if week_start_dt <= st < week_end:
            out.append(w)
    return out


def count_workouts_in_week(
    workouts: Iterable[dict],
    now: datetime,
    tz: timezone = timezone.utc,
) -> int:
    """now가 속한 주(월~일)의 운동 횟수."""
    return len(filter_in_week(workouts, week_start(now, tz)))


def days_since_last_workout(
    workouts: Iterable[dict],
    now: datetime,
) -> int:
    """마지막 운동 이후 경과 일수. 기록 없으면 999."""
    starts = [parse_iso(w.get("start_time")) for w in workouts]
    starts = [s for s in starts if s is not None]
    if not starts:
        return 999
    latest = max(starts).astimezone(now.tzinfo or timezone.utc)
    return max(0, (now.date() - latest.date()).days)


def extract_pr_candidates(workouts: Iterable[dict]) -> dict[str, dict]:
    """운동별 PR 후보. 최대 weight_kg, 동률이면 최대 reps.

    반환: { exercise_title: { weight_kg, reps, workout_id, when } }
    """
    best: dict[str, dict] = {}
    for w in workouts:
        wid = w.get("id")
        when = w.get("start_time")
        for ex in w.get("exercises") or []:
            title = (ex.get("title") or "").strip()
            if not title:
                continue
            for s in ex.get("sets") or []:
                if s.get("type") == "warmup":
                    continue
                weight = float(s.get("weight_kg") or 0)
                reps = int(s.get("reps") or 0)
                if weight <= 0 or reps <= 0:
                    continue
                cur = best.get(title)
                if cur is None or weight > cur["weight_kg"] or (
                    weight == cur["weight_kg"] and reps > cur["reps"]
                ):
                    best[title] = {
                        "weight_kg": weight,
                        "reps": reps,
                        "workout_id": wid,
                        "when": when,
                    }
    return best


def diff_prs(prev: dict[str, dict], curr: dict[str, dict]) -> list[dict]:
    """이전 PR 대비 갱신된 종목 리스트.

    반환: [{ exercise, old_weight, old_reps, new_weight, new_reps }]
    """
    updates = []
    for title, new in curr.items():
        old = prev.get(title)
        if old is None:
            updates.append({
                "exercise": title,
                "old_weight": 0.0,
                "old_reps": 0,
                "new_weight": new["weight_kg"],
                "new_reps": new["reps"],
            })
            continue
        if (
            new["weight_kg"] > old["weight_kg"]
            or (new["weight_kg"] == old["weight_kg"] and new["reps"] > old["reps"])
        ):
            updates.append({
                "exercise": title,
                "old_weight": old["weight_kg"],
                "old_reps": old["reps"],
                "new_weight": new["weight_kg"],
                "new_reps": new["reps"],
            })
    return updates


# ─── 텔레그램 메시지 포맷터 ──────────────────────────────
def format_workout_summary(workout: dict) -> str:
    """워크아웃 한 건의 텔레그램 메시지 요약."""
    title = workout.get("title") or "이름 없음"
    duration = workout_duration_minutes(workout)
    head = f"🏋️ {title}"
    if duration is not None:
        head += f" ({duration}분)"

    lines = [head]
    for ex in workout.get("exercises") or []:
        ex_title = ex.get("title") or ""
        sets = [s for s in (ex.get("sets") or []) if s.get("type") != "warmup"]
        if not sets:
            continue
        max_w = max((float(s.get("weight_kg") or 0) for s in sets), default=0.0)
        reps_seq = ",".join(str(int(s.get("reps") or 0)) for s in sets)
        lines.append(f"├ {ex_title} {max_w:g}kg × {reps_seq}")

    volume = workout_volume(workout)
    if volume > 0:
        lines.append(f"└ 총 볼륨 {volume:,.0f}kg")
    return "\n".join(lines)


def format_weekly_report(
    workouts_this_week: list[dict],
    pr_updates: list[dict],
) -> str:
    """월요일 아침 주간 리포트 메시지."""
    n = len(workouts_this_week)
    total_volume = sum(workout_volume(w) for w in workouts_this_week)
    total_sets = sum(workout_set_count(w) for w in workouts_this_week)

    lines = [
        f"📊 지난주 운동 리포트",
        f"├ 운동 {n}회 / 총 {total_sets}세트",
        f"└ 총 볼륨 {total_volume:,.0f}kg",
    ]
    if pr_updates:
        lines.append("")
        lines.append("🔥 신기록")
        for u in pr_updates[:8]:
            if u["old_weight"] == 0:
                lines.append(
                    f"├ {u['exercise']} {u['new_weight']:g}kg × {u['new_reps']} (신규)"
                )
            else:
                lines.append(
                    f"├ {u['exercise']} "
                    f"{u['old_weight']:g}kg×{u['old_reps']} → "
                    f"{u['new_weight']:g}kg×{u['new_reps']}"
                )
    return "\n".join(lines)
