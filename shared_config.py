"""
공통 설정 모듈 — 전체 봇이 공유하는 설정과 유틸리티.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
봇별 config.py에서 이 모듈을 import하여 사용.

계층 구조:
  1. shared_config.py  — 공통 상수, 타임존, 유틸리티
  2. 봇별 .env         — 봇별 시크릿 (TELEGRAM_BOT_TOKEN 등)
  3. 봇별 config.py    — 봇별 설정, 프롬프트
"""

import logging
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from dotenv import load_dotenv

log = logging.getLogger(__name__)


# ─── 타임존 ─────────────────────────────────────────────
KST = timezone(timedelta(hours=9))

# ─── 공통 상수 ──────────────────────────────────────────
TELEGRAM_CHAT_ID_DEFAULT = "0"
MAX_MESSAGE_LENGTH = 4000  # 텔레그램 메시지 길이 제한
REPO_NAME = "kanzaka110/Sanjuk-Notion-Telegram-Bot"


class EnvRequirement(NamedTuple):
    """환경변수 요구사항 정의."""

    key: str
    required: bool
    description: str


# ─── 봇별 필수 환경변수 정의 ────────────────────────────
COMMON_ENV = [
    EnvRequirement("TELEGRAM_BOT_TOKEN", True, "텔레그램 봇 토큰"),
    EnvRequirement("TELEGRAM_CHAT_ID", False, "허용 Chat ID"),
]

BOT_EXTRA_ENV: dict[str, list[EnvRequirement]] = {
    "Chat_bot": [
        EnvRequirement("GITHUB_TOKEN", False, "GitHub 메모리 push용"),
        EnvRequirement("GITHUB_REPO", False, "GitHub 리포 경로"),
    ],
}


# ─── Claude CLI 유틸리티 ───────────────────────────��───
CLAUDE_CLI = "/usr/bin/claude"


def claude_cli(
    prompt: str,
    *,
    model: str = "sonnet",
    system_prompt: str = "",
    timeout: int = 120,
    web_search: bool = False,
    json_schema: str = "",
    effort: str = "",
) -> str:
    """Claude CLI를 subprocess로 호출한다 (API 비용 $0).

    Args:
        prompt: 사용자 프롬프트
        model: 모델 선택 (sonnet, opus, haiku)
        system_prompt: 시스템 프롬프트 (선택)
        timeout: 타임아웃 (초)
        web_search: 웹 검색 도구 활성화
        json_schema: JSON 스키마 (구조화된 출력)
        effort: 탐색 깊이 (low, medium, high, max)

    Returns:
        CLI 응답 텍스트. 실패 시 빈 문자열.
    """
    cmd = [CLAUDE_CLI, "-p", prompt, "--model", model,
           "--disable-slash-commands", "--no-session-persistence"]
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]
    if web_search:
        cmd += ["--allowedTools", "WebSearch,WebFetch"]
    if json_schema:
        cmd += ["--json-schema", json_schema]
    if effort:
        cmd += ["--effort", effort]

    # ANTHROPIC_API_KEY가 설정되면 CLI가 Max 구독 대신 API 키를 사용하므로 제거
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        error_detail = (result.stderr.strip() or result.stdout.strip()
                        or "알 수 없는 오류")
        log.warning("Claude CLI 실패: returncode=%d, error=%s",
                    result.returncode, error_detail[:300])
        return ""
    except subprocess.TimeoutExpired:
        log.warning("Claude CLI 타임아웃 (%d초)", timeout)
        return ""
    except FileNotFoundError:
        log.error("Claude CLI를 찾을 수 없습니다: %s", CLAUDE_CLI)
        return ""
    except Exception as e:
        log.warning("Claude CLI 오류: %s", e)
        return ""


# ─── 세션 관리 ─────────────────────────────────────────
_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
_active_sessions: dict[str, str] = {}  # bot_name → session_id


def _get_daily_session_id(bot_name: str) -> str:
    """날짜 기반 세션 ID를 반환한다 (하루 1세션)."""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    return str(uuid.uuid5(_NAMESPACE, f"{bot_name}-{today}"))


