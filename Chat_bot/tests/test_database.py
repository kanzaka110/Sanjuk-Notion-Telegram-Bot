"""database.py 단위 테스트."""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta

import pytest
import pytest_asyncio

# config 로딩 전에 환경변수 설정
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from config import KST


@pytest_asyncio.fixture
async def tmp_db(tmp_path):
    """임시 DB 경로를 설정한다."""
    db_path = str(tmp_path / "test.db")
    config.DB_PATH = db_path

    # database 모듈을 다시 import하여 DB_PATH 반영
    import database
    database.DB_PATH = db_path
    await database.init_db()
    yield database
    config.DB_PATH = db_path


@pytest.mark.asyncio
async def test_save_and_retrieve(tmp_db):
    """메시지 저장 후 조회."""
    await tmp_db.save_message(123, "user", "안녕!", "flash")
    await tmp_db.save_message(123, "assistant", "안녕~ 반가워!", "flash")

    messages = await tmp_db.get_recent_messages(123, limit=10)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "안녕!"
    assert messages[1].role == "assistant"


@pytest.mark.asyncio
async def test_recent_messages_limit(tmp_db):
    """limit이 정상 작동하는지 확인."""
    for i in range(30):
        await tmp_db.save_message(123, "user", f"메시지 {i}", "flash")

    messages = await tmp_db.get_recent_messages(123, limit=10)
    assert len(messages) == 10
    # 가장 최근 10개만 반환 (21~30)
    assert "메시지 20" in messages[0].content


@pytest.mark.asyncio
async def test_get_today_messages(tmp_db):
    """오늘 메시지만 조회."""
    await tmp_db.save_message(123, "user", "오늘 메시지", "flash")

    messages = await tmp_db.get_today_messages(123)
    assert len(messages) >= 1
    assert messages[-1].content == "오늘 메시지"


@pytest.mark.asyncio
async def test_empty_database(tmp_db):
    """빈 DB에서 조회 시 빈 리스트."""
    messages = await tmp_db.get_recent_messages(999, limit=10)
    assert messages == []


@pytest.mark.asyncio
async def test_daily_stats(tmp_db):
    """일일 통계 확인."""
    await tmp_db.save_message(123, "user", "Flash 메시지", "flash")
    await tmp_db.save_message(123, "assistant", "Flash 응답", "flash")
    await tmp_db.save_message(123, "user", "Pro 메시지", "pro")
    await tmp_db.save_message(123, "assistant", "Pro 응답", "pro")

    stats = await tmp_db.get_daily_stats(123)
    assert stats["total"] == 4
    assert stats["flash"] == 2
    assert stats["pro"] == 2


@pytest.mark.asyncio
async def test_different_chat_ids(tmp_db):
    """다른 chat_id는 분리 조회."""
    await tmp_db.save_message(111, "user", "사용자A", "flash")
    await tmp_db.save_message(222, "user", "사용자B", "flash")

    messages_a = await tmp_db.get_recent_messages(111)
    messages_b = await tmp_db.get_recent_messages(222)
    assert len(messages_a) == 1
    assert len(messages_b) == 1
    assert messages_a[0].content == "사용자A"
