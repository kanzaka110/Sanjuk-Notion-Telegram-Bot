"""
텔레그램 챗봇 — 언리얼 튜토리얼 가이드 비서 (Gemini API)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UE5 관련 질문 시 실시간 공식 문서/커뮤니티/영상 검색 후 답변.
Gemini 2.0 Flash 무료 사용.

환경변수:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY
"""

import os
import logging
import time
from datetime import datetime, timezone, timedelta

from google import genai
from chat_db import (
    init_db, save_message, get_recent_messages, clear_history,
    set_preference, get_preference, detect_ue_version, format_user_context,
)

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
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))
KST = timezone(timedelta(hours=9))
gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# 대화 히스토리: SQLite 영속 저장 (chat_db.py)

# 검색 캐시 (120초)
_search_cache: dict[str, dict] = {}
CACHE_TTL = 120

SYSTEM_PROMPT = """당신은 '언리얼 튜토리얼 가이드 비서'. 반말로 대화.

## 가장 중요한 규칙: 모르는 건 지어내지 마
- 아래 "검색 결과"에 포함된 정보만 사실로 취급해
- 존재하지 않는 노드, 클래스, API를 지어내지 마
- 확실하지 않으면 "공식 문서에서 직접 확인해봐"라고 해
- URL은 검색 결과에 실제로 나온 것만 제공해. 지어낸 URL 절대 금지

## 전문 분야
Animation Blueprint, Control Rig, Motion Matching, MetaHuman, Sequencer,
Live Link, ML Deformer, GASP, Mover Plugin, UAF/AnimNext

## 역할
- 정확한 정보 제공. 블루프린트 노드명, C++ 클래스명은 확실한 것만
- 초보자에게는 단계별, 숙련자에게는 최적화 팁
- 실무에서 바로 쓸 수 있게

## 답변 스타일
- 텔레그램 대화답게 간결하게
- 코드/블루프린트 예시는 짧고 핵심만"""


# ─── 실시간 UE 정보 검색 ──────────────────────────────
def search_ue_info(query: str) -> str:
    """UE 관련 질문에 대해 최신 정보를 DuckDuckGo로 검색."""
    cache_key = query[:50]
    now = time.time()
    if cache_key in _search_cache and now - _search_cache[cache_key]["ts"] < CACHE_TTL:
        return _search_cache[cache_key]["data"]

    results = []
    search_queries = [
        f"Unreal Engine {query} site:dev.epicgames.com",
        f"UE5 {query} tutorial guide",
        f"언리얼 엔진 {query} 튜토리얼",
        f"Unreal {query} site:forums.unrealengine.com",
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
                except:
                    pass
                time.sleep(0.5)

            # 최신 뉴스/업데이트
            try:
                for r in d.news(f"Unreal Engine {query}", max_results=3):
                    title = r.get("title", "")
                    if title:
                        results.append(f"• [최신] {title}")
            except:
                pass
    except Exception as e:
        log.error(f"검색 오류: {e}")

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
    # UE 버전 자동 감지
    detected_ver = detect_ue_version(user_message)
    if detected_ver:
        set_preference(chat_id, "ue_version", detected_ver)
        log.info(f"  🎯 UE 버전 감지: {detected_ver}")

    save_message(chat_id, "user", user_message)
    history = get_recent_messages(chat_id, limit=20)

    # UE 관련 키워드 감지
    ue_keywords = [
        "언리얼", "unreal", "UE", "블루프린트", "blueprint", "애니메이션",
        "animation", "control rig", "컨트롤 릭", "motion matching",
        "모션 매칭", "metahuman", "메타휴먼", "sequencer", "시퀀서",
        "live link", "라이브 링크", "ML deformer", "GASP", "mover",
        "ABP", "anim", "IK", "리타겟", "retarget", "morph", "몽타주",
        "montage", "state machine", "스테이트", "blend", "블렌드",
        "노티파이", "notify", "루트 모션", "root motion", "본", "bone",
        "스켈레톤", "skeleton", "메시", "mesh", "나이아가라", "niagara",
        "머티리얼", "material", "레벨", "level", "액터", "actor",
        "컴포넌트", "component", "플러그인", "plugin", "C++",
    ]
    is_ue = any(kw.lower() in user_message.lower() for kw in ue_keywords)

    # 실시간 검색 (UE 관련 질문일 때만)
    search_data = ""
    if is_ue:
        log.info("  🔍 UE 관련 정보 검색 중...")
        search_result = search_ue_info(user_message)
        search_data = f"\n\n━━━ 최신 검색 결과 (공식 문서/커뮤니티/뉴스) ━━━\n{search_result}\n━━━━━━━━━━━━━━━━━━━━━"

    # 사용자 컨텍스트 (UE 버전 등) 주입
    user_context = format_user_context(chat_id)
    if user_context:
        search_data += f"\n\n{user_context}"

    context = "\n".join(history)
    user_prompt = f"{SYSTEM_PROMPT}{search_data}\n\n대화 기록:\n{context}\n\n위 대화의 마지막 사용자 메시지에 답변해주세요."

    try:
        response = gemini_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=user_prompt,
        )

        assistant_msg = response.text.strip()
        if not assistant_msg:
            return "응답을 받지 못했습니다. 다시 시도해주세요."

        save_message(chat_id, "ai", assistant_msg)
        return assistant_msg

    except Exception as e:
        log.error(f"Gemini API 오류: {e}")
        return f"오류가 발생했습니다: {e}"


