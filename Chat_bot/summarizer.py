"""
산적 수다방 - 매일 요약 + GitHub Push
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
매일 23시 KST에 하루 대화를 요약하고 GitHub memory/ 에 push.
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from github import Github, GithubException

# shared_config에서 Claude CLI 유틸리티 로드
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared_config import claude_cli

from config import (
    CHECKIN_PROMPT,
    CONSOLIDATION_PROMPT,
    DIGEST_PROMPT,
    GITHUB_REPO,
    GITHUB_TOKEN,
    KST,
    MEMORY_PATH,
    SEGMENT_SUMMARY_PROMPT,
    SUMMARY_PROMPT,
)
from context_loader import load_recent_summaries
from database import Message, get_today_messages

log = logging.getLogger(__name__)


def _format_conversation(messages: list[Message]) -> str:
    """대화 메시지를 텍스트로 포맷한다."""
    lines: list[str] = []
    for msg in messages:
        speaker = "사용자" if msg.role == "user" else "봇"
        lines.append(f"{speaker}: {msg.content}")
    return "\n".join(lines)


async def summarize_messages(messages: list[Message]) -> str | None:
    """대화를 Claude CLI로 요약한다."""
    if not messages:
        return None

    conversation_text = _format_conversation(messages)
    prompt = f"{SUMMARY_PROMPT}\n\n---\n\n{conversation_text}"

    try:
        result = await asyncio.to_thread(
            claude_cli, prompt, model="sonnet", timeout=60,
        )
        return result or None
    except Exception as e:
        log.error("요약 생성 실패: %s", e)
        return None


def create_memory_markdown(target_date: datetime, summary: str) -> str:
    """Claude Code 메모리 형식의 마크다운을 생성한다."""
    date_str = target_date.strftime("%Y-%m-%d")
    return (
        f"---\n"
        f"name: 수다봇 대화 요약 {date_str}\n"
        f"description: 텔레그램 수다봇에서 추출한 사용자 정보 ({date_str})\n"
        f"type: user\n"
        f"---\n\n"
        f"## {date_str} 대화 요약\n\n"
        f"{summary}\n"
    )


def push_to_github(file_path: str, content: str, commit_message: str) -> bool:
    """GitHub에 파일을 생성/업데이트한다."""
    if not GITHUB_TOKEN:
        log.warning("GITHUB_TOKEN이 설정되지 않아 push를 건너뜁니다.")
        return False

    try:
        gh = Github(GITHUB_TOKEN)
        repo = gh.get_repo(GITHUB_REPO)

        try:
            existing = repo.get_contents(file_path)
            repo.update_file(
                path=file_path,
                message=commit_message,
                content=content,
                sha=existing.sha,
            )
            log.info("GitHub 파일 업데이트: %s", file_path)
        except GithubException as e:
            if e.status == 404:
                repo.create_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                )
                log.info("GitHub 파일 생성: %s", file_path)
            else:
                raise

        return True
    except Exception as e:
        log.error("GitHub push 실패: %s", e)
        return False


def update_memory_index(target_date: datetime, summary_title: str) -> bool:
    """MEMORY.md 인덱스에 항목을 추가한다."""
    if not GITHUB_TOKEN:
        return False

    date_str = target_date.strftime("%Y-%m-%d")
    filename = f"chat_{date_str}.md"
    new_entry = f"- [수다봇 {date_str}]({filename}) -- {summary_title}"

    try:
        gh = Github(GITHUB_TOKEN)
        repo = gh.get_repo(GITHUB_REPO)
        index_path = f"{MEMORY_PATH}/MEMORY.md"

        try:
            index_file = repo.get_contents(index_path)
            current_content = index_file.decoded_content.decode("utf-8")

            if date_str in current_content:
                log.info("MEMORY.md에 %s 항목이 이미 존재합니다.", date_str)
                return True

            updated_content = current_content.rstrip() + "\n" + new_entry + "\n"
            repo.update_file(
                path=index_path,
                message=f"docs: 수다봇 메모리 인덱스 업데이트 ({date_str})",
                content=updated_content,
                sha=index_file.sha,
            )
        except GithubException as e:
            if e.status == 404:
                log.warning("MEMORY.md를 찾을 수 없습니다: %s", index_path)
                return False
            raise

        log.info("MEMORY.md 인덱스 업데이트 완료: %s", date_str)
        return True
    except Exception as e:
        log.error("MEMORY.md 업데이트 실패: %s", e)
        return False


async def summarize_segment(messages: list[Message]) -> str | None:
    """대화 세그먼트를 짧게 요약한다."""
    if not messages or len(messages) < 3:
        return None

    conversation_text = _format_conversation(messages)
    prompt = f"{SEGMENT_SUMMARY_PROMPT}\n\n---\n\n{conversation_text}"

    try:
        result = await asyncio.to_thread(
            claude_cli, prompt, model="sonnet", timeout=60,
        )
        return result or None
    except Exception as e:
        log.error("세그먼트 요약 실패: %s", e)
        return None


async def run_weekly_consolidation(chat_id: int) -> list[dict] | None:
    """주간 기억 통합: 반복 패턴 추출 → 코어 메모리 업데이트."""
    summaries = load_recent_summaries()
    if not summaries:
        return None

    prompt = f"{CONSOLIDATION_PROMPT}\n\n---\n\n{summaries}"

    try:
        result_text = await asyncio.to_thread(
            claude_cli, prompt, model="sonnet", timeout=60,
        )
        if not result_text or "변화 없음" in result_text:
            return None

        entries = []
        for line in result_text.strip().split("\n"):
            line = line.strip("- ")
            if ":" in line:
                parts = line.split(":", 1)
                category = parts[0].strip().lower()
                content = parts[1].strip() if len(parts) > 1 else ""
                if category in ("fact", "preference", "opinion", "plan", "mood") and content:
                    entries.append({"category": category, "content": content})
        return entries if entries else None

    except Exception as e:
        log.error("주간 기억 통합 실패: %s", e)
        return None


async def generate_daily_digest() -> str | None:
    """일일 다이제스트를 생성한다 (캘린더 + 할일 + GCP + 대화 요약)."""
    parts = []

    # 캘린더
    try:
        from google_calendar import get_calendar_context
        cal = get_calendar_context("today")
        if cal:
            parts.append(cal)
    except Exception:
        pass

    # 내일 캘린더
    try:
        from google_calendar import get_today_schedule
        from datetime import datetime, timedelta
        # 내일 일정은 get_calendar_context에 없으므로 별도 조회
        parts.append("[내일 일정은 내일 아침 브리핑에서 확인]")
    except Exception:
        pass

    # 할일
    try:
        from todo_manager import get_todo_context
        todo = get_todo_context()
        if todo:
            parts.append(todo)
    except Exception:
        pass

    # GCP 상태
    try:
        from gcp_status import get_gcp_context
        gcp = get_gcp_context()
        if gcp:
            parts.append(gcp)
    except Exception:
        pass

    # 대화 요약
    summaries = load_recent_summaries()
    if summaries:
        parts.append(f"[오늘 대화]\n{summaries[:500]}")

    if not parts:
        return None

    context = "\n\n".join(parts)
    prompt = f"{DIGEST_PROMPT}\n\n---\n\n{context}"

    try:
        result = await asyncio.to_thread(
            claude_cli, prompt, model="sonnet", timeout=60,
        )
        return result if result else None
    except Exception as e:
        log.error("다이제스트 생성 실패: %s", e)
        return None


async def generate_checkin_message() -> str | None:
    """최근 대화 요약 + 캘린더 일정을 기반으로 선제적 연락 메시지를 생성한다."""
    summaries = load_recent_summaries()

    # 캘린더 일정 로딩
    calendar_ctx = ""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from google_calendar import get_calendar_context
        calendar_ctx = get_calendar_context("today")
    except Exception:
        pass

    context_parts = []
    if summaries:
        context_parts.append(f"[최근 대화 요약]\n{summaries}")
    if calendar_ctx:
        context_parts.append(f"\n{calendar_ctx}")

    if not context_parts:
        return None

    prompt = f"{CHECKIN_PROMPT}\n\n---\n\n" + "\n".join(context_parts)

    try:
        result = await asyncio.to_thread(
            claude_cli, prompt, model="sonnet", timeout=60,
        )
        if result and result.strip().upper() != "SKIP":
            return result.strip()
        return None
    except Exception as e:
        log.error("선제적 연락 생성 실패: %s", e)
        return None


async def run_daily_summary(chat_id: int) -> None:
    """매일 23시 실행: 요약 → md 생성 → GitHub push."""
    now = datetime.now(KST)
    date_str = now.strftime("%Y-%m-%d")
    log.info("일일 요약 시작: %s", date_str)

    messages = await get_today_messages(chat_id)
    if not messages:
        log.info("오늘 대화가 없어 요약을 건너뜁니다.")
        return

    user_messages = [m for m in messages if m.role == "user"]
    log.info("오늘 대화 %d건 (사용자 %d건)", len(messages), len(user_messages))

    summary = await summarize_messages(messages)
    if not summary:
        log.warning("요약 생성 실패, push를 건너뜁니다.")
        return

    markdown = create_memory_markdown(now, summary)

    file_path = f"{MEMORY_PATH}/chat_{date_str}.md"
    commit_msg = f"docs: 수다봇 대화 요약 ({date_str})"
    pushed = push_to_github(file_path, markdown, commit_msg)

    if not pushed:
        log.warning("GitHub push 실패")
        return

    summary_first_line = summary.split("\n")[0][:80]
    update_memory_index(now, summary_first_line)

    # RAG 벡터 DB에도 저장
    try:
        from rag_memory import store_memory
        store_memory(summary, {"source": "daily_summary", "date": date_str})
        log.info("RAG 메모리 저장 완료")
    except Exception as e:
        log.debug("RAG 저장 실패 (무시): %s", e)

    log.info("일일 요약 완료: %s", date_str)
