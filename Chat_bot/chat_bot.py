"""
텔레그램 챗봇 — 산적 수다방 / Sanjuk_Talk_bot
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Gemini 하이브리드(Flash/Pro) 수다 봇.
매일 23시 대화 요약 → GitHub memory/ push → Claude Code 메모리 누적.
매일 12시 선제적 연락 (메모리 기반).

환경변수:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY,
  GITHUB_TOKEN, GITHUB_REPO
"""

import asyncio
import logging
import re
from datetime import time as dt_time

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

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
    run_daily_summary,
    run_weekly_consolidation,
    summarize_segment,
)
from vector_memory import (
    format_core_memory,
    format_memory_context,
    get_core_memory,
    init_vector_db,
    save_segment,
    search_memory,
    store_memory,
    update_core_memory,
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
        "/deep - Pro 모드\n"
        "/casual - Flash 모드\n"
        "/status - 상태\n"
        "/clear - 대화 초기화\n"
        "/summary - 오늘 요약\n"
        "/help - 도움말"
    )


async def cmd_deep(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pro 모드로 전환."""
    if not _is_allowed(update):
        return
    success, message = gemini.switch_to_pro()
    await update.message.reply_text(message)


async def cmd_casual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Flash 모드로 복귀."""
    if not _is_allowed(update):
        return
    message = gemini.switch_to_flash()
    await update.message.reply_text(message)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """현재 상태 표시."""
    if not _is_allowed(update):
        return
    status = gemini.get_status()
    stats = await get_daily_stats(update.effective_chat.id)
    await update.message.reply_text(
        f"산적 수다방 상태\n\n"
        f"{status}\n"
        f"오늘 대화: {stats['total']}건 "
        f"(Flash {stats['flash']} / Pro {stats['pro']})"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """대화 컨텍스트 초기화 (DB 데이터는 유지)."""
    if not _is_allowed(update):
        return
    # 컨텍스트 초기화는 다음 대화에서 recent_messages를 0으로 시작
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


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """도움말."""
    if not _is_allowed(update):
        return
    await update.message.reply_text(
        "산적 수다방 도움말\n\n"
        "/deep - Pro 모드\n"
        "/casual - Flash 모드\n"
        "/status - 상태\n"
        "/clear - 대화 초기화\n"
        "/summary - 오늘 요약\n"
        "/refresh - 컨텍스트 새로고침\n"
        "/help - 도움말"
    )


# ─── 멀티 버블 응답 ────────────────────────────────────
def _split_into_bubbles(text: str) -> list[str]:
    """응답을 2-3개 자연스러운 메시지 버블로 분리한다.

    짧은 응답(100자 이하)은 그대로, 긴 응답은 문단이나 줄바꿈 기준으로 나눈다.
    """
    text = text.strip()

    # 짧은 응답은 분리하지 않음
    if len(text) <= 100:
        return [text]

    # 빈 줄(문단 구분)로 먼저 분리 시도
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if 2 <= len(paragraphs) <= 4:
        return paragraphs

    # 문단 구분이 없으면 줄바꿈으로 분리
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) >= 3:
        # 2-3 그룹으로 묶기
        chunk_size = max(1, len(lines) // 3)
        bubbles = []
        for i in range(0, len(lines), chunk_size):
            chunk = "\n".join(lines[i : i + chunk_size])
            if chunk:
                bubbles.append(chunk)
        return bubbles[:3]

    # 분리가 안 되면 그대로
    return [text]


async def _send_bubbles(message, bubbles: list[str]) -> None:
    """버블들을 짧은 딜레이와 함께 순차 전송한다."""
    for i, bubble in enumerate(bubbles):
        if len(bubble) > 4000:
            for j in range(0, len(bubble), 4000):
                await message.reply_text(bubble[j : j + 4000])
        else:
            await message.reply_text(bubble)
        # 마지막 버블이 아니면 타이핑 효과 + 딜레이
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

    from datetime import datetime
    now = datetime.now(KST)
    gap = (now - last_msg.created_at).total_seconds()

    if gap < SEGMENT_GAP_SECONDS:
        return  # 아직 대화가 이어지는 중

    # 마지막 세그먼트 이후 메시지들 조회
    from datetime import timedelta
    segment_start = now - timedelta(seconds=gap + 3600)  # 공백 전 1시간 범위
    recent = await get_messages_since(chat_id, segment_start)

    if len(recent) < 3:
        return  # 대화가 너무 짧음

    summary = await summarize_segment(recent)
    if summary:
        await save_segment(chat_id, summary, len(recent))
        log.info("대화 세그먼트 저장: %d건 → %s", len(recent), summary[:50])


# ─── 메시지 핸들러 ──────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """일반 텍스트 메시지 처리."""
    if not _is_allowed(update):
        return
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text
    model_name = "pro" if gemini.state.current_model.endswith("pro") else "flash"

    # 0. 세그먼트 감지 (30분 공백 후 첫 메시지인지)
    await _check_and_save_segment(chat_id)

    # 1. 사용자 메시지 저장
    await save_message(chat_id, "user", user_text, model_name)

    # 2. 벡터 메모리에 저장 (백그라운드)
    asyncio.create_task(store_memory(chat_id, user_text))

    # 3. 최근 대화 조회 (컨텍스트)
    if context.user_data.get("clear_context"):
        recent = []
        context.user_data["clear_context"] = False
    else:
        recent = await get_recent_messages(chat_id, limit=20)

    # 4. 벡터 메모리 검색 (관련 과거 대화)
    memories = await search_memory(chat_id, user_text, top_k=3)
    memory_ctx = format_memory_context(memories)

    # 5. 코어 메모리 로딩
    core = await get_core_memory(chat_id)
    core_ctx = format_core_memory(core)

    # 6. Gemini 응답 생성
    answer, fallback_notice = await gemini.ask(
        user_text, recent,
        memory_context=memory_ctx,
        core_memory_context=core_ctx,
    )

    # 7. 폴백 알림이 있으면 먼저 전송
    if fallback_notice:
        await update.message.reply_text(fallback_notice)

    # 8. 응답 저장
    await save_message(chat_id, "assistant", answer, model_name)

    # 9. 멀티 버블 전송
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
    """매일 선제적 연락 — 메모리 기반으로 먼저 말 걸기.

    유저 활동 패턴에 맞춰 타이밍 조정 (기본 12시).
    2일 이상 대화 없으면 "요즘 바빠?" 스타일로 연락.
    """
    if ALLOWED_CHAT_ID == 0:
        return
    log.info("선제적 연락 생성 시작")
    try:
        # 마지막 대화 시간 확인
        last_msg = await get_last_message(ALLOWED_CHAT_ID)
        if last_msg:
            from datetime import datetime
            gap_hours = (datetime.now(KST) - last_msg.created_at).total_seconds() / 3600
            if gap_hours > 48:
                # 2일 이상 대화 없으면 가벼운 안부
                message = "요즘 바빠? 뜸하네"
                await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=message)
                await save_message(ALLOWED_CHAT_ID, "assistant", message, "flash")
                log.info("침묵 기반 연락 전송")
                return

        message = await generate_checkin_message()
        if message and message.strip().upper() != "SKIP":
            await context.bot.send_message(
                chat_id=ALLOWED_CHAT_ID,
                text=message,
            )
            await save_message(ALLOWED_CHAT_ID, "assistant", message, "flash")
            log.info("선제적 연락 전송: %s", message[:50])
        else:
            log.info("선제적 연락 스킵 (할 말 없음)")
    except Exception as e:
        log.error("선제적 연락 실패: %s", e)


async def scheduled_consolidation(context: ContextTypes.DEFAULT_TYPE) -> None:
    """매주 일요일 23:30 KST — 주간 기억 통합."""
    log.info("주간 기억 통합 시작")
    try:
        entries = await run_weekly_consolidation(ALLOWED_CHAT_ID)
        if entries:
            for entry in entries:
                await update_core_memory(
                    ALLOWED_CHAT_ID,
                    entry["category"],
                    entry["content"],
                )
            log.info("코어 메모리 %d건 업데이트", len(entries))
        else:
            log.info("주간 통합: 새로운 패턴 없음")
    except Exception as e:
        log.error("주간 기억 통합 실패: %s", e)


# ─── 메인 ───────────────────────────────────────────────
async def post_init(application) -> None:
    """봇 시작 시 DB 초기화 + 벡터 DB 초기화 + 컨텍스트 로딩."""
    await init_db()
    await init_vector_db()
    log.info("데이터베이스 초기화 완료 (대화 + 벡터 메모리)")
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
    app.add_handler(CommandHandler("deep", cmd_deep))
    app.add_handler(CommandHandler("casual", cmd_casual))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CommandHandler("help", cmd_help))

    # 일반 메시지
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 매일 23:00 KST — 대화 요약 + GitHub push
    app.job_queue.run_daily(
        scheduled_summary,
        time=dt_time(hour=23, minute=0, tzinfo=KST),
        name="daily_summary",
    )

    # 매일 12:00 KST — 선제적 연락 (메모리 기반)
    app.job_queue.run_daily(
        scheduled_checkin,
        time=dt_time(hour=12, minute=0, tzinfo=KST),
        name="daily_checkin",
    )

    # 매주 일요일 23:30 KST — 주간 기억 통합
    app.job_queue.run_daily(
        scheduled_consolidation,
        time=dt_time(hour=23, minute=30, tzinfo=KST),
        days=(6,),  # 일요일만
        name="weekly_consolidation",
    )

    log.info("산적 수다방 봇 시작! (모델: %s)", gemini.state.current_model)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