def claude_cli_session(
    prompt: str,
    *,
    bot_name: str = "default",
    model: str = "sonnet",
    system_prompt: str = "",
    timeout: int = 90,
    tools: str = "WebSearch,WebFetch,Read",
) -> str:
    """세션 유지형 Claude CLI 호출 (멀티턴 대화 + 도구).

    첫 호출은 --session-id로 새 세션 생성,
    이후 호출은 --resume로 세션 이어가기.

    Args:
        prompt: 사용자 프롬프트
        bot_name: 봇 이름 (세션 구분용)
        model: 모델 선택
        system_prompt: 시스템 프롬프트 (첫 호출에만 적용)
        timeout: 타임아웃 (초)
        tools: 허용할 도구 (쉼표 구분)

    Returns:
        CLI 응답 텍스트. 실패 시 빈 문자열.
    """
    session_id = _get_daily_session_id(bot_name)
    is_resumed = session_id in _active_sessions

    cmd = [CLAUDE_CLI, "-p", prompt, "--model", model,
           "--disable-slash-commands"]

    if tools:
        cmd += ["--allowedTools", tools]

    if is_resumed:
        cmd += ["--resume", session_id]
    else:
        cmd += ["--session-id", session_id]
        if system_prompt:
            cmd += ["--system-prompt", system_prompt]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0 and result.stdout.strip():
            _active_sessions[bot_name] = session_id
            return result.stdout.strip()

        stderr = result.stderr[:300] if result.stderr else ""
        # 세션 충돌 시 resume으로 재시도
        if "already in use" in stderr and not is_resumed:
            _active_sessions[bot_name] = session_id
            return claude_cli_session(
                prompt, bot_name=bot_name, model=model,
                system_prompt=system_prompt, timeout=timeout,
            )
        log.warning("Claude CLI 세션 실패: rc=%d, stderr=%s",
                    result.returncode, stderr)
        return ""
    except subprocess.TimeoutExpired:
        log.warning("Claude CLI 세션 타임아웃 (%d초)", timeout)
        _active_sessions[bot_name] = session_id
        return ""
    except FileNotFoundError:
        log.error("Claude CLI를 찾을 수 없습니다: %s", CLAUDE_CLI)
        return ""
    except Exception as e:
        log.warning("Claude CLI 세션 오류: %s", e)
        return ""


def validate_env(bot_name: str, *, exit_on_fail: bool = True) -> list[str]:
    """봇에 필요한 환경변수를 검증한다.

    Args:
        bot_name: 봇 디렉토리명 (Chat_bot, Luck_bot 등)
        exit_on_fail: True이면 필수 변수 누락 시 sys.exit(1)

    Returns:
        누락된 환경변수 키 목록 (비필수 포함)
    """
    all_reqs = COMMON_ENV + BOT_EXTRA_ENV.get(bot_name, [])
    missing_required: list[str] = []
    missing_optional: list[str] = []

    for req in all_reqs:
        value = os.environ.get(req.key, "")
        if not value:
            if req.required:
                missing_required.append(f"  - {req.key}: {req.description}")
            else:
                missing_optional.append(req.key)

    if missing_required:
        msg = f"[{bot_name}] 필수 환경변수 누락:\n" + "\n".join(missing_required)
        if exit_on_fail:
            print(msg, file=sys.stderr)
            sys.exit(1)
        else:
            return [line.split(":")[0].strip("- ") for line in missing_required]

    return missing_optional


def load_bot_env(bot_dir: str) -> None:
    """봇 디렉토리의 .env 파일을 로드한다.

    Args:
        bot_dir: 봇 소스 디렉토리의 절대 경로
    """
    env_path = os.path.join(bot_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        # 루트 .env 폴백 (UE_bot, GameNews_bot)
        root_env = os.path.join(os.path.dirname(bot_dir), ".env")
        if os.path.exists(root_env):
            load_dotenv(root_env)
