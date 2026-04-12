"""summarizer.py 단위 테스트."""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import KST
from database import Message
from summarizer import create_memory_markdown, _format_conversation


def _make_message(role: str, content: str) -> Message:
    """테스트용 메시지를 생성한다."""
    return Message(
        id=1,
        chat_id=123,
        role=role,
        content=content,
        model_used="flash",
        created_at=datetime.now(KST),
    )


def test_create_memory_markdown_format():
    """마크다운에 프론트매터가 포함되는지 확인."""
    now = datetime(2026, 3, 30, 23, 0, tzinfo=KST)
    md = create_memory_markdown(now, "- UE5 작업 스트레스\n- 치킨 먹음")

    assert "---" in md
    assert "name: 수다봇 대화 요약 2026-03-30" in md
    assert "type: user" in md
    assert "UE5 작업 스트레스" in md


def test_create_memory_markdown_date_format():
    """날짜 형식이 YYYY-MM-DD인지 확인."""
    now = datetime(2026, 1, 5, 23, 0, tzinfo=KST)
    md = create_memory_markdown(now, "테스트")
    assert "2026-01-05" in md


def test_format_conversation():
    """대화 포맷이 올바른지 확인."""
    messages = [
        _make_message("user", "오늘 날씨 좋다"),
        _make_message("assistant", "진짜? 어디 나갈 거야?"),
    ]
    text = _format_conversation(messages)
    assert "사용자: 오늘 날씨 좋다" in text
    assert "봇: 진짜?" in text


def test_format_empty_conversation():
    """빈 대화 포맷."""
    text = _format_conversation([])
    assert text == ""


@pytest.mark.asyncio
async def test_summarize_empty_returns_none():
    """빈 메시지 리스트는 None 반환."""
    from summarizer import summarize_messages
    result = await summarize_messages([])
    assert result is None
