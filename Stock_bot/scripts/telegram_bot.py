"""
텔레그램 챗봇 — 산적주식비서 (Gemini API)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
포트폴리오 실시간 데이터 + 프리미엄 뉴스를 Gemini에게 전달하여
최고급 투자 조언 대화 제공. Gemini 2.0 Flash 무료 사용.

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
    save_trade_note, get_trade_notes, format_trade_notes, extract_trade_from_response,
)

import yfinance as yf

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

# ─── 포트폴리오 ───────────────────────────────────────
PORTFOLIO = {
    "005930.KS": "삼성전자",
    "012450.KS": "한화에어로스페이스",
    "133690.KS": "TIGER 미국나스닥100",
    "360750.KS": "TIGER 미국S&P500",
    "251350.KS": "KODEX MSCI선진국",
    "161510.KS": "PLUS 고배당주",
    "329200.KS": "TIGER 리츠부동산인프라",
    "192090.KS": "TIGER 차이나CSI300",
    "NVDA": "엔비디아",
    "GOOGL": "구글(알파벳A)",
    "MU": "마이크론",
    "LMT": "록히드마틴",
}
INDICES = {"^KS11": "KOSPI", "^KQ11": "KOSDAQ", "^GSPC": "S&P500", "^IXIC": "NASDAQ"}
KRW_TICKERS = {t for t in PORTFOLIO if ".KS" in t}

# 대화 히스토리: SQLite 영속 저장 (chat_db.py)

# 시세 캐시 (60초)
_market_cache = {"data": "", "ts": 0}
CACHE_TTL = 60

SYSTEM_PROMPT = """당신은 '산적주식비서'. 반말로 대화. 오늘은 2026년입니다.

## 가장 중요한 규칙: 모르는 건 지어내지 마
- 아래에 제공되는 "실시간 시장 데이터"만 사실로 취급해
- 뉴스, 이벤트, 공시 정보는 데이터에 포함된 것만 언급해
- 데이터에 없는 주가, 이벤트, 실적을 절대 지어내지 마
- 확인 안 된 정보는 "확인이 필요하다" 또는 "최신 뉴스를 직접 체크해봐"라고 해
- 학습 데이터(과거 정보)를 현재 사실처럼 말하지 마

## 역할
- 실시간 데이터 기반 투자 조언
- 리스크를 먼저 언급, 과장 없이
- 매수/매도 추천 시: 진입가, 목표가, 손절가 포함 (실시간 데이터 기준으로)

## 투자자 프로필
- 투자 성향: 중립 (성장주 + 배당주 혼합)
- 관심: 반도체, 방산, AI, 글로벌 ETF