# ─── 핸들러 ───────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.reply_text(
        "🎮 언리얼 튜토리얼 가이드 비서입니다!\n\n"
        "UE5 관련 질문 시 공식 문서/커뮤니티를 실시간 검색하여 답변합니다.\n\n"
        "전문 분야:\n"
        "• Animation Blueprint / Control Rig\n"
        "• Motion Matching / MetaHuman\n"
        "• Sequencer / Live Link\n"
        "• ML Deformer / GASP / Mover Plugin\n\n"
        "/search [키워드] — UE 관련 최신 정보 검색\n"
        "/clear — 대화 기록 초기화\n"
        "/help — 도움말"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    clear_history(update.effective_chat.id)
    _search_cache.clear()
    await update.message.reply_text("대화 기록이 초기화되었습니다.")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """UE 관련 최신 정보 검색."""
    if not is_authorized(update.effective_chat.id):
        return
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("사용법: /search Control Rig IK")
        return
    await update.message.chat.send_action("typing")
    _search_cache.pop(query[:50], None)  # 강제 갱신
    result = search_ue_info(query)
    await update.message.reply_text(f"🔍 검색: {query}\n\n{result}")


async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """UE 버전 설정/확인."""
    if not is_authorized(update.effective_chat.id):
        return
    chat_id = update.effective_chat.id
    if context.args:
        ver = context.args[0]
        set_preference(chat_id, "ue_version", ver)
        await update.message.reply_text(f"UE 버전이 {ver}로 설정되었습니다. 앞으로 이 버전 기준으로 답변합니다.")
    else:
        current = get_preference(chat_id, "ue_version")
        if current:
            await update.message.reply_text(f"현재 설정된 UE 버전: {current}\n변경: /version 5.5")
        else:
            await update.message.reply_text("UE 버전이 설정되지 않았습니다.\n설정: /version 5.5")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.reply_text(
        "사용 가능한 명령어:\n"
        "/start — 봇 시작\n"
        "/search [키워드] — UE 최신 정보 검색\n"
        "/version [5.x] — UE 버전 설정/확인\n"
        "/clear — 대화 기록 초기화\n"
        "/help — 이 도움말\n\n"
        "UE 관련 질문 시 자동으로 공식 문서/커뮤니티를 검색합니다.\n"
        "대화 중 'UE 5.5' 등을 언급하면 자동으로 버전이 기억됩니다."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if not is_authorized(update.effective_chat.id):
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text
    log.info(f"[{chat_id}] 수신: {user_text[:50]}")

    await update.message.chat.send_action("typing")

    reply = ask_gemini(chat_id, user_text)

    if len(reply) > 4000:
        for i in range(0, len(reply), 4000):
            await update.message.reply_text(reply[i:i + 4000])
    else:
        await update.message.reply_text(reply)

    log.info(f"[{chat_id}] 응답: {reply[:50]}")


# ─── 메인 ─────────────────────────────────────────────
def main():
    init_db()
    now = datetime.now(KST)
    log.info(f"🎮 언리얼 튜토리얼 가이드 비서 시작 — {now.strftime('%Y-%m-%d %H:%M:%S KST')}")
    log.info("Gemini 2.0 Flash + 실시간 검색 모드 + SQLite 영속 저장")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("version", cmd_version))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("폴링 시작...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
