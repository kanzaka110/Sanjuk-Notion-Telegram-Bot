"""
Proactive Insights — 능동 통찰
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
사용자가 묻기 전에 봇이 먼저 말할 만한 통찰을 분석한다.
- 캘린더 패턴(반복 이벤트, 빈번한 방문지)
- 컨디션/수면 패턴
- 워크로드 위험 (밀집 일정, 짧은 회의 간격)
- KG 기반 사람·프로젝트 패턴
"""

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))


def analyze_calendar_pattern() -> list[str]:
    """캘린더 패턴 분석. 반복 방문지·빈번 키워드 등."""
    insights: list[str] = []
    try:
        from google_calendar import _fetch_events

        # 지난 30일 + 앞으로 14일 통계
        now = datetime.now(KST)
        past_start = now - timedelta(days=30)
        future_end = now + timedelta(days=14)
        events = _fetch_events(past_start, future_end)

        # 키워드 빈도 (제목에서 자주 나오는 명사구 단순 추정)
        titles = [e.get("summary", "") for e in events if e.get("summary")]
        keywords = Counter()
        for t in titles:
            for kw in ["피부과", "정신의학과", "회의", "병원", "치과", "약속"]:
                if kw in t:
                    keywords[kw] += 1

        for kw, cnt in keywords.most_common(3):
            if cnt >= 3:
                insights.append(
                    f"최근 한 달 + 앞으로 2주에 '{kw}' 일정 {cnt}건 — "
                    f"빈도 높음, 추가 약/검진/예약 챙길 시기 아닌지 확인."
                )

        # 충돌 미리 알림
        from google_calendar import find_conflicts
        future_events = [e for e in events if "dateTime" in e.get("start", {})
                         and datetime.fromisoformat(e["start"]["dateTime"]).astimezone(KST) > now]
        conflicts = find_conflicts(future_events)
        if conflicts:
            insights.append(f"앞으로 일정 중 시간 충돌 {len(conflicts)}건 — `/preview` 또는 봇에 충돌 물어봐.")

        # 일정 밀집도 분석 — 다음 7일에 timed 이벤트 5+개면 빠듯
        next_week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        next_week_end = next_week_start + timedelta(days=7)
        next_week_timed = [e for e in events
                           if "dateTime" in e.get("start", {})
                           and next_week_start <= datetime.fromisoformat(e["start"]["dateTime"]).astimezone(KST) < next_week_end]
        if len(next_week_timed) >= 5:
            insights.append(f"앞으로 7일에 시간 지정 일정 {len(next_week_timed)}건 — 빠듯한 한 주 예상.")

    except Exception as e:
        log.error("캘린더 패턴 분석 실패: %s", e)

    return insights


def analyze_condition_pattern() -> list[str]:
    """수면·컨디션 패턴 분석."""
    insights: list[str] = []
    try:
        from condition_tracker import get_recent
        recent = get_recent(days=7)
        if not recent:
            return insights

        avg_sleep = sum(r.get("sleep_hours", 0) for r in recent) / len(recent)
        if avg_sleep > 0 and avg_sleep < 6:
            insights.append(f"지난 7일 평균 수면 {avg_sleep:.1f}h — 부족. 일찍 자는 거 추천.")

        scores = [r.get("score", 0) for r in recent if r.get("score")]
        if scores:
            avg_score = sum(scores) / len(scores)
            if avg_score < 5:
                insights.append(f"지난 7일 컨디션 평균 {avg_score:.1f}점 — 회복 필요해 보임.")
    except Exception as e:
        log.error("컨디션 패턴 분석 실패: %s", e)
    return insights


def analyze_workload() -> list[str]:
    """업무 시간 분포 분석."""
    insights: list[str] = []
    try:
        from work_timer import get_week_report
        report = get_week_report()
        if report and "총" in report:
            insights.append(f"이번주 작업 시간 요약:\n{report}")
    except Exception as e:
        log.error("워크로드 분석 실패: %s", e)
    return insights


def generate_insights() -> str:
    """모든 통찰을 하나의 텍스트로 합쳐 반환."""
    parts: list[str] = []
    parts.extend(analyze_calendar_pattern())
    parts.extend(analyze_condition_pattern())
    parts.extend(analyze_workload())

    if not parts:
        return ""

    return "💡 능동 통찰:\n" + "\n".join(f"• {p}" for p in parts)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(generate_insights() or "(통찰 없음)")
