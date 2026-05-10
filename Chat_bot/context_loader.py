"""
산적 수다방 - 컨텍스트 로더
━━━━━━━━━━━━━━━━━━━━━━━━━━━
GCP 로컬 레포에서 .md 파일을 읽어 사용자 배경 지식을 구축한다.
"""

import logging
import os
import sys
import time
from pathlib import Path

log = logging.getLogger(__name__)

# GCP에서 클론된 통합 리포 경로
REPO_PATHS = [
    Path.home() / "Sanjuk-Notion-Telegram-Bot",
]

# 읽을 .md 파일 패턴 (너무 큰 파일 제외)
MAX_FILE_SIZE = 50_000  # 50KB
SKIP_DIRS = {".git", "node_modules", "venv", "__pycache__", ".github"}


def _read_md_file(path: Path) -> str | None:
    """md 파일을 읽되, 너무 크면 건너뛴다."""
    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            return None
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def load_md_context() -> str:
    """모든 레포의 .md 파일을 읽어 컨텍스트 문자열을 만든다."""
    sections: list[str] = []

    for repo_path in REPO_PATHS:
        if not repo_path.exists():
            continue

        repo_name = repo_path.name
        md_files: list[tuple[str, str]] = []

        for md_path in repo_path.rglob("*.md"):
            # 불필요한 디렉토리 스킵
            if any(skip in md_path.parts for skip in SKIP_DIRS):
                continue

            content = _read_md_file(md_path)
            if not content:
                continue

            rel_path = md_path.relative_to(repo_path)
            md_files.append((str(rel_path), content.strip()))

        if md_files:
            file_texts = []
            for rel_path, content in md_files[:20]:  # 레포당 최대 20개
                # 내용을 1000자로 요약
                summary = content[:1000]
                if len(content) > 1000:
                    summary += "..."
                file_texts.append(f"[{rel_path}]\n{summary}")

            sections.append(
                f"### {repo_name}\n" + "\n\n".join(file_texts)
            )

    if not sections:
        return ""

    return (
        "## 사용자의 프로젝트/문서 (GitHub 레포에서 읽음)\n\n"
        + "\n\n---\n\n".join(sections)
    )


def load_memory_context() -> str:
    """Claude 메모리 파일을 읽어 사용자 정보를 구축한다."""
    memory_path = Path.home() / "Sanjuk-Notion-Telegram-Bot" / ".claude" / "projects" / "C--dev-Sanjuk-Notion-Telegram-Bot" / "memory"

    if not memory_path.exists():
        return ""

    entries: list[str] = []
    for md_path in sorted(memory_path.glob("*.md")):
        if md_path.name == "MEMORY.md":
            continue
        content = _read_md_file(md_path)
        if not content:
            continue
        # 프론트매터 이후 내용만 추출
        parts = content.split("---", 2)
        body = parts[2].strip() if len(parts) >= 3 else content.strip()
        if body:
            entries.append(f"[{md_path.stem}]\n{body[:500]}")

    if not entries:
        return ""

    return (
        "## 사용자에 대해 알고 있는 정보 (Claude 메모리)\n\n"
        + "\n\n".join(entries[:15])
    )


_cached_context: str | None = None
_cache_timestamp: float = 0
CONTEXT_REFRESH_INTERVAL = 6 * 3600  # 6시간마다 자동 갱신


def load_recent_summaries() -> str:
    """최근 7일간의 수다봇 대화 요약을 읽어 컨텍스트로 반환한다."""
    memory_path = Path.home() / "Sanjuk-Notion-Telegram-Bot" / ".claude" / "projects" / "C--dev-Sanjuk-Notion-Telegram-Bot" / "memory"
    if not memory_path.exists():
        return ""

    summary_files = sorted(memory_path.glob("chat_*.md"), reverse=True)[:7]
    if not summary_files:
        return ""

    entries: list[str] = []
    for f in summary_files:
        content = _read_md_file(f)
        if not content:
            continue
        parts = content.split("---", 2)
        body = parts[2].strip() if len(parts) >= 3 else content.strip()
        if body and body != "새로운 정보 없음":
            entries.append(f"[{f.stem}]\n{body[:300]}")

    if not entries:
        return ""

    return (
        "## 최근 대화 요약 (지난 대화에서 알게 된 것)\n\n"
        + "\n\n".join(entries)
    )


def load_calendar_context() -> str:
    """Google Calendar에서 오늘+이번 주 일정을 로딩한다."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from google_calendar import get_calendar_context
        return get_calendar_context("week")
    except Exception as e:
        log.debug("캘린더 로딩 실패 (무시): %s", e)
        return ""


def load_todo_context() -> str:
    """할일 목록을 로딩한다."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from todo_manager import get_todo_context
        return get_todo_context()
    except Exception as e:
        log.debug("할일 로딩 실패 (무시): %s", e)
        return ""


def load_gcp_context() -> str:
    """GCP VM 시스템 상태를 로딩한다."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from gcp_status import get_gcp_context
        return get_gcp_context()
    except Exception as e:
        log.debug("GCP 상태 로딩 실패 (무시): %s", e)
        return ""


def get_full_context() -> str:
    """전체 컨텍스트를 캐시하여 반환한다 (6시간마다 자동 갱신)."""
    global _cached_context, _cache_timestamp

    now = time.time()
    if _cached_context is not None and (now - _cache_timestamp) < CONTEXT_REFRESH_INTERVAL:
        return _cached_context

    log.info("컨텍스트 로딩 시작...")
    memory = load_memory_context()
    summaries = load_recent_summaries()
    md_docs = load_md_context()
    calendar = load_calendar_context()
    gcp = load_gcp_context()
    todo = load_todo_context()

    parts = [p for p in [memory, summaries, calendar, gcp, todo, md_docs] if p]
    _cached_context = "\n\n".join(parts) if parts else ""
    _cache_timestamp = now

    if _cached_context:
        log.info("컨텍스트 로딩 완료: %d자", len(_cached_context))
    else:
        log.info("로딩된 컨텍스트 없음")

    return _cached_context


def refresh_context() -> str:
    """컨텍스트를 강제로 다시 로딩한다."""
    global _cached_context, _cache_timestamp
    _cached_context = None
    _cache_timestamp = 0
    return get_full_context()
