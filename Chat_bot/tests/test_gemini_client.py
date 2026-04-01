"""gemini_client.py 단위 테스트 (API mock)."""

import os
from datetime import date, datetime
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import KST, MODEL_FLASH, MODEL_PRO, PRO_DAILY_LIMIT, PRO_WARNING_THRESHOLD
from gemini_client import GeminiClient, ModelState


@pytest.fixture
def client():
    """Gemini 클라이언트를 생성한다."""
    with patch("gemini_client.genai.Client"):
        c = GeminiClient()
        # 날짜 리셋을 위해 오늘 날짜 설정
        c._state = replace(c._state, last_reset_date=datetime.now(KST).date())
        yield c


def test_default_model_is_flash(client):
    """기본 모델은 Flash."""
    assert client.state.current_model == MODEL_FLASH


def test_switch_to_pro_succeeds(client):
    """Pro 전환 성공."""
    success, msg = client.switch_to_pro()
    assert success is True
    assert client.state.current_model == MODEL_PRO
    assert "Pro 모드" in msg


def test_switch_to_pro_fails_at_limit(client):
    """한도 소진 시 Pro 전환 실패."""
    client._state = replace(client._state, pro_used_today=PRO_DAILY_LIMIT)
    success, msg = client.switch_to_pro()
    assert success is False
    assert client.state.current_model == MODEL_FLASH
    assert "한도" in msg


def test_switch_to_flash(client):
    """Flash 복귀."""
    client._state = replace(client._state, current_model=MODEL_PRO)
    msg = client.switch_to_flash()
    assert client.state.current_model == MODEL_FLASH
    assert "Flash" in msg


def test_auto_fallback_at_threshold(client):
    """80% 도달 시 자동 Flash 폴백."""
    client._state = replace(
        client._state,
        current_model=MODEL_PRO,
        pro_used_today=PRO_WARNING_THRESHOLD,
    )
    notice = client._check_auto_fallback()
    assert notice is not None
    assert client.state.current_model == MODEL_FLASH
    assert "자동" in notice


def test_no_fallback_below_threshold(client):
    """80% 미만이면 폴백 없음."""
    client._state = replace(
        client._state,
        current_model=MODEL_PRO,
        pro_used_today=PRO_WARNING_THRESHOLD - 1,
    )
    notice = client._check_auto_fallback()
    assert notice is None
    assert client.state.current_model == MODEL_PRO


def test_daily_reset(client):
    """날짜 변경 시 카운터 리셋."""
    from datetime import timedelta
    yesterday = datetime.now(KST).date() - timedelta(days=1)
    client._state = replace(
        client._state,
        pro_used_today=50,
        last_reset_date=yesterday,
    )
    client._reset_if_new_day()
    assert client.state.pro_used_today == 0


def test_status_shows_info(client):
    """상태 메시지에 모델명과 남은 횟수가 포함."""
    status = client.get_status()
    assert "Flash" in status
    assert str(PRO_DAILY_LIMIT) in status
