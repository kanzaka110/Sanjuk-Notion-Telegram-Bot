"""Hevy Cloud API 클라이언트.

- Base URL: https://api.hevyapp.com/v1
- Auth: api-key 헤더 (Pro 구독자만 발급 가능)
- 환경변수: HEVY_API_KEY

봇 본체는 비동기(asyncio)이므로 httpx.AsyncClient 사용.
cron 스크립트에서도 asyncio.run()으로 호출 가능.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

BASE_URL = "https://api.hevyapp.com/v1"
DEFAULT_TIMEOUT = 10.0


class HevyAPIError(Exception):
    """Hevy API 호출 중 발생한 오류."""


class HevyClient:
    """Hevy API 비동기 클라이언트."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("HEVY_API_KEY", "")
        if not key:
            raise HevyAPIError("HEVY_API_KEY 환경변수가 비어 있다")
        self._api_key = key
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"api-key": key, "accept": "application/json"},
            timeout=timeout,
        )

    async def __aenter__(self) -> "HevyClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        try:
            r = await self._client.get(path, params=params)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise HevyAPIError(
                f"GET {path} HTTP {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        except httpx.HTTPError as e:
            raise HevyAPIError(f"GET {path} 네트워크 오류: {e}") from e

    # ─── 워크아웃 ─────────────────────────────────────────
    async def get_workouts(self, page: int = 1, page_size: int = 10) -> dict:
        """워크아웃 페이지 (최신순)."""
        return await self._get(
            "/workouts", {"page": page, "pageSize": page_size}
        )

    async def get_workout(self, workout_id: str) -> dict:
        """특정 워크아웃 상세."""
        return await self._get(f"/workouts/{workout_id}")

    async def get_workout_count(self) -> int:
        """전체 워크아웃 카운트."""
        data = await self._get("/workouts/count")
        return int(data.get("workout_count", 0))

    async def iter_recent_workouts(self, days: int = 7) -> list[dict]:
        """최근 N일 안에 시작된 워크아웃을 모두 모아 반환한다.

        페이지네이션을 따라 내려가며 cutoff(start_time < now-days) 시점까지만 수집.
        Hevy API는 최신순으로 반환하므로 cutoff에 도달하면 즉시 종료.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        out: list[dict] = []
        page = 1
        while True:
            data = await self.get_workouts(page=page, page_size=10)
            workouts = data.get("workouts") or []
            if not workouts:
                break
            for w in workouts:
                start = _parse_iso(w.get("start_time"))
                if start is None:
                    continue
                if start < cutoff:
                    return out
                out.append(w)
            if page >= int(data.get("page_count", 1)):
                break
            page += 1
        return out

    # ─── 루틴/템플릿 ───────────────────────────────────────
    async def get_routines(self, page: int = 1, page_size: int = 10) -> dict:
        return await self._get(
            "/routines", {"page": page, "pageSize": page_size}
        )

    async def get_exercise_templates(
        self, page: int = 1, page_size: int = 100
    ) -> dict:
        return await self._get(
            "/exercise_templates", {"page": page, "pageSize": page_size}
        )


def _parse_iso(value: str | None) -> datetime | None:
    """Hevy의 ISO8601 문자열을 timezone-aware datetime으로 변환."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
