"""Bounded Perplexity Search API adapter for public briefing evidence."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Callable

import requests

from briefing_model_router import DEFAULT_STATE_DIR, assert_public_content

API_URL = "https://api.perplexity.ai/search"
KEY_PATH = Path("/home/kanzaka110/.claude-work/secrets/perplexity_api_key")
CACHE_TTL_SECONDS = 6 * 60 * 60
RATE_WINDOW_SECONDS = 60
RATE_MAX_CALLS = 3


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def _reserve_quota(state_dir: Path, now: float) -> None:
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = state_dir / "perplexity-quota-v1.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        quota_path = state_dir / "perplexity-quota-v1.json"
        rows = _read_json(quota_path, [])
        recent = [float(v) for v in rows if now - float(v) < RATE_WINDOW_SECONDS]
        if len(recent) >= RATE_MAX_CALLS:
            raise RuntimeError("perplexity_rate_budget_exhausted")
        recent.append(now)
        _atomic_json(quota_path, recent)


def _render(results: list[dict]) -> str:
    lines = []
    for index, item in enumerate(results[:12], 1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()[:300]
        url = str(item.get("url") or "").strip()[:1000]
        snippet = str(item.get("snippet") or item.get("text") or "").strip()[:800]
        published = str(item.get("date") or item.get("published_at") or "").strip()[:80]
        if not title or not url.startswith(("https://", "http://")):
            continue
        lines.append(f"[{index}] TITLE: {title}\nURL: {url}\nDATE: {published or 'UNKNOWN'}\nSNIPPET: {snippet}")
    return "\n\n".join(lines)


def search_public(
    prompt: str,
    *,
    before_transport: Callable[[], None] | None = None,
    state_dir: str | Path | None = None,
    timeout: int = 30,
) -> str:
    assert_public_content(prompt)
    root = Path(state_dir) if state_dir else DEFAULT_STATE_DIR
    query = prompt.strip()[:4000]
    query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
    cache_path = root / "perplexity-cache-v1.json"
    now = time.time()
    cache = _read_json(cache_path, {})
    cached = cache.get(query_hash) if isinstance(cache, dict) else None
    if isinstance(cached, dict) and now - float(cached.get("stored_at", 0)) < CACHE_TTL_SECONDS:
        text = str(cached.get("text") or "").strip()
        if text:
            return text

    key = KEY_PATH.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError("perplexity_key_unavailable")
    _reserve_quota(root, now)
    if before_transport:
        before_transport()
    response = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"query": query, "max_results": 12, "max_tokens_per_page": 1024},
        timeout=max(1, min(int(timeout), 60)),
        allow_redirects=False,
    )
    response.raise_for_status()
    if len(response.content) > 1024 * 1024:
        raise RuntimeError("perplexity_response_too_large")
    payload = response.json()
    results = payload.get("results", []) if isinstance(payload, dict) else []
    text = _render(results if isinstance(results, list) else [])
    if not text:
        raise RuntimeError("perplexity_empty_evidence")
    if not isinstance(cache, dict):
        cache = {}
    cache[query_hash] = {"stored_at": now, "text": text}
    _atomic_json(cache_path, cache)
    return text
