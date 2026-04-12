"""shared_config.py 단위 테스트."""

import os
from unittest.mock import patch

import pytest

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared_config import (
    BOT_EXTRA_ENV,
    COMMON_ENV,
    KST,
    validate_env,
)


class TestKST:
    """타임존 상수 테스트."""

    def test_kst_offset_is_9_hours(self) -> None:
        """KST는 UTC+9."""
        from datetime import timedelta

        assert KST.utcoffset(None) == timedelta(hours=9)


class TestEnvRequirements:
    """환경변수 요구사항 정의 테스트."""

    def test_common_env_has_telegram_token(self) -> None:
        """공통 환경변수에 TELEGRAM_BOT_TOKEN 포함."""
        keys = [r.key for r in COMMON_ENV]
        assert "TELEGRAM_BOT_TOKEN" in keys

    def test_common_env_no_api_keys(self) -> None:
        """공통 환경변수에 API 키가 없음 (Claude CLI 사용)."""
        keys = [r.key for r in COMMON_ENV]
        assert "GEMINI_API_KEY" not in keys
        assert "ANTHROPIC_API_KEY" not in keys

    def test_bots_have_extra_env(self) -> None:
        """Chat_bot만 추가 환경변수 정의."""
        expected_bots = {"Chat_bot"}
        assert set(BOT_EXTRA_ENV.keys()) == expected_bots


class TestValidateEnv:
    """validate_env 검증 테스트."""

    def test_all_present_returns_empty(self) -> None:
        """필수+선택 모두 있으면 빈 리스트."""
        env = {
            "TELEGRAM_BOT_TOKEN": "tok",
            "TELEGRAM_CHAT_ID": "123",
            "GEMINI_API_KEY": "key",
            "GITHUB_TOKEN": "ghp",
            "GITHUB_REPO": "repo",
        }
        with patch.dict(os.environ, env, clear=False):
            result = validate_env("Chat_bot", exit_on_fail=False)
        assert result == []

    def test_missing_optional_returns_keys(self) -> None:
        """선택 환경변수 누락 시 키 목록 반환."""
        env = {
            "TELEGRAM_BOT_TOKEN": "tok",
            "GEMINI_API_KEY": "key",
        }
        with patch.dict(os.environ, env, clear=True):
            result = validate_env("Chat_bot", exit_on_fail=False)
        # TELEGRAM_CHAT_ID, GITHUB_TOKEN, GITHUB_REPO는 optional
        assert "TELEGRAM_CHAT_ID" in result

    def test_missing_required_returns_keys(self) -> None:
        """필수 환경변수 누락 시 키 목록 반환 (exit_on_fail=False)."""
        with patch.dict(os.environ, {}, clear=True):
            result = validate_env("Luck_bot", exit_on_fail=False)
        # TELEGRAM_BOT_TOKEN만 필수 (Luck_bot에 추가 필수 없음)
        assert len(result) >= 1

    def test_missing_required_exits(self) -> None:
        """필수 환경변수 누락 + exit_on_fail=True → SystemExit."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit):
                validate_env("Chat_bot", exit_on_fail=True)

    def test_unknown_bot_uses_common_only(self) -> None:
        """알 수 없는 봇은 공통 환경변수만 검증."""
        env = {
            "TELEGRAM_BOT_TOKEN": "tok",
            "GEMINI_API_KEY": "key",
        }
        with patch.dict(os.environ, env, clear=True):
            result = validate_env("Unknown_bot", exit_on_fail=False)
        # 공통 optional인 TELEGRAM_CHAT_ID만 누락
        assert result == ["TELEGRAM_CHAT_ID"]
