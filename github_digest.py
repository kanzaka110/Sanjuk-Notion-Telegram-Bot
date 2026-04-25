"""
GitHub 활동 다이제스트 — 오늘 커밋/PR 요약
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

REPOS = [
    Path.home() / "Sanjuk-Notion-Telegram-Bot",
    Path.home() / "Sanjuk-Stock-Simulator",
    Path.home() / "Sanjuk-Unreal",
    Path.home() / "3dsmax-mcp",
    Path.home() / "Sanjuk-Claude-Code",
]


def _run(cmd: str, cwd: str = None, timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_today_commits() -> dict[str, list[str]]:
    """각 repo의 오늘 커밋 목록."""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    result = {}
    for repo in REPOS:
        if not repo.exists():
            continue
        name = repo.name
        log_output = _run(
            f'git log --since="{today} 00:00" --format="%h %s" --all',
            cwd=str(repo),
        )
        if log_output:
            result[name] = log_output.strip().split("\n")
    return result


def get_github_digest() -> str:
    """GitHub 활동 다이제스트 텍스트."""
    commits = get_today_commits()
    if not commits:
        return ""

    lines = ["[GitHub 오늘 활동]"]
    total = 0
    for repo, msgs in commits.items():
        lines.append(f"\n{repo} ({len(msgs)}건):")
        for msg in msgs[:5]:
            lines.append(f"  - {msg}")
        total += len(msgs)

    lines.insert(1, f"총 {total}건 커밋")
    return "\n".join(lines)
