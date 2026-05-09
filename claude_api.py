"""
Claude API 직접 호출 모듈 — OAuth 토큰 기반 ($0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Claude Max OAuth 토큰으로 Anthropic API 직접 호출.
CLI 오버헤드(~16초) 없이 1~4초 응답.
"""

import json
import logging
import time
from pathlib import Path

from anthropic import Anthropic

log = logging.getLogger(__name__)

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"

# 토큰 캐시
_cached_token: str = ""
_token_expires: float = 0


def _get_token() -> str:
    """OAuth 토큰을 읽고 캐시한다."""
    global _cached_token, _token_expires

    now = time.time() * 1000  # ms
    if _cached_token and _token_expires > now + 60_000:
        return _cached_token

    try:
        data = json.loads(CREDENTIALS_PATH.read_text())
        oauth = data.get("claudeAiOauth", {})
        _cached_token = oauth.get("accessToken", "")
        _token_expires = oauth.get("expiresAt", 0)
        return _cached_token
    except Exception as e:
        log.error("OAuth 토큰 읽기 실패: %s", e)
        return _cached_token


def _get_client() -> Anthropic | None:
    """Anthropic 클라이언트를 반환한다."""
    token = _get_token()
    if not token:
        log.error("OAuth 토큰 없음")
        return None
    return Anthropic(api_key=token)


# ─── 대화 히스토리 관리 ────────────────────────────────
_conversations: dict[str, list[dict]] = {}
MAX_HISTORY = 40  # 최근 40턴 유지


def _get_history(session: str) -> list[dict]:
    """세션의 대화 히스토리를 반환한다."""
    if session not in _conversations:
        _conversations[session] = []
    return _conversations[session]


def _trim_history(history: list[dict]) -> list[dict]:
    """히스토리가 너무 길면 앞부분을 자른다."""
    if len(history) > MAX_HISTORY:
        return history[-MAX_HISTORY:]
    return history


