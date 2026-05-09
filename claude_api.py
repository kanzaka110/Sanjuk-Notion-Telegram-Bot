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