## 답변 스타일
- 텔레그램 대화답게 간결하게. 마크다운 헤더(###) 쓰지 마
- 리포트 형식 금지. 친구에게 투자 조언하듯이
- 아부 금지, 팩트 기반 직언
- "분석 리포트", "긴급 업데이트" 같은 타이틀 붙이지 마"""


# ─── 실시간 데이터 조회 ───────────────────────────────
def get_market_snapshot() -> str:
    """포트폴리오 시세 + 지수 + 최신 뉴스를 텍스트로 반환 (60초 캐시)."""
    now = time.time()
    if now - _market_cache["ts"] < CACHE_TTL and _market_cache["data"]:
        return _market_cache["data"]

    lines = []
    try:
        # 지수
        lines.append("【시장 지수】")
        for tk, nm in INDICES.items():
            try:
                h = yf.Ticker(tk).history(period="2d")
                if len(h) >= 2:
                    c, p = float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
                    pct = (c - p) / p * 100
                    lines.append(f"  {nm}: {c:,.0f} ({pct:+.2f}%)")
            except:
                pass

        # 포트폴리오
        lines.append("\n【포트폴리오 현재가】")
        for tk, nm in PORTFOLIO.items():
            try:
                h = yf.Ticker(tk).history(period="2d")
                if len(h) >= 2:
                    c, p = float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
                    pct = (c - p) / p * 100
                    sym = "₩" if tk in KRW_TICKERS else "$"
                    lines.append(f"  {nm}: {sym}{c:,.0f} ({pct:+.2f}%)")
            except:
                pass
            time.sleep(0.1)

        # 주요 뉴스
        lines.append("\n【최신 주요 뉴스】")
        news_queries = [
            "stock market today breaking news",
            "코스피 증시 속보",
            "NVDA nvidia stock",
            "semiconductor chip news today",
            "Fed interest rate",
        ]
        with DDGS() as d:
            for q in news_queries[:3]:
                try:
                    for r in d.news(q, max_results=2, timelimit="d"):
                        title = r.get("title", "")
                        if title:
                            lines.append(f"  • {title}")
                except:
                    pass
                time.sleep(0.5)

    except Exception as e:
        lines.append(f"  (데이터 조회 오류: {e})")

    snapshot = "\n".join(lines)
    _market_cache["data"] = snapshot
    _market_cache["ts"] = now
    return snapshot


# ─── 권한 체크 ─────────────────────────────────────────
def is_authorized(chat_id: int) -> bool:
    if ALLOWED_CHAT_ID == 0:
        return True
    return chat_id == ALLOWED_CHAT_ID


# ─── Gemini API 응답 생성 ─────────────────────────────
def ask_gemini(chat_id: int, user_message: str) -> str:
    save_message(chat_id, "user", user_message)
    history = get_recent_messages(chat_id, limit=20)

    # 투자 관련 키워드 감지
    invest_keywords = [
        "주식", "매수", "매도", "종목", "주가", "시장", "증시", "코스피",
        "나스닥", "환율", "금리", "ETF", "포트폴리오", "배당", "실적",
        "삼성", "엔비디아", "NVDA", "마이크론", "한화", "록히드", "구글",
        "stock", "buy", "sell", "market", "반도체", "AI", "VIX",
        "전략", "리스크", "손절", "목표가", "진입", "분할", "수익률",
    ]
    is_invest = any(kw in user_message for kw in invest_keywords)

    # 실시간 데이터 (투자 관련 질문일 때만)
    market_data = ""
    if is_invest:
        log.info("  📊 실시간 시세 조회 중...")
        market_data = f"\n\n━━━ 실시간 시장 데이터 ━━━\n{get_market_snapshot()}\n━━━━━━━━━━━━━━━━━━━━━"

    # 매매 기록 컨텍스트 주입
    trade_context = format_trade_notes(chat_id)
    if trade_context:
        market_data += f"\n\n{trade_context}"

    context = "\n".join(history)
    user_prompt = f"{SYSTEM_PROMPT}{market_data}\n\n대화 기록:\n{context}\n\n위 대화의 마지막 사용자 메시지에 답변해주세요."

    try:
        response = gemini_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=user_prompt,
        )

        assistant_msg = response.text.strip()
        if not assistant_msg:
            return "응답을 받지 못했습니다. 다시 시도해주세요."

        save_message(chat_id, "ai", assistant_msg)

        # 매매 추천 자동 기록
        trade = extract_trade_from_response(assistant_msg)
        if trade:
            save_trade_note(chat_id, trade["ticker"], trade["action"], trade["price"], trade["reason"])
            log.info(f"  💾 매매 기록 저장: {trade['action']} {trade['ticker']}")

        return assistant_msg

    except Exception as e:
        log.error(f"Gemini API 오류: {e}")
        return f"오류가 발생했습니다: {e}"


# ─── 핸들러 ───────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.reply_text(
        "📊 산적주식비서입니다!\n\n"
        "실시간 시세 + 전문 분석 기반으로 대화합니다.\n\n"
        "예시 질문:\n"
        "• 엔비디아 지금 매수해도 돼?\n"
        "• 오늘 시장 분위기 어때?\n"
        "• 삼성전자 목표가 얼마로 잡을까?\n"
        "• 포트폴리오 리밸런싱 어떻게 할까?\n\n"
        "/clear — 대화 기록 초기화\n"
        "/market — 현재 시세 요약"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    clear_history(update.effective_chat.id)
    _market_cache["ts"] = 0  # 캐시도 리셋
    await update.message.reply_text("대화 기록이 초기화되었습니다.")


async def cmd_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """현재 시세 요약 명령어."""
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.chat.send_action("typing")
    _market_cache["ts"] = 0  # 강제 갱신
    snapshot = get_market_snapshot()
    now = datetime.now(KST).strftime("%H:%M KST")
    await update.message.reply_text(f"📊 시세 현황 ({now})\n\n{snapshot}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.reply_text(
        "사용 가능한 명령어:\n"
        "/start — 봇 시작\n"
        "/market — 현재 시세 요약\n"
        "/clear — 대화 기록 초기화\n"
        "/help — 이 도움말\n\n"
        "투자 관련 질문 시 실시간 시세+뉴스를 자동 참조합니다."
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
    log.info(f"📊 산적주식비서 시작 — {now.strftime('%Y-%m-%d %H:%M:%S KST')}")
    log.info("Gemini 2.0 Flash + 실시간 데이터 모드 + SQLite 영속 저장")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("market", cmd_market))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("폴링 시작...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