# ─── Tool Use 도구 정의 ────────────────────────────────
# Anthropic API tools 스키마. 비서봇이 동적으로 호출할 수 있는 도구들.
ASSISTANT_TOOLS = [
    {
        "name": "get_calendar",
        "description": "캘린더에서 일정을 조회한다. scope=today/week(14일)/month 중 선택.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["today", "week", "month"],
                    "description": "조회 범위. today=오늘만, week=오늘부터 14일, month=이번 달 남은 일정",
                }
            },
            "required": ["scope"],
        },
    },
    {
        "name": "find_calendar_conflicts",
        "description": "앞으로 14일 안의 시간 겹침 일정 쌍을 찾는다. 충돌 확인용.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_memory",
        "description": "과거 대화/메모에서 키워드로 검색. 사용자가 '지난번에', '예전에' 라고 할 때 활용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색어"},
                "n_results": {"type": "integer", "description": "결과 수 (기본 5)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_todos",
        "description": "현재 미완료 할일 목록을 가져온다.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "web_search",
        "description": "최신 뉴스, 주가, 기술 정보 등 인터넷 검색이 필요할 때.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "검색어"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_gcp_status",
        "description": "GCP VM 시스템 상태(봇 서비스 / 메모리 / 디스크 / Claude Code 세션) 확인.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_unread_emails",
        "description": "Gmail의 미확인 메일 최근 N건 요약. inbox 정리/triage 시 사용. 토큰 미설정 시 안내 메시지 반환.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "조회할 메일 수 (기본 5, 최대 15)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_email_count",
        "description": "Gmail의 미확인 메일 개수만 빠르게 확인. 'unread 메일 몇 개야?' 같은 질문에 적합.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "kg_add_fact",
        "description": (
            "지식 그래프에 사실(subject—predicate—object 트리플)을 추가한다. "
            "사람·프로젝트·관계·이벤트 같은 의미 있는 정보를 알게 됐을 때 호출. "
            "예: subject='광호', predicate='친구이며', object='5/23 부산 SRT 동행' / "
            "subject='MAHA', predicate='프로젝트', object='시프트업 페이셜팀'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "주체 (사람·프로젝트·개념 등)"},
                "predicate": {"type": "string", "description": "관계 동사구"},
                "object": {"type": "string", "description": "대상/속성"},
            },
            "required": ["subject", "predicate", "object"],
        },
    },
    {
        "name": "kg_query",
        "description": (
            "지식 그래프에서 entity(사람·프로젝트·키워드)와 연결된 모든 사실을 조회. "
            "사용자가 '광호 누구야?' 같은 질문하면 이 도구로 쌓인 사실 회상. "
            "search_memory(벡터)와 보완적 — 관계가 명확할 땐 KG, 자유 텍스트 회상은 RAG."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "조회할 entity 이름"},
                "limit": {"type": "integer", "description": "최대 결과 수 (기본 30)"},
            },
            "required": ["entity"],
        },
    },
    {
        "name": "get_today_luck",
        "description": "운세봇(Sanjuk_Luck_bot)의 오늘의 운세를 가져온다. 사주 기반 분석이라 수다봇 비서가 컨텍스트로 활용 가능.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_proactive_insights",
        "description": "능동 통찰 — 캘린더 패턴(반복 방문지·일정 밀집), 컨디션 패턴(수면·점수), 워크로드 분석을 종합해서 봇이 먼저 알려야 할 것들을 반환.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_work_summary",
        "description": "work_timer 기록으로 작업 시간 요약. period=today/week.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["today", "week"]},
            },
            "required": ["period"],
        },
    },
    {
        "name": "log_habit",
        "description": "사용자가 '약 먹었어' '운동 했어' 등 말하면 이 도구로 기록. status는 'done'/'skip'/'partial'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "habit_name": {"type": "string", "description": "예: 약, 운동"},
                "status": {"type": "string", "enum": ["done", "skip", "partial"]},
                "note": {"type": "string", "description": "선택 메모"},
            },
            "required": ["habit_name", "status"],
        },
    },
    {
        "name": "get_habit_summary",
        "description": "최근 N일 습관 달성률 요약. 사용자가 '약 잘 챙겨먹고 있어?' 묻거나 봇이 능동 리마인드 시 사용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "기본 7"},
                "habit_name": {"type": "string", "description": "특정 습관만 (선택)"},
            },
            "required": [],
        },
    },
    {
        "name": "list_automations",
        "description": "등록된 자동화 규칙 목록. 사용자가 '내 자동화 뭐 있어?' 물을 때 사용.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "add_automation",
        "description": (
            "자동화 규칙 추가. trigger_type=daily_at(time HH:MM), weekly_at(weekday 0~6, time HH:MM), "
            "on_calendar_keyword(keyword, minutes_before). action_type=send_message(text), prompt_claude(prompt). "
            "예: 매일 8:30에 '오늘 잘 챙겨!' 메시지 → trigger=daily_at, time=08:30, action=send_message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "trigger_type": {"type": "string", "enum": ["daily_at", "weekly_at", "on_calendar_keyword"]},
                "trigger_config": {"type": "object", "description": "trigger 타입별 설정 dict"},
                "action_type": {"type": "string", "enum": ["send_message", "prompt_claude"]},
                "action_config": {"type": "object", "description": "action 타입별 설정 dict"},
            },
            "required": ["name", "trigger_type", "trigger_config", "action_type", "action_config"],
        },
    },
]


