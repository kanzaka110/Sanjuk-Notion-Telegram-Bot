"""Bounded OAuth-only Grok adapter for public briefing stages.

The adapter has no broker/order authority and never inherits the service
environment. Prompts containing account, holding, order, or credential markers
are rejected before process creation.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
from contextvars import ContextVar

HERMES_RELEASE = "3c27eb6234bf91b8ceee9e9071591b31e9b148cb"
_RELEASE_ROOT = f"/home/kanzaka110/.local/share/sanjuk-grok-bridge/releases/{HERMES_RELEASE}"
HERMES_BIN = f"{_RELEASE_ROOT}/venv/bin/hermes"
HERMES_HOME = "/home/kanzaka110/.local/share/sanjuk-grok-bridge/home"
_PROVIDER = "xai-oauth"
_MODEL = "grok-build-0.1"
_OUTPUT_RE = re.compile(r"<SANJUK_OUTPUT>(.*?)</SANJUK_OUTPUT>", re.DOTALL)
_SENSITIVE_RE = re.compile(
    r"계좌|예수금|보유\s*(?:종목|수량|상태)|수량\s*[=:]|평단|주문|자동거래|실주문|"
    r"account(?:_id)?|holdings?|cost\s*basis|cash\s*(?:balance|buying)|broker|"
    r"credential|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|password|secret",
    re.IGNORECASE,
)
_LAST_FAILURE: ContextVar[str] = ContextVar("grok_cli_last_failure", default="")


class GrokPromptRefused(RuntimeError):
    """Prompt violated the public-only provider boundary."""


def get_last_failure_reason() -> str:
    return _LAST_FAILURE.get()


def _set_failure(reason: str) -> None:
    _LAST_FAILURE.set(reason)


def _oauth_only_environment() -> dict[str, str]:
    return {
        "HOME": "/home/kanzaka110",
        "HERMES_HOME": HERMES_HOME,
        "PATH": f"{_RELEASE_ROOT}/venv/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONUNBUFFERED": "1",
    }


def _wrapped_prompt(prompt: str, json_schema: str | None) -> str:
    shape = ""
    if json_schema:
        shape = f"\nReturn valid JSON matching this schema: {json_schema}"
    return (
        "Public-information analysis only. Do not request or infer account, holding, "
        "order, broker, credential, or personal data. "
        "Put the complete final response exactly once between <SANJUK_OUTPUT> and "
        "</SANJUK_OUTPUT>; do not use those markers elsewhere."
        f"{shape}\n\nTASK:\n{prompt}"
    )


def grok_cli(
    prompt: str,
    *,
    model: str = _MODEL,
    timeout: int = 180,
    effort: str = "none",
    json_schema: str | None = None,
    **_kwargs: object,
) -> str:
    """Run one OAuth Grok call and return only the bounded response payload."""
    del effort
    _set_failure("")
    if model != _MODEL:
        _set_failure("model_not_allowed")
        return ""
    if not isinstance(prompt, str) or not prompt.strip():
        _set_failure("empty_prompt")
        return ""
    try:
        from briefing_model_router import assert_public_content
        assert_public_content(prompt)
    except ValueError as exc:
        _set_failure("sensitive_prompt")
        raise GrokPromptRefused("sensitive_prompt") from exc

    command = [
        HERMES_BIN,
        "chat",
        "-Q",
        "-q",
        _wrapped_prompt(prompt, json_schema),
        "--provider",
        _PROVIDER,
        "-m",
        _MODEL,
        "-t",
        "safe",
        "--reasoning",
        "none",
    ]
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=_oauth_only_environment(),
            start_new_session=True,
        )
        stdout, _stderr = proc.communicate(timeout=max(1, int(timeout)))
    except subprocess.TimeoutExpired:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                proc.communicate(timeout=5)
            except Exception:
                pass
        _set_failure("timeout")
        return ""
    except (OSError, ValueError):
        _set_failure("unavailable")
        return ""

    if proc.returncode != 0:
        _set_failure("unavailable")
        return ""
    matches = _OUTPUT_RE.findall(stdout or "")
    if not matches:
        _set_failure("invalid_output")
        return ""
    payload = matches[-1].strip()
    if json_schema:
        try:
            json.loads(payload)
        except json.JSONDecodeError:
            _set_failure("invalid_json")
            return ""
    if not payload:
        _set_failure("empty_output")
        return ""
    return payload


__all__ = [
    "GrokPromptRefused",
    "HERMES_BIN",
    "HERMES_HOME",
    "HERMES_RELEASE",
    "get_last_failure_reason",
    "grok_cli",
]
