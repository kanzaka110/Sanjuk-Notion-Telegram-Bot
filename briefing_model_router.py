"""Run-scoped policy, privacy, cap, delivery and lineage owner for content briefings."""
from __future__ import annotations

import contextvars
import json
import os
import re
import subprocess
import unicodedata
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

POLICY_VERSION = "content-briefing-model-router.v2"
SCHEMA_VERSION = "briefing-run-event.v3"
DEFAULT_STATE_DIR = Path("/home/kanzaka110/.local/state/sanjuk-briefing-router/content")
_REPO_ROOT = Path(__file__).resolve().parent

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
_ALLOWED_AUTHORITIES = _PUBLIC_AUTHORITIES | {"private_advice"}
_SENSITIVE = re.compile(
    r"birth[_ -]?date|birth[_ -]?time|생년월일|출생\s*시간|사주|일주|시주|연주|월주|"
    r"계좌|보유|주문|broker|holdings?|account(?:_id)?|credential|api[_ -]?key|"
    r"access[_ -]?token|refresh[_ -]?token|password|secret|perforce|confluence|[a-z]:\\",
    re.IGNORECASE,
)
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class RoutingRefusal(RuntimeError):
    pass


@dataclass
class _Session:
    briefing_type: str
    state_dir: Path
    repo_commit: str
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    counts: dict[str, int] = field(default_factory=dict)
    provider_counts: dict[str, int] = field(default_factory=dict)
    sensitive_rejections: int = 0
    fallback_count: int = 0
    outbound_sensitive_count: int = 0
    order_authority_invocations: int = 0
    delivery_recorded: bool = False
    delivery_success: bool = False
    delivery_attempts: int = 0
    summary_recorded: bool = False


_CURRENT: contextvars.ContextVar[_Session | None] = contextvars.ContextVar(
    "content_briefing_session", default=None
)


def _repo_commit(repo_root: Path = _REPO_ROOT) -> str:
    try:
        value = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout.strip().lower()
    except Exception as exc:
        raise RoutingRefusal("repo_commit_unavailable") from exc
    if not _COMMIT_RE.fullmatch(value):
        raise RoutingRefusal("repo_commit_invalid")
    return value


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
        "repo_commit": session.repo_commit,
        "briefing_type": session.briefing_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        **event,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o600)


def _summary(session: _Session) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "run_id": session.run_id,
        "repo_commit": session.repo_commit,
        "briefing_type": session.briefing_type,
        "provider_call_counts": dict(session.provider_counts),
        "stage_call_counts": dict(session.counts),
        "sensitive_rejection_count": session.sensitive_rejections,
        "fallback_count": session.fallback_count,
        "outbound_sensitive_count": session.outbound_sensitive_count,
        "order_authority_invocations": session.order_authority_invocations,
        "delivery_success": session.delivery_success,
        "delivery_attempts": session.delivery_attempts,
    }


def record_delivery(*, success: bool, reason_code: str = "", attempts: int = 1) -> None:
    session = _CURRENT.get()
    if session is None:
        raise RoutingRefusal("briefing_session_missing")
    if session.delivery_recorded:
        raise RoutingRefusal("delivery_already_recorded")
    if attempts < 0:
        raise RoutingRefusal("delivery_attempts_invalid")
    session.delivery_recorded = True
    session.delivery_success = bool(success)
    session.delivery_attempts = int(attempts)
    _append_event(session, {
        "event_type": "delivery_terminal",
        "channel": "telegram",
        "outcome": "success" if success else "failed",
        "reason_code": "" if success else (reason_code or "telegram_delivery_failed"),
        "attempts": int(attempts),
    })


@contextmanager
def briefing_model_session(
    briefing_type: str, *, state_dir: str | Path | None = None, run_id: str | None = None,
    repo_root: str | Path | None = None,
) -> Iterator[_Session]:
    if briefing_type not in POLICY:
        raise RoutingRefusal("briefing_type_not_allowed")
    session = _Session(
        briefing_type,
        Path(state_dir) if state_dir else DEFAULT_STATE_DIR,
        _repo_commit(Path(repo_root) if repo_root else _REPO_ROOT),
        run_id or uuid.uuid4().hex,
    )
    token = _CURRENT.set(session)
    try:
        yield session
    finally:
        if not session.delivery_recorded:
            record_delivery(success=False, reason_code="delivery_not_recorded", attempts=0)
        if not session.summary_recorded:
            _append_event(session, {"event_type": "run_summary", **_summary(session)})
            session.summary_recorded = True
        _CURRENT.reset(token)


def get_run_summary() -> dict[str, object]:
    session = _CURRENT.get()
    if session is None:
        raise RoutingRefusal("briefing_session_missing")
    return _summary(session)


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
        return grok_cli(prompt, timeout=int(str(kwargs["timeout"])))
    if provider == "codex":
        from briefing_codex_cli import codex_cli
        return codex_cli(prompt, timeout=int(str(kwargs["timeout"])))
    if provider == "claude":
        from shared_config import claude_cli
        return claude_cli(prompt, model="sonnet", timeout=int(str(kwargs["timeout"])))
    raise RoutingRefusal("provider_not_allowed")


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
    if authority not in _ALLOWED_AUTHORITIES:
        session.order_authority_invocations += 1
        raise RoutingRefusal("authority_not_allowed")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16000:
        raise RoutingRefusal("payload_invalid")
    try:
        if authority in _PUBLIC_AUTHORITIES:
            assert_public_content(prompt)
    except ValueError as exc:
        session.sensitive_rejections += 1
        _append_event(session, {
            "event_type": "provider_call", "stage": stage, "provider": provider,
            "role": stage.lower(), "model": model, "authority": authority,
            "reserved": False, "cache_hit": False, "outcome": "refused",
            "reason_code": "sensitive_public_payload",
        })
        raise RoutingRefusal("sensitive_public_payload") from exc
    if session.counts.get(stage, 0) >= cap:
        raise RoutingRefusal("stage_call_cap_exhausted")
    reserved = False

    def reserve_transport() -> None:
        nonlocal reserved
        if reserved:
            return
        if authority in _PUBLIC_AUTHORITIES:
            try:
                assert_public_content(prompt)
            except ValueError as exc:
                session.outbound_sensitive_count += 1
                raise RoutingRefusal("sensitive_public_payload") from exc
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
            prompt, provider=provider, model=model, authority=authority, timeout=timeout,
            state_dir=session.state_dir, before_transport=reserve_transport,
        )
    except Exception:
        _append_event(session, {
            "event_type": "provider_call", "stage": stage, "provider": provider,
            "role": stage.lower(), "model": model, "authority": authority,
            "reserved": reserved, "cache_hit": False, "outcome": "failed",
            "reason_code": "provider_call_failed",
        })
        raise
    if not isinstance(text, str) or not text.strip():
        raise RoutingRefusal("provider_call_failed")
    _append_event(session, {
        "event_type": "provider_call", "stage": stage, "provider": provider,
        "role": stage.lower(), "model": model, "authority": authority,
        "reserved": reserved, "cache_hit": not reserved, "outcome": "success",
        "reason_code": "",
    })
    return text.strip()


__all__ = [
    "POLICY", "POLICY_VERSION", "RoutingRefusal", "assert_public_content",
    "briefing_model_session", "get_run_summary", "record_delivery", "route_current",
]