def _execute_tool(name: str, args: dict) -> str:
    """도구 호출을 실행해 텍스트 결과를 반환한다."""
    try:
        if name == "get_calendar":
            from google_calendar import get_calendar_context
            return get_calendar_context(args.get("scope", "today")) or "(캘린더 데이터 없음)"

        if name == "find_calendar_conflicts":
            from google_calendar import _fetch_events, find_conflicts
            from datetime import datetime, timedelta, timezone
            kst = timezone(timedelta(hours=9))
            now = datetime.now(kst).replace(hour=0, minute=0, second=0, microsecond=0)
            end = now + timedelta(days=14)
            evs = _fetch_events(now, end)
            pairs = find_conflicts(evs)
            if not pairs:
                return "충돌 없음."
            lines = ["충돌 일정:"]
            for a, b in pairs[:10]:
                a_t = a.get("start", {}).get("dateTime", "")
                b_t = b.get("start", {}).get("dateTime", "")
                lines.append(f"  - {a_t} '{a.get('summary','')}' ⇄ {b_t} '{b.get('summary','')}'")
            return "\n".join(lines)

        if name == "search_memory":
            from rag_memory import search_memory
            results = search_memory(args["query"], n_results=args.get("n_results", 5))
            if not results:
                return "관련 메모 없음."
            return "\n\n".join(
                f"[{r.get('metadata', {}).get('date', '?')}] {r.get('content', '')[:300]}"
                for r in results
            )

        if name == "get_todos":
            from todo_manager import get_todo_context
            return get_todo_context() or "(할일 없음)"

        if name == "web_search":
            from web_search import web_search
            return web_search(args["query"]) or "(검색 결과 없음)"

        if name == "get_gcp_status":
            from gcp_status import get_gcp_context
            return get_gcp_context() or "(GCP 상태 정보 없음)"

        if name == "get_unread_emails":
            from gmail_client import get_recent_unread, _get_service
            if not _get_service():
                return "Gmail OAuth 미설정 — `python gmail_client.py --auth` 실행 필요."
            limit = min(int(args.get("limit", 5)), 15)
            mails = get_recent_unread(limit)
            if not mails:
                return "미확인 메일 없음."
            lines = [f"미확인 메일 {len(mails)}건:"]
            for m in mails:
                sender = m.get("from", "").split("<")[0].strip()
                lines.append(f"  - {sender} | {m.get('subject', '')}")
                snip = (m.get("snippet") or "").strip()
                if snip:
                    lines.append(f"      → {snip[:120]}")
            return "\n".join(lines)

        if name == "get_email_count":
            from gmail_client import get_unread_count, _get_service
            if not _get_service():
                return "Gmail OAuth 미설정."
            n = get_unread_count()
            return f"미확인 메일 {n}건" if n >= 0 else "Gmail 조회 실패"

        if name == "kg_add_fact":
            from knowledge_graph import add_fact
            ok = add_fact(args["subject"], args["predicate"], args["object"])
            return "사실 저장 완료" if ok else "이미 존재하거나 저장 실패"

        if name == "kg_query":
            from knowledge_graph import query_related, format_facts
            results = query_related(args["entity"], limit=args.get("limit", 30))
            return f"'{args['entity']}'에 대한 사실:\n" + format_facts(results)

        if name == "get_today_luck":
            try:
                # luck_bot은 비동기 함수 — sync wrapper 필요
                import asyncio
                from Luck_bot.luck_bot import generate_daily_fortune
                loop = asyncio.new_event_loop()
                try:
                    text = loop.run_until_complete(generate_daily_fortune())
                finally:
                    loop.close()
                return text or "(오늘의 운세 생성 실패)"
            except Exception as e:
                return f"(운세봇 호출 실패: {e})"

        if name == "get_proactive_insights":
            from proactive_insights import generate_insights
            return generate_insights() or "(특별한 통찰 없음 — 평온한 상태)"

        if name == "get_work_summary":
            from work_timer import get_today_report, get_week_report
            period = args.get("period", "today")
            if period == "week":
                return get_week_report() or "(이번주 작업 기록 없음)"
            return get_today_report() or "(오늘 작업 기록 없음)"

        if name == "log_habit":
            from habit_tracker import log_habit
            ok = log_habit(args["habit_name"], args["status"], args.get("note", ""))
            return "기록 완료" if ok else "기록 실패"

        if name == "get_habit_summary":
            from habit_tracker import get_summary
            return get_summary(args.get("habit_name"), args.get("days", 7))

        if name == "list_automations":
            from automations import list_automations, format_rule_list
            return format_rule_list(list_automations())

        if name == "add_automation":
            from automations import add_automation
            rid = add_automation(
                args["name"],
                args["trigger_type"],
                args["trigger_config"],
                args["action_type"],
                args["action_config"],
            )
            return f"자동화 #{rid} '{args['name']}' 등록 완료"

        return f"(알 수 없는 도구: {name})"
    except Exception as e:
        log.error("도구 실행 실패 (%s): %s", name, e)
        return f"(도구 오류: {e})"


def chat_with_tools(
    message: str,
    *,
    session: str = "default",
    model: str = "claude-sonnet-4-6",
    system: str = "",
    max_tokens: int = 2048,
    max_iterations: int = 5,
) -> str:
    """Tool use 지원 대화 호출. Claude가 필요할 때 도구를 호출하고 결과를 보고 다시 답한다."""
    client = _get_client()
    if not client:
        return ""

    history = _get_history(session)
    history.append({"role": "user", "content": message})
    history = _trim_history(history)
    _conversations[session] = history

    fallback_used = False

    for _iter in range(max_iterations):
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": history,
            "tools": ASSISTANT_TOOLS,
        }
        if system:
            kwargs["system"] = system

        try:
            response = client.messages.create(**kwargs)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str and "haiku" not in model and not fallback_used:
                log.warning("Sonnet rate limit, haiku로 폴백 (tool use)")
                model = MODEL_MAP.get("haiku", "claude-haiku-4-5-20251001")
                fallback_used = True
                continue
            log.error("Claude API 오류 (tool use): %s", e)
            if history and history[-1]["role"] == "user":
                history.pop()
            return ""

        # 도구 호출 없이 끝나면 결과 반환
        if response.stop_reason != "tool_use":
            text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
            answer = "".join(text_blocks).strip()
            history.append({"role": "assistant", "content": response.content})
            return answer

        # tool_use 응답 처리
        history.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                tool_name = block.name
                tool_args = block.input or {}
                log.info("도구 호출: %s(%s)", tool_name, tool_args)
                result_text = _execute_tool(tool_name, tool_args)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text[:5000],
                })
        history.append({"role": "user", "content": tool_results})

    log.warning("도구 루프 max_iterations 초과")
    return "(도구 호출이 너무 많아서 응답을 마무리 못 했어. 다시 시도해줘.)"


