"""
텔레그램 챗봇 — 게임뉴스 비서 (Gemini API)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
게임 관련 질문 시 실시간 검색 후 답변.
Gemini 2.5 Flash 무료 사용.

환경변수:
  GAME_NEWS_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY
"""

import os
import logging
import time
from datetime import datetime, timezone, timedelta

from google import genai

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

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
gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# 대화 히스토리
chat_history: dict[int, list[str]] = {}
MAX_HISTORY = 10

# 검색 캐시 (120초)
_search_cache: dict[str, dict] = {}
CACHE_TTL = 120

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
- 이모지를 적절히 사용하여 가독성 향상"""


# ─── 실시간 게임 정보 검색 ────────────────────────────
def search_game_info(query: str) -> str:
    """게임 관련 질문에 대해 최신 정보를 DuckDuckGo로 검색."""
    cache_key = query[:50]
    now = time.time()
    if cache_key in _search_cache and now - _search_cache[cache_key]["ts"] < CACHE_TTL:
        return _search_cache[cache_key]["data"]

    results = []
    search_queries = [
        f"{query} game news 2026",
        f"{query} 게임 뉴스",
        f"{query} game review update",
    ]

    try:
        with DDGS() as d:
            for sq in search_queries:
                try:
                    for r in d.text(sq, max_results=3):
                        title = r.get("title", "")
                        body = r.get("body", "")[:120]
                        href = r.get("href", "")
                        if title:
                            results.append(f"• {title}\n  {body}\n  {href}")
                except Exception:
                    pass
                time.sleep(0.5)

            # 최신 뉴스
            try:
                for r in d.news(f"{query} game", max_results=3):
                    title = r.get("title", "")
                    if title:
                        results.append(f"• [최신] {title}")
            except Exception:
                pass
    except Exception as e:
        log.error("검색 오류: %s", e)

    data = "\n".join(results[:12]) if results else "(검색 결과 없음)"
    _search_cache[cache_key] = {"data": data, "ts": now}
    return data


# ─── 권한 체크 ─────────────────────────────────────────
def is_authorized(chat_id: int) -> bool:
    if ALLOWED_CHAT_ID == 0:
        return True
    return chat_id == ALLOWED_CHAT_ID


# ─── Gemini API 응답 생성 ─────────────────────────────
def ask_gemini(chat_id: int, user_message: str) -> str:
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

    # 실시간 검색 (게임 관련 질문일 때만)
    search_data = ""
    if is_game:
        log.info("  🔍 게임 관련 정보 검색 중...")
        search_result = search_game_info(user_message)
        search_data = f"\n\n━━━ 최신 검색 결과 (게임 뉴스/리뷰) ━━━\n{search_result}\n━━━━━━━━━━━━━━━━━━━━━"

    context = "\n".join(history)
    user_prompt = (
        f"{SYSTEM_PROMPT}{search_data}\n\n"
        f"대화 기록:\n{context}\n\n"
        f"위 대화의 마지막 사용자 메시지에 답변해주세요."
    )

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
        )

        assistant_msg = response.text.strip()
        if not assistant_msg:
            return "응답을 받지 못했습니다. 다시 시도해주세요."

        history.append(f"AI: {assistant_msg}")
        chat_history[chat_id] = history
        return assistant_msg

    except Exception as e:
        log.error("Gemini API 오류: %s", e)
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
        "/search [키워드] — 게임 뉴스 검색\n"
        "/clear — 대화 기록 초기화\n"
        "/help — 도움말"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    chat_history.pop(update.effective_chat.id, None)
    _search_cache.clear()
    await update.message.reply_text("대화 기록이 초기화되었습니다.")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """게임 관련 최신 정보 검색."""
    if not is_authorized(update.effective_chat.id):
        return
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("사용법: /search 엘든링 DLC")
        return
    await update.message.chat.send_action("typing")
    _search_cache.pop(query[:50], None)
    result = search_game_info(query)
    await update.message.reply_text(f"🔍 검색: {query}\n\n{result}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.reply_text(
        "🎮 게임뉴스 비서 도움말\n\n"
        "아무 게임 관련 질문이나 해주세요!\n\n"
        "/start — 봇 시작\n"
        "/search [키워드] — 게임 뉴스 검색\n"
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

    reply = ask_gemini(chat_id, user_text)

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
    log.info("Gemini 2.5 Flash + 실시간 검색 모드")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("폴링 시작...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
