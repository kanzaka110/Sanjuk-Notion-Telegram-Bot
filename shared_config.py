"""
공통 설정 모듈 — 전체 봇이 공유하는 설정과 유틸리티.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
봇별 config.py에서 이 모듈을 import하여 사용.

계층 구조:
  1. shared_config.py  — 공통 상수, 타임존, 유틸리티
  2. 봇별 .env         — 봇별 시크릿 (TELEGRAM_BOT_TOKEN 등)
  3. 봇별 config.py    — 봇별 설정, 프롬프트
"""

import os
import sys
from datetime import timedelta, timezone
from typing import NamedTuple

from dotenv import load_dotenv


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
    EnvRequirement("GEMINI_API_KEY", True, "Gemini API 키"),
]

BOT_EXTRA_ENV: dict[str, list[EnvRequirement]] = {
    "Chat_bot": [
        EnvRequirement("GITHUB_TOKEN", False, "GitHub 메모리 push용"),
        EnvRequirement("GITHUB_REPO", False, "GitHub 리포 경로"),
    ],
    "Luck_bot": [
        EnvRequirement("ANTHROPIC_API_KEY", True, "Claude Sonnet API 키"),
    ],
    "UE_bot": [
        EnvRequirement("ANTHROPIC_API_KEY", True, "Claude Sonnet API 키"),
        EnvRequirement("NOTION_API_KEY", True, "Notion API 키"),
        EnvRequirement("NOTION_DATABASE_ID", True, "Notion DB ID"),
    ],
    "GameNews_bot": [
        EnvRequirement("ANTHROPIC_API_KEY", True, "Claude Sonnet API 키"),
    ],
}


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