def load_session_history(session: str, messages: list[dict]) -> int:
    """세션 히스토리를 DB에서 복원할 때 사용. user/assistant 페어 형식.

    Args:
        session: 세션 이름
        messages: [{"role": "user"|"assistant", "content": str}, ...]

    Returns:
        실제 적재된 메시지 수.
    """
    # API는 user 메시지로 시작/끝나거나 user-assistant 교차여야 안전
    cleaned: list[dict] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if role not in ("user", "assistant") or not content:
            continue
        # 동일 role 연속이면 마지막 것만 유지
        if cleaned and cleaned[-1]["role"] == role:
            cleaned[-1] = {"role": role, "content": content}
        else:
            cleaned.append({"role": role, "content": content})

    # API는 user로 시작해야 함 — 첫 메시지가 assistant면 제거
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)

    cleaned = cleaned[-MAX_HISTORY:]
    _conversations[session] = cleaned
    log.info("세션 '%s' 히스토리 복원: %d턴", session, len(cleaned))
    return len(cleaned)


# ─── 메인 API 호출 ─────────────────────────────────────
def chat(
    message: str,
    *,
    session: str = "default",
    model: str = "claude-sonnet-4-6",
    system: str = "",
    max_tokens: int = 2048,
) -> str:
    """대화형 API 호출 (멀티턴 히스토리 유지).

    Args:
        message: 사용자 메시지
        session: 세션 이름 (대화 구분)
        model: 모델 ID
        system: 시스템 프롬프트
        max_tokens: 최대 응답 토큰

    Returns:
        응답 텍스트. 실패 시 빈 문자열.
    """
    client = _get_client()
    if not client:
        return ""

    history = _get_history(session)
    history.append({"role": "user", "content": message})
    history = _trim_history(history)
    _conversations[session] = history

    try:
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": history,
        }
        if system:
            kwargs["system"] = system

        response = client.messages.create(**kwargs)
        answer = response.content[0].text

        history.append({"role": "assistant", "content": answer})
        return answer

    except Exception as e:
        error_str = str(e)
        # sonnet rate limit → haiku 폴백
        if "429" in error_str and "haiku" not in model:
            log.warning("Sonnet rate limit, haiku로 폴백")
            fallback = MODEL_MAP.get("haiku", "claude-haiku-4-5-20251001")
            try:
                kwargs["model"] = fallback
                response = client.messages.create(**kwargs)
                answer = response.content[0].text
                history.append({"role": "assistant", "content": answer})
                return answer
            except Exception as e2:
                log.error("Haiku 폴백도 실패: %s", e2)

        log.error("Claude API 오류: %s", e)
        # 실패한 메시지는 히스토리에서 제거
        if history and history[-1]["role"] == "user":
            history.pop()
        return ""


def ask(
    prompt: str,
    *,
    model: str = "claude-haiku-4-5-20251001",
    system: str = "",
    max_tokens: int = 512,
) -> str:
    """단발성 API 호출 (히스토리 없음, 유틸리티용).

    Args:
        prompt: 프롬프트
        model: 모델 ID
        system: 시스템 프롬프트
        max_tokens: 최대 응답 토큰

    Returns:
        응답 텍스트. 실패 시 빈 문자열.
    """
    client = _get_client()
    if not client:
        return ""

    try:
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = client.messages.create(**kwargs)
        return response.content[0].text

    except Exception as e:
        log.error("Claude API 오류 (ask): %s", e)
        return ""


# ─── 모델 이름 매핑 ────────────────────────────────────
MODEL_MAP = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-7",
}


def resolve_model(name: str) -> str:
    """별칭을 실제 모델 ID로 변환한다."""
    return MODEL_MAP.get(name, name)
