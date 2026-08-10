"""Bounded OAuth Codex adapter for sanitized public persona analysis."""
from __future__ import annotations

import contextvars
import json
import os
import re
import signal
import subprocess
import tempfile
from pathlib import Path

_CODEX_BIN = Path("/home/kanzaka110/.local/bin/codex")
_CODEX_HOME = Path("/home/kanzaka110/.codex")
_ALLOWED_MODEL = "gpt-5.6-sol"
_LAST_FAILURE: contextvars.ContextVar[str] = contextvars.ContextVar(
    "codex_cli_last_failure", default=""
)
_SENSITIVE = re.compile(
    r"계좌|예수금|보유\s*(?:종목|수량|상태)?|포트폴리오|평단|주문|실거래|"
    r"자동\s*(?:매매|거래)|브로커|broker|account(?:_id)?|holdings?|"
    r"cost[_ -]?basis|cash[_ -]?balance|credential|api[_ -]?key|token|secret",
    re.IGNORECASE,
)


class CodexPromptRefused(ValueError):
    pass


def get_last_failure_reason() -> str:
    return _LAST_FAILURE.get()


def _set_failure(reason: str) -> None:
    _LAST_FAILURE.set(reason)


def _safe_env() -> dict[str, str]:
    return {
        "HOME": "/home/kanzaka110",
        "CODEX_HOME": str(_CODEX_HOME),
        "PATH": "/home/kanzaka110/.local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def codex_cli(
    prompt: str,
    *,
    model: str = _ALLOWED_MODEL,
    timeout: int = 300,
    effort: str = "none",
    system_prompt: str | None = None,
    json_schema: str | None = None,
    **_kwargs: object,
) -> str:
    """Run one sanitized persona call without inheriting service secrets."""
    del effort
    _set_failure("")
    combined = f"{system_prompt or ''}\n\nPUBLIC BRIEFING DATA:\n{prompt}".strip()
    if model != _ALLOWED_MODEL:
        _set_failure("model_not_allowed")
        return ""
    try:
        from briefing_model_router import assert_public_content
        assert_public_content(prompt)
    except ValueError as exc:
        _set_failure("sensitive_prompt")
        raise CodexPromptRefused("sensitive_prompt") from exc
    if not _CODEX_BIN.is_file() or not os.access(_CODEX_BIN, os.X_OK):
        _set_failure("binary_unavailable")
        return ""

    with tempfile.TemporaryDirectory(prefix="sanjuk-codex-public-") as tmp:
        workdir = Path(tmp)
        output_path = workdir / "last-message.txt"
        command = [
            str(_CODEX_BIN), "exec", "--sandbox", "read-only",
            "--skip-git-repo-check", "--ignore-user-config",
            "-C", str(workdir), "-m", model,
            "--output-last-message", str(output_path),
        ]
        if json_schema:
            schema_path = workdir / "response-schema.json"
            schema_path.write_text(json_schema, encoding="utf-8")
            command.extend(["--output-schema", str(schema_path)])
        command.append("-")

        proc: subprocess.Popen[str] | None = None
        try:
            proc = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=_safe_env(),
                start_new_session=True,
            )
            proc.communicate(input=combined, timeout=max(1, int(timeout)))
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
            _set_failure("spawn_error")
            return ""

        if proc.returncode != 0:
            _set_failure("provider_error")
            return ""
        try:
            text = output_path.read_text(encoding="utf-8").strip()
        except OSError:
            text = ""
        if not text:
            _set_failure("empty_output")
            return ""
        if json_schema:
            try:
                json.loads(text)
            except json.JSONDecodeError:
                _set_failure("invalid_json")
                return ""
        _set_failure("")
        return text
