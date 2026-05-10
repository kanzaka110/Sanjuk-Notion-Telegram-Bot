"""hevy/client.py 단위 테스트."""

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hevy.client import HevyAPIError, HevyClient, _parse_iso


# ─── 초기화 ────────────────────────────────────────────
def test_init_without_key_raises(monkeypatch):
    """HEVY_API_KEY 환경변수가 비어 있으면 에러."""
    monkeypatch.delenv("HEVY_API_KEY", raising=False)
    with pytest.raises(HevyAPIError):
        HevyClient(api_key=None)


def test_init_with_explicit_key():
    """키를 직접 주입하면 OK."""
    c = HevyClient(api_key="test_key_abc")
    assert c._api_key == "test_key_abc"


def test_init_reads_env(monkeypatch):
    """환경변수로 키 주입."""
    monkeypatch.setenv("HEVY_API_KEY", "env_key_xyz")
    c = HevyClient()
    assert c._api_key == "env_key_xyz"


# ─── _parse_iso ─────────────────────────────────────────
def test_parse_iso_z_suffix():
    """Z 접미사를 +00:00로 변환."""
    dt = _parse_iso("2026-05-09T19:30:00Z")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_iso_invalid():
    """잘못된 문자열은 None."""
    assert _parse_iso("not-a-date") is None
    assert _parse_iso(None) is None
    assert _parse_iso("") is None


# ─── get_workout_count ─────────────────────────────────
@pytest.mark.asyncio
async def test_get_workout_count_returns_int():
    """workout_count 필드를 int로 반환."""
    c = HevyClient(api_key="abc")
    with patch.object(c, "_get", AsyncMock(return_value={"workout_count": 42})):
        assert await c.get_workout_count() == 42
    await c.aclose()


@pytest.mark.asyncio
async def test_get_workout_count_missing_field():
    """필드 없으면 0."""
    c = HevyClient(api_key="abc")
    with patch.object(c, "_get", AsyncMock(return_value={})):
        assert await c.get_workout_count() == 0
    await c.aclose()


# ─── iter_recent_workouts ──────────────────────────────
@pytest.mark.asyncio
async def test_iter_recent_workouts_filters_by_cutoff():
    """7일 전보다 오래된 워크아웃은 cutoff에서 잘라낸다."""
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    old = (now - timedelta(days=10)).isoformat().replace("+00:00", "Z")

    c = HevyClient(api_key="abc")
    page1 = {
        "workouts": [
            {"id": "1", "start_time": recent},
            {"id": "2", "start_time": old},
        ],
        "page_count": 1,
        "page": 1,
    }
    with patch.object(c, "get_workouts", AsyncMock(return_value=page1)):
        out = await c.iter_recent_workouts(days=7)
    assert len(out) == 1
    assert out[0]["id"] == "1"
    await c.aclose()


@pytest.mark.asyncio
async def test_iter_recent_workouts_empty():
    """워크아웃 0건이면 빈 리스트."""
    c = HevyClient(api_key="abc")
    with patch.object(
        c, "get_workouts",
        AsyncMock(return_value={"workouts": [], "page_count": 1, "page": 1}),
    ):
        out = await c.iter_recent_workouts(days=7)
    assert out == []
    await c.aclose()


@pytest.mark.asyncio
async def test_iter_recent_workouts_paginates():
    """page_count > 1이면 다음 페이지까지 호출."""
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=1)).isoformat().replace("+00:00", "Z")

    c = HevyClient(api_key="abc")
    pages = [
        {"workouts": [{"id": "1", "start_time": recent}], "page_count": 2, "page": 1},
        {"workouts": [{"id": "2", "start_time": recent}], "page_count": 2, "page": 2},
    ]
    with patch.object(c, "get_workouts", AsyncMock(side_effect=pages)):
        out = await c.iter_recent_workouts(days=7)
    assert [w["id"] for w in out] == ["1", "2"]
    await c.aclose()
