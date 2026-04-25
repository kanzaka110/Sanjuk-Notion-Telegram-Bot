"""
텔레그램 챗봇 — 산적 수다방 / Sanjuk_Talk_bot
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Claude CLI 기반 수다 봇 (API 비용 $0).
매일 23시 대화 요약 → GitHub memory/ push → Claude Code 메모리 누적.
매일 12시 선제적 연락 (메모리 기반).

환경변수:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
  GITHUB_TOKEN, GITHUB_REPO
"""

import asyncio
import logging
import re
import sys
from datetime import time as dt_time
from pathlib import Path

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# 음성 메시지 처리
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from voice_handler import handle_voice_message
from todo_manager import add_todo, complete_todo, delete_todo, get_pending_todos, format_todo_list, get_todo_context
from expense_tracker import add_expense, parse_expense, get_today_expenses, get_month_expenses, get_expense_summary
from photo_handler import handle_photo_message
from web_search import search_web_async
from calendar_writer import parse_and_create_event
from rag_memory import search_memory, store_memory, get_relevant_context, get_memory_stats

from config import ALLOWED_CHAT_ID, KST, TELEGRAM_BOT_TOKEN
from database import (
    get_daily_stats,
    get_last_message,
    get_messages_since,
    get_recent_messages,
    init_db,
    save_message,
)
from context_loader import get_full_context, refresh_context
from gemini_client import GeminiClient
from summarizer import (
    generate_checkin_message,
    generate_daily_digest,
    run_daily_summary,
    run_weekly_consolidation,
    summarize_segment,
)

# ─── 로깅 ───────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ─── 전역 인스턴스 ──────────────────────────────────────
gemini = GeminiClient()


# ─── 권한 체크 ──────────────────────────────────────────
def _is_allowed(update: Update) -> bool:
    """허용된 Chat ID인지 확인한다."""
    if not update.effective_chat:
        return False
    if ALLOWED_CHAT_ID == 0:
        return True
    return update.effective_chat.id == ALLOWED_CHAT_ID


