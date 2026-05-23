"""gemini_client.py (Claude API 직접 호출 기반) 단위 테스트."""

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gemini_client import GeminiClient


@pytest.fixture
def client():
    """GeminiClient 인스턴스를 생성한다."""
    return GeminiClient()


def test_get_status(client):
    """상태 메시지에 Claude API 직접 호출 모드가 포함."""
    status = client.get_status()
    assert "Claude" in status
    assert "API 직접 호출" in status


def test_switch_to_pro_always_succeeds(client):
    """Pro 전환은 항상 성공."""
    success, msg = client.switch_to_pro()
    assert success is True


def test_switch_to_flash(client):
    """Flash 복귀 메시지."""
    msg = client.switch_to_flash()
    assert "Sonnet 4.6" in msg


@pytest.mark.asyncio
async def test_ask_with_mock(client):
    """Claude API mock으로 ask 테스트."""
    from database import Message
    from datetime import datetime, timezone, timedelta
    KST = timezone(timedelta(hours=9))

    with patch("gemini_client.chat_with_tools", return_value="테스트 응답이야"):
        answer, notice = await client.ask(
            "안녕",
            recent_messages=[],
            core_memory_context="",
        )
        assert "테스트 응답이야" in answer
        assert notice is None


@pytest.mark.asyncio
async def test_ask_empty_response(client):
    """API 응답이 비어있으면 기본 메시지."""
    with patch("gemini_client.chat_with_tools", return_value=""):
        answer, _ = await client.ask("안녕", recent_messages=[])
        assert "응답" in answer or "다시" in answer
