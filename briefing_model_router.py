"""Run-scoped policy, privacy, cap and lineage owner for content briefings."""
from __future__ import annotations

import contextvars
import json
import os
import re
import unicodedata
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

POLICY_VERSION = "content-briefing-model-router.v1"
SCHEMA_VERSION = "briefing-model-event.v2"
DEFAULT_STATE_DIR = Path("/home/kanzaka110/.local/state/sanjuk-briefing-router/content")

POLICY = {
    "GAME_NEWS": {
        "GAME_PUBLIC_EVIDENCE": ("perplexity", "search-api", "public_evidence", 2, 30),
        "GAME_PUBLIC_ANALYSIS": ("grok", "grok-build-0.1", "public_analysis", 1, 180),
        "GAME_PUBLIC_EDITORIAL": ("codex", "gpt-5.6-sol", "public_editorial", 1, 300),
    },
    "AI_TOOLS": {
        "AI_PUBLIC_EVIDENCE": ("perplexity", "search-api", "public_evidence", 2, 30),
        "AI_PUBLIC_ANALYSIS": ("grok", "grok-build-0.1", "public_analysis", 1, 180),
        "AI_PUBLIC_EDITORIAL": ("codex", "gpt-5.6-sol", "public_editorial", 1, 300),
    },
    "LUCK": {
        "LUCK_PRIVATE_FINAL": ("claude", "sonnet", "private_advice", 3, 240),
    },
}
_PUBLIC_AUTHORITIES = {"public_evidence", "public_analysis", "public_editorial"}
_SENSITIVE = re.compile(
    r"birth[_ -]?date|birth[_ -]?time|생년월일|출생\s*시간|사주|일주|시주|연주|월주|"
    r"계좌|보유|주문|broker|holdings?|account(?:_id)?|credential|api[_ -]?key|"
    r"access[_ -]?token|refresh[_ -]?token|password|secret|perforce|confluence|[a-z]:\\",
    re.IGNORECASE,
)


class RoutingRefusal(RuntimeError):
    pass


@dataclass
class _Session:
    briefing_type: str
    state_dir: Path
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    counts: dict[str, int] = field(default_factory=dict)
    provider_counts: dict[str, int] = field(default_factory=dict)
    sensitive_rejections: int = 0
    public_successes: int = 0


_CURRENT: contextvars.ContextVar[_Session | None] = contextvars.ContextVar(
    "content_briefing_session", default=None
)


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).lower().split())


def assert_public_content(text: str) -> None:
    if not isinstance(text, str) or not text.strip() or len(text) > 16000:
        raise ValueError("payload_invalid")
    if _SENSITIVE.search(_normalize(text)):
        raise ValueError("sensitive_public_payload")


def _append_event(session: _Session, event: dict[str, object]) -> None:
    session.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(session.state_dir, 0o700)
    path = session.state_dir / "lineage-v1.jsonl"
    row = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "run_id": session.run_id,
        "briefing_type": session.briefing_type,
        "fallback_used": False,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        **event,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o600)


@contextmanager
def briefing_model_session(
    briefing_type: str, *, state_dir: str | Path | None = None
) -> Iterator[None]:
    if briefing_type not in POLICY:
        raise RoutingRefusal("briefing_type_not_allowed")
    session = _Session(briefing_type, Path(state_dir) if state_dir else DEFAULT_STATE_DIR)
    token = _CURRENT.set(session)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def get_run_summary() -> dict[str, object]:
    session = _CURRENT.get()
    if session is None:
        raise RoutingRefusal("briefing_session_missing")
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "run_id": session.run_id,
        "briefing_type": session.briefing_type,
        "provider_call_counts": dict(session.provider_counts),
        "sensitive_rejection_count": session.sensitive_rejections,
        "outbound_sensitive_count": 0 if session.public_successes else None,
        "order_authority_invocations": 0,
    }


def _default_executor(prompt: str, **kwargs: object) -> str:
    provider = str(kwargs["provider"])
    if provider == "perplexity":
        from briefing_perplexity import search_public
        return search_public(
            prompt,
            before_transport=kwargs.get("before_transport"),
            state_dir=kwargs.get("state_dir"),
            timeout=int(str(kwargs["timeout"])),
        )
    if provider == "grok":
        from briefing_grok_cli import grok_cli
        return grok_cli(prompt, timeout=int(kwargs["timeout"]))
    if provider == "codex":
        from briefing_codex_cli import codex_cli
        return codex_cli(prompt, timeout=int(kwargs["timeout"]))
    if provider == "claude":
        from shared_config import claude_cli
        return claude_cli(prompt, model="sonnet", timeout=int(kwargs["timeout"]))
    return ""


def route_current(
    stage: str,
    prompt: str,
    *,
    _executor: Callable[..., str] | None = None,
) -> str:
    session = _CURRENT.get()
    if session is None:
        raise RoutingRefusal("briefing_session_missing")
    cfg = POLICY[session.briefing_type].get(stage)
    if cfg is None:
        raise RoutingRefusal("stage_not_allowed")
    provider, model, authority, cap, timeout = cfg
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16000:
        raise RoutingRefusal("payload_invalid")
    try:
        if authority in _PUBLIC_AUTHORITIES:
            assert_public_content(prompt)
    except ValueError:
        session.sensitive_rejections += 1
        _append_event(session, {
            "stage": stage, "provider": provider, "role": stage.lower(), "model": model,
            "authority": authority, "reserved": False, "cache_hit": False,
            "outcome": "refused", "reason_code": "sensitive_public_payload",
        })
        raise RoutingRefusal("sensitive_public_payload")
    used = session.counts.get(stage, 0)
    if used >= cap:
        raise RoutingRefusal("stage_call_cap_exhausted")
    reserved = False

    def reserve_transport() -> None:
        nonlocal reserved
        if reserved:
            return
        current = session.counts.get(stage, 0)
        if current >= cap:
            raise RoutingRefusal("stage_call_cap_exhausted")
        session.counts[stage] = current + 1
        session.provider_counts[provider] = session.provider_counts.get(provider, 0) + 1
        reserved = True

    executor = _executor or _default_executor
    if _executor is not None or provider != "perplexity":
        reserve_transport()
    try:
        text = executor(
            prompt,
            provider=provider,
            model=model,
            authority=authority,
            timeout=timeout,
            state_dir=session.state_dir,
            before_transport=reserve_transport,
        )
    except Exception:
        _append_event(session, {
            "stage": stage, "provider": provider, "role": stage.lower(), "model": model,
            "authority": authority, "reserved": reserved, "cache_hit": False,
            "outcome": "failed", "reason_code": "provider_call_failed",
        })
        raise
    if not isinstance(text, str) or not text.strip():
        raise RoutingRefusal("provider_call_failed")
    if authority in _PUBLIC_AUTHORITIES:
        session.public_successes += 1
    _append_event(session, {
        "stage": stage, "provider": provider, "role": stage.lower(), "model": model,
        "authority": authority, "reserved": reserved, "cache_hit": not reserved,
        "outcome": "success", "reason_code": "",
    })
    return text.strip()


__all__ = ["POLICY", "RoutingRefusal", "assert_public_content", "briefing_model_session", "get_run_summary", "route_current"]