# ─── 명령어 핸들러 ──────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """봇 소개 및 사용법."""
    if not _is_allowed(update):
        return
    await update.message.reply_text(
        "산적 수다방.\n\n"
        "편하게 말 걸어.\n\n"
        "/status - 상태\n"
        "/clear - 대화 초기화\n"
        "/summary - 오늘 요약\n"
        "/help - 도움말"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """현재 상태 표시."""
    if not _is_allowed(update):
        return
    status = gemini.get_status()
    stats = await get_daily_stats(update.effective_chat.id)
    await update.message.reply_text(
        f"산적 수다방 상태\n\n"
        f"{status}\n"
        f"오늘 대화: {stats['total']}건"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """대화 컨텍스트 초기화 (DB 데이터는 유지)."""
    if not _is_allowed(update):
        return
    context.user_data["clear_context"] = True
    await update.message.reply_text("대화 컨텍스트 초기화 완료.")


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """수동으로 오늘 대화 요약을 실행한다."""
    if not _is_allowed(update):
        return
    await update.message.reply_text("오늘 대화 요약 중...")
    await run_daily_summary(update.effective_chat.id)
    await update.message.reply_text("요약 완료. GitHub에 push했어.")


async def cmd_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """컨텍스트 강제 새로고침."""
    if not _is_allowed(update):
        return
    ctx = refresh_context()
    await update.message.reply_text(f"컨텍스트 새로고침 완료. ({len(ctx)}자 로딩)")


async def cmd_todo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """할일 목록 보기."""
    if not _is_allowed(update):
        return
    todos = get_pending_todos()
    await update.message.reply_text(format_todo_list(todos) if todos else "할일 없음")


async def cmd_todo_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """할일 추가. /add 보고서 작성"""
    if not _is_allowed(update):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("사용법: /add 할일 내용")
        return
    item = add_todo(text)
    await update.message.reply_text(f"추가: #{item['id']} {item['text']}")


async def cmd_todo_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """할일 완료. /done 1"""
    if not _is_allowed(update):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("사용법: /done 번호")
        return
    item = complete_todo(int(context.args[0]))
    if item:
        await update.message.reply_text(f"완료: #{item['id']} {item['text']}")
    else:
        await update.message.reply_text("해당 번호 없음")


async def cmd_spend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """지출 기록. /spend 커피 5500"""
    if not _is_allowed(update):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("사용법: /spend 커피 5500")
        return
    parsed = parse_expense(text)
    if not parsed:
        await update.message.reply_text("금액 인식 실패. '커피 5500' 형식으로")
        return
    item = add_expense(parsed["description"], parsed["amount"])
    today = get_today_expenses()
    total = sum(e["amount"] for e in today)
    await update.message.reply_text(
        f"기록: {item['description']} {item['amount']:,}원\n오늘 총 지출: {total:,}원"
    )


async def cmd_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """지출 내역 조회."""
    if not _is_allowed(update):
        return
    arg = context.args[0] if context.args else "today"
    if arg == "month":
        expenses = get_month_expenses()
        header = "이번 달 지출"
    else:
        expenses = get_today_expenses()
        header = "오늘 지출"
    await update.message.reply_text(f"{header}\n{get_expense_summary(expenses)}")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """웹 검색. /search 언리얼 5.6 업데이트"""
    if not _is_allowed(update):
        return
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("사용법: /search 검색어")
        return
    await update.message.chat.send_action("typing")
    result = await search_web_async(query)
    if len(result) > 4000:
        result = result[:4000]
    await update.message.reply_text(result)


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """일정 생성. /schedule 다음 주 화요일 3시 팀 미팅"""
    if not _is_allowed(update):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("사용법: /schedule 다음 주 화요일 3시 팀 미팅")
        return
    await update.message.chat.send_action("typing")
    import asyncio
    event = await asyncio.to_thread(parse_and_create_event, text)
    if event:
        await update.message.reply_text(f"일정 등록 완료: {event['summary']}")
    else:
        await update.message.reply_text("일정 등록 실패. 다시 시도해줘.")


async def cmd_recall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """과거 대화 검색. /recall 투자 전략"""
    if not _is_allowed(update):
        return
    query = " ".join(context.args) if context.args else ""
    if not query:
        stats = get_memory_stats()
        await update.message.reply_text(f"{stats}\n사용법: /recall 검색어")
        return
    memories = search_memory(query, n_results=5)
    if not memories:
        await update.message.reply_text("관련 기억 없음")
        return
    lines = []
    for m in memories:
        lines.append(f"[{m['date']}] {m['text'][:200]}")
    await update.message.reply_text("\n\n".join(lines))


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """사진 메시지 분석."""
    if not _is_allowed(update):
        return
    if not update.message:
        return
    await update.message.chat.send_action("typing")
    caption = update.message.caption or ""
    result = await handle_photo_message(update, context, caption)
    if result:
        # 지출 영수증 감지
        parsed = parse_expense(result)
        if parsed and "영수증" in result.lower() or "원" in result:
            await update.message.reply_text(result)
        else:
            await update.message.reply_text(result)
    else:
        await update.message.reply_text("사진 분석 실패. 다시 보내줘.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """도움말."""
    if not _is_allowed(update):
        return
    await update.message.reply_text(
        "비서봇 도움말\n\n"
        "-- 기본 --\n"
        "/status - 상태\n"
        "/clear - 대화 초기화\n"
        "/refresh - 컨텍스트 새로고침\n\n"
        "-- 할일 --\n"
        "/todo - 할일 목록\n"
        "/add 내용 - 할일 추가\n"
        "/done 번호 - 할일 완료\n\n"
        "-- 지출 --\n"
        "/spend 커피 5500 - 지출 기록\n"
        "/expenses - 오늘 지출\n"
        "/expenses month - 이번 달 지출\n\n"
        "-- 도구 --\n"
        "/search 검색어 - 웹 검색\n"
        "/schedule 일정 - 캘린더 등록\n"
        "/summary - 오늘 대화 요약\n"
        "/recall 키워드 - 과거 대화 검색\n\n"
        "음성/사진도 지원!"
    )


# ─── 멀티 버블 응답 ────────────────────────────────────
def _split_into_bubbles(text: str) -> list[str]:
    """응답을 2-3개 자연스러운 메시지 버블로 분리한다."""
    text = text.strip()

    if len(text) <= 100:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if 2 <= len(paragraphs) <= 4:
        return paragraphs

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) >= 3:
        chunk_size = max(1, len(lines) // 3)
        bubbles = []
        for i in range(0, len(lines), chunk_size):
            chunk = "\n".join(lines[i : i + chunk_size])
            if chunk:
                bubbles.append(chunk)
        return bubbles[:3]

    return [text]


async def _send_bubbles(message, bubbles: list[str]) -> None:
    """버블들을 짧은 딜레이와 함께 순차 전송한다."""
    for i, bubble in enumerate(bubbles):
        if len(bubble) > 4000:
            for j in range(0, len(bubble), 4000):
                await message.reply_text(bubble[j : j + 4000])
        else:
            await message.reply_text(bubble)
        if i < len(bubbles) - 1:
            await message.chat.send_action("typing")
            await asyncio.sleep(0.8)


# ─── 대화 세그먼트 감지 ────────────────────────────────
SEGMENT_GAP_SECONDS = 1800  # 30분

async def _check_and_save_segment(chat_id: int) -> None:
    """30분 이상 공백이 있으면 이전 대화를 세그먼트로 요약 저장한다."""
    last_msg = await get_last_message(chat_id)
    if not last_msg:
        return

    from datetime import datetime, timedelta
    now = datetime.now(KST)
    gap = (now - last_msg.created_at).total_seconds()

    if gap < SEGMENT_GAP_SECONDS:
        return

    segment_start = now - timedelta(seconds=gap + 3600)
    recent = await get_messages_since(chat_id, segment_start)

    if len(recent) < 3:
        return

    summary = await summarize_segment(recent)
    if summary:
        log.info("대화 세그먼트 요약: %d건 → %s", len(recent), summary[:50])


# ─── 메시지 핸들러 ──────────────────────────────────────
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """음성 메시지를 텍스트로 변환 후 처리."""
    if not _is_allowed(update):
        return
    if not update.message:
        return

    await update.message.chat.send_action("typing")
    text = await handle_voice_message(update, context)
    if not text:
        await update.message.reply_text("음성 인식 실패. 다시 보내줘.")
        return

    # 변환된 텍스트 표시 후 대화 처리
    await update.message.reply_text(f"[음성 인식] {text}")

    # 일반 메시지와 동일하게 처리
    chat_id = update.effective_chat.id
    await _check_and_save_segment(chat_id)
    await save_message(chat_id, "user", text, "cli")

    recent = await get_recent_messages(chat_id, limit=20)
    core_ctx = get_full_context()

    answer, _ = await gemini.ask(text, recent, core_memory_context=core_ctx)
    await save_message(chat_id, "assistant", answer, "cli")

    bubbles = _split_into_bubbles(answer)
    await _send_bubbles(update.message, bubbles)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """일반 텍스트 메시지 처리."""
    if not _is_allowed(update):
        return
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text

    # 0. 세그먼트 감지
    await _check_and_save_segment(chat_id)

    # 1. 사용자 메시지 저장
    await save_message(chat_id, "user", user_text, "cli")

    # 2. 최근 대화 조회
    if context.user_data.get("clear_context"):
        recent = []
        context.user_data["clear_context"] = False
    else:
        recent = await get_recent_messages(chat_id, limit=20)

    # 3. 코어 메모리 로딩 (context_loader에서 제공)
    core_ctx = get_full_context()

    # 4. Claude CLI 응답 생성
    answer, fallback_notice = await gemini.ask(
        user_text, recent,
        core_memory_context=core_ctx,
    )

    # 5. 응답 저장
    await save_message(chat_id, "assistant", answer, "cli")

    # 6. 멀티 버블 전송
    bubbles = _split_into_bubbles(answer)
    await _send_bubbles(update.message, bubbles)


# ─── 스케줄러 콜백 ──────────────────────────────────────
async def scheduled_summary(context: ContextTypes.DEFAULT_TYPE) -> None:
    """매일 23시 KST 자동 요약."""
    log.info("스케줄 요약 시작")
    try:
        await run_daily_summary(ALLOWED_CHAT_ID)
        log.info("스케줄 요약 완료")
    except Exception as e:
        log.error("스케줄 요약 실패: %s", e)


async def scheduled_checkin(context: ContextTypes.DEFAULT_TYPE) -> None:
    """매일 선제적 연락 — 메모리 기반으로 먼저 말 걸기."""
    if ALLOWED_CHAT_ID == 0:
        return
    log.info("선제적 연락 생성 시작")
    try:
        last_msg = await get_last_message(ALLOWED_CHAT_ID)
        if last_msg:
            from datetime import datetime
            gap_hours = (datetime.now(KST) - last_msg.created_at).total_seconds() / 3600
            if gap_hours > 48:
                message = "요즘 바빠? 뜸하네"
                await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=message)
                await save_message(ALLOWED_CHAT_ID, "assistant", message, "cli")
                log.info("침묵 기반 연락 전송")
                return

        message = await generate_checkin_message()
        if message and message.strip().upper() != "SKIP":
            await context.bot.send_message(
                chat_id=ALLOWED_CHAT_ID,
                text=message,
            )
            await save_message(ALLOWED_CHAT_ID, "assistant", message, "cli")
            log.info("선제적 연락 전송: %s", message[:50])
        else:
            log.info("선제적 연락 스킵 (할 말 없음)")
    except Exception as e:
        log.error("선제적 연락 실패: %s", e)


async def scheduled_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    """매일 21시 KST — 일일 다이제스트 전송."""
    if ALLOWED_CHAT_ID == 0:
        return
    log.info("일일 다이제스트 생성 시작")
    try:
        digest = await generate_daily_digest()
        if digest:
            await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=digest)
            await save_message(ALLOWED_CHAT_ID, "assistant", digest, "cli")
            log.info("일일 다이제스트 전송 완료")
        else:
            log.info("다이제스트 생성 스킵 (내용 없음)")
    except Exception as e:
        log.error("일일 다이제스트 실패: %s", e)


async def scheduled_consolidation(context: ContextTypes.DEFAULT_TYPE) -> None:
    """매주 일요일 23:30 KST — 주간 기억 통합."""
    log.info("주간 기억 통합 시작")
    try:
        entries = await run_weekly_consolidation(ALLOWED_CHAT_ID)
        if entries:
            log.info("코어 메모리 %d건 업데이트 (요약만 로깅)", len(entries))
        else:
            log.info("주간 통합: 새로운 패턴 없음")
    except Exception as e:
        log.error("주간 기억 통합 실패: %s", e)


# ─── 메인 ───────────────────────────────────────────────
async def post_init(application) -> None:
    """봇 시작 시 DB 초기화 + 컨텍스트 로딩."""
    await init_db()
    log.info("데이터베이스 초기화 완료")
    ctx = get_full_context()
    if ctx:
        log.info("사용자 컨텍스트 로딩 완료: %d자", len(ctx))


def main() -> None:
    """봇 엔트리포인트."""
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # 명령어 등록
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("todo", cmd_todo))
    app.add_handler(CommandHandler("add", cmd_todo_add))
    app.add_handler(CommandHandler("done", cmd_todo_done))
    app.add_handler(CommandHandler("spend", cmd_spend))
    app.add_handler(CommandHandler("expenses", cmd_expenses))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("recall", cmd_recall))

    # 일반 메시지
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 음성 메시지
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    # 사진 메시지
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # 매일 23:00 KST — 대화 요약 + GitHub push
    app.job_queue.run_daily(
        scheduled_summary,
        time=dt_time(hour=23, minute=0, tzinfo=KST),
        name="daily_summary",
    )

    # 매일 12:00 KST — 선제적 연락
    app.job_queue.run_daily(
        scheduled_checkin,
        time=dt_time(hour=12, minute=0, tzinfo=KST),
        name="daily_checkin",
    )

    # 매일 21:00 KST — 일일 다이제스트
    app.job_queue.run_daily(
        scheduled_digest,
        time=dt_time(hour=21, minute=0, tzinfo=KST),
        name="daily_digest",
    )

    # 매주 일요일 23:30 KST — 주간 기억 통합
    app.job_queue.run_daily(
        scheduled_consolidation,
        time=dt_time(hour=23, minute=30, tzinfo=KST),
        days=(6,),
        name="weekly_consolidation",
    )

    log.info("산적 수다방 봇 시작! (Claude CLI)")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
