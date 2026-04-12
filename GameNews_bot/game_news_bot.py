"""
텔레그램 챗봇 — 게임뉴스 비서 (Claude CLI)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
게임 관련 질문 시 Claude CLI + WebSearch로 실시간 검색 후 답변.
API 비용 $0.

환경변수:
  GAME_NEWS_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import os
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# shared_config에서 Claude CLI 유틸리티 로드
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared_config import claude_cli

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ─── 설정 ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["GAME_NEWS_BOT_TOKEN"]
ALLOWED_CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))
KST = timezone(timedelta(hours=9))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# 대화 히스토리
chat_history: dict[int, list[str]] = {}
MAX_HISTORY = 10

SYSTEM_PROMPT = """당신은 '게임뉴스 비서' — 게임 업계 최신 뉴스와 트렌드 전문가입니다. 한국어로 대화합니다.

## 전문 분야
PC/콘솔/모바일 게임 뉴스, 게임 리뷰, 출시 일정, 업데이트 정보,
e스포츠, 게임 개발 트렌드, 인디 게임, AAA 타이틀

## 역할
- 최신 게임 뉴스와 업데이트 정보를 정확하게 전달
- 게임 관련 질문에 구체적이고 신뢰할 수 있는 답변 제공
- 출시 예정 게임, 패치 노트, 이벤트 정보 안내
- 게임 추천, 비교 분석, 팁 제공

## 답변 스타일
- 텔레그램 메시지에 맞게 간결하되 핵심은 빠짐없이
- 관련 뉴스 소스가 있으면 함께 제공
- 이모지를 적절히 사용하여 가독성 향상

## 가장 중요한 규칙
- 모르는 건 지어내지 마
- URL은 실제 검색에서 확인된 것만 제공해"""


# ─── 권한 체크 ─────────────────────────────────────────
def is_authorized(chat_id: int) -> bool:
    if ALLOWED_CHAT_ID == 0:
        return True
    return chat_id == ALLOWED_CHAT_ID


# ─── Claude CLI 응답 생성 ────────────────────────────
def ask_claude(chat_id: int, user_message: str) -> str:
    history = chat_history.get(chat_id, [])
    history.append(f"사용자: {user_message}")
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    # 게임 관련 키워드 감지
    game_keywords = [
        "게임", "game", "스팀", "steam", "플스", "playstation", "ps5",
        "엑박", "xbox", "닌텐도", "nintendo", "스위치", "switch",
        "출시", "release", "패치", "patch", "업데이트", "update",
        "리뷰", "review", "공략", "guide", "팁", "tip",
        "e스포츠", "esports", "lol", "롤", "발로란트", "valorant",
        "오버워치", "overwatch", "배그", "pubg", "포트나이트", "fortnite",
        "디아블로", "diablo", "엘든링", "elden ring", "젤다", "zelda",
        "GTA", "마인크래프트", "minecraft", "원신", "genshin",
        "인디", "indie", "AAA", "DLC", "시즌", "season",
        "트레일러", "trailer", "발매", "런칭", "launch",
        "할인", "sale", "무료", "free", "에픽", "epic",
    ]
    is_game = any(kw.lower() in user_message.lower() for kw in game_keywords)

    context = "\n".join(history)
    prompt = f"""대화 기록:
{context}

위 대화의 마지막 사용자 메시지에 답변해주세요."""

    try:
        assistant_msg = claude_cli(
            prompt,
            model="sonnet",
            system_prompt=SYSTEM_PROMPT,
            web_search=is_game,
            timeout=60,
        )

        if not assistant_msg:
            return "응답을 받지 못했습니다. 다시 시도해주세요."

        history.append(f"AI: {assistant_msg}")
        chat_history[chat_id] = history
        return assistant_msg

    except Exception as e:
        log.error("Claude CLI 오류: %s", e)
        return f"오류가 발생했습니다: {e}"


# ─── 핸들러 ───────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.reply_text(
        "🎮 게임뉴스 비서입니다!\n\n"
        "게임 관련 질문이나 수다 편하게 해주세요.\n\n"
        "기능:\n"
        "• 최신 게임 뉴스/업데이트 정보\n"
        "• 게임 리뷰/추천/비교\n"
        "• 출시 일정/이벤트 안내\n"
        "• e스포츠 소식\n\n"
        "/clear — 대화 기록 초기화\n"
        "/help — 도움말"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    chat_history.pop(update.effective_chat.id, None)
    await update.message.reply_text("대화 기록이 초기화되었습니다.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.reply_text(
        "🎮 게임뉴스 비서 도움말\n\n"
        "아무 게임 관련 질문이나 해주세요!\n\n"
        "/start — 봇 시작\n"
        "/clear — 대화 기록 초기화\n"
        "/help — 이 도움말\n\n"
        "게임 관련 질문 시 자동으로 최신 뉴스를 검색합니다."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if not is_authorized(update.effective_chat.id):
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text
    log.info("[%s] 수신: %s", chat_id, user_text[:50])

    await update.message.chat.send_action("typing")

    reply = ask_claude(chat_id, user_text)

    if len(reply) > 4000:
        for i in range(0, len(reply), 4000):
            await update.message.reply_text(reply[i : i + 4000])
    else:
        await update.message.reply_text(reply)

    log.info("[%s] 응답: %s", chat_id, reply[:50])


# ─── 메인 ─────────────────────────────────────────────
def main():
    now = datetime.now(KST)
    log.info("🎮 게임뉴스 비서 시작 — %s", now.strftime("%Y-%m-%d %H:%M:%S KST"))
    log.info("Claude CLI + WebSearch 모드")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("폴링 시작...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
