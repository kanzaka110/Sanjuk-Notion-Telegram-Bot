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
