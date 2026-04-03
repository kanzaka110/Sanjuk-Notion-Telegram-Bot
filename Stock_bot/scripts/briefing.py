"""
투자 브리핑 자동화 스크립트 v4
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
개선 사항:
  ① 통화 표기 — .KS / ETF → ₩, 미국주식 → $ 자동 구분
  ② 매수/매도 전략에 진입 타이밍 (장중 시간대, 조건) 추가
  ③ Notion 페이지 레이아웃 채팅 시각화 스타일로 전면 개편
     - 상태 배지(🟢🔴🟡) / 가격 카드 / 신호 강도 바 표현
  ④ 날짜 + 시간 저장 (ISO datetime)
"""

import os, json, time, requests
import yfinance as yf
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types
import anthropic

# ═══════════════════════════════════════════════════════
# 0. 설정
# ═══════════════════════════════════════════════════════
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_DB_ID   = os.environ.get("NOTION_DB_ID", os.environ.get("NOTION_DATABASE_ID", ""))
BRIEFING_TYPE  = os.environ.get("BRIEFING_TYPE", "MANUAL")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
KST = timezone(timedelta(hours=9))

LABEL_MAP = {
    "KR_BEFORE": "🇰🇷 국내장 시작 전",
    "US_BEFORE": "🇺🇸 미국장 시작 전",
    "MANUAL":    "📊 수시 브리핑",
}
LABEL = LABEL_MAP.get(BRIEFING_TYPE, "📊 수시 브리핑")

# KRW 통화 판별: .KS 종목 + 국내 ETF 코드 (1xxx, 3xxx)
KRW_TICKERS = {"005930.KS","012450.KS","133690.KS","360750.KS",
               "251350.KS","161510.KS","329200.KS","192090.KS"}

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
    "MU":   "마이크론",
    "LMT":  "록히드마틴",
}
INDICES = {"^KS11":"KOSPI","^KQ11":"KOSDAQ","^GSPC":"S&P500","^IXIC":"NASDAQ","^DJI":"DOW"}
MACRO   = {"BZ=F":"브렌트유","CL=F":"WTI","USDKRW=X":"원달러(₩)","^VIX":"VIX","^TNX":"미10년국채","GC=F":"금"}


# ═══════════════════════════════════════════════════════
# 1. 통화 표기 유틸
# ═══════════════════════════════════════════════════════
def fmt_price(ticker: str, price: float) -> str:
    """티커에 따라 ₩ 또는 $ 표기로 가격 포맷."""
    if ticker in KRW_TICKERS:
        return f"₩{price:,.0f}"
    elif ticker in ("USDKRW=X",):
        return f"₩{price:,.2f}"
    else:
        return f"${price:,.2f}"

def fmt_change(ticker: str, change: float) -> str:
    arrow = "▲" if change >= 0 else "▼"
    abs_c = abs(change)
    if ticker in KRW_TICKERS:
        return f"{arrow} ₩{abs_c:,.0f}"
    elif ticker in ("USDKRW=X",):
        return f"{arrow} ₩{abs_c:,.2f}"
    else:
        return f"{arrow} ${abs_c:,.2f}"

def pct_bar(pct: float) -> str:
    """등락률을 간단한 텍스트 바로 표현."""
    if pct >= 3:   return "▲▲▲"
    if pct >= 1:   return "▲▲"
    if pct >= 0:   return "▲"
    if pct >= -1:  return "▼"
    if pct >= -3:  return "▼▼"
    return "▼▼▼"

def signal_badge(signal: str) -> str:
    m = {"매수":"🟢 매수","매도":"🔴 매도","홀딩":"🔵 홀딩","관망":"⚪ 관망",
         "강력매수":"🔥 강력매수","강력매도":"⛔ 강력매도"}
    return m.get(signal, signal)

def urgency_badge(u: str) -> str:
    m = {"🔥강력":"🔥 강력","⚡적극":"⚡ 적극","✅일반":"✅ 일반",
         "🔴즉시":"🔴 즉시","🟠주의":"🟠 주의","🟡모니터링":"🟡 모니터링"}
    return m.get(u, u)


# ═══════════════════════════════════════════════════════
# 2. yfinance 데이터 수집
# ═══════════════════════════════════════════════════════
def get_quote(ticker):
    try:
        h = yf.Ticker(ticker).history(period="5d")
        if len(h) >= 2:
            c, p = float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
            return {"price":round(c,2),"change":round(c-p,2),"pct":round((c-p)/p*100,2),
                    "high":round(float(h["High"].iloc[-1]),2),
                    "low":round(float(h["Low"].iloc[-1]),2)}
        if len(h)==1:
            c=float(h["Close"].iloc[-1])
            return {"price":c,"change":0,"pct":0,"high":c,"low":c}
    except Exception as e: print(f"  ⚠️  {ticker}: {e}")
    return None

def get_ticker_news(ticker, n=3):
    try:
        items = yf.Ticker(ticker).news or []
        out=[]
        for i in items[:n]:
            t=(i.get("content",{}).get("title") or i.get("title","")).strip()
            if t: out.append(t)
        return out
    except: return []

def fetch_market():
    print("📊 [1/3] yfinance 데이터 수집...")
    stocks = {}
    for tk,nm in PORTFOLIO.items():
        q=get_quote(tk)
        if q: stocks[tk]={"name":nm,**q}
        time.sleep(0.12)
    indices={nm:get_quote(tk) for tk,nm in INDICES.items() if get_quote(tk)}
    macro  ={nm:get_quote(tk) for tk,nm in MACRO.items()   if get_quote(tk)}
    tnews  ={}
    for tk in ["NVDA","GOOGL","MU","LMT","005930.KS","012450.KS"]:
        h=get_ticker_news(tk,3)
        if h: tnews[PORTFOLIO.get(tk,tk)]=h
        time.sleep(0.15)
    return {"stocks":stocks,"indices":indices,"macro":macro,"tnews":tnews}


# ═══════════════════════════════════════════════════════
# 3. 뉴스 수집 — Gemini Google Search 사용
# ═══════════════════════════════════════════════════════
def fetch_news():
    print("🔍 [2/3] Gemini Google Search로 뉴스 수집...")
    return {}  # Gemini가 Google Search 도구로 직접 최신 정보 검색


# ═══════════════════════════════════════════════════════
# 4. Claude API — 구조화 JSON (타이밍 포함)
# ═══════════════════════════════════════════════════════
def build_prompt(mkt, news):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    idx = "\n".join(f"  {k}: {v['price']:,.2f} ({v['pct']:+.2f}%)" for k,v in mkt["indices"].items() if v)
    mac = "\n".join(f"  {k}: {v['price']:,.2f} ({v['pct']:+.2f}%)" for k,v in mkt["macro"].items() if v)
    stk_lines = []
    for tk,d in mkt["stocks"].items():
        price_str = fmt_price(tk, d["price"])
        chg_str   = fmt_change(tk, d["change"])
        high_str  = fmt_price(tk, d["high"])
        low_str   = fmt_price(tk, d["low"])
        tn = mkt["tnews"].get(d["name"],[])
        ns = " / ".join(tn[:2]) if tn else "-"
        stk_lines.append(f"  {d['name']}({tk}): {price_str} ({d['pct']:+.2f}% / {chg_str}) "
                         f"H:{high_str} L:{low_str} | {ns}")
    stk = "\n".join(stk_lines)

    return f"""
당신은 나의 '전략 주식 파트너'입니다.
현재 시각: {now}   |   브리핑 유형: {LABEL}

━━━ yfinance 실시간 데이터 ━━━
【시장 지수】
{idx}

【매크로 지표】
{mac}

【포트폴리오 (통화 포함 현재가)】
{stk}

━━━ 실시간 뉴스 (Google Search로 직접 검색해주세요) ━━━
아래 항목들을 Google Search 도구로 검색하여 최신 정보를 반영하세요:
1. 국내 증시 (코스피, 코스닥 오늘 동향)
2. 미국 증시 (S&P500, 나스닥, 다우 동향)
3. 매크로 (금리, 환율, 유가, VIX)
4. 포트폴리오 종목별 최신 뉴스 (삼성전자, 한화에어로스페이스, 엔비디아, 마이크론, 록히드마틴, 구글)
5. Bloomberg, Reuters, WSJ, CNBC, FT 전문 분석
6. 증권사 리포트, 외국인/기관 수급 동향
7. 오늘 경제 캘린더 (실적 발표, 경제 지표 발표)

━━━ 브리핑 지침 ━━━
① 과장 형용사 금지 — 반드시 % + 수치 사용
② 리스크를 장점보다 먼저 언급
③ 매수/매도 신호는 [매수/매도/홀딩/관망] + 근거 필수
④ 전략에 반드시 진입 타이밍 (시간대, 조건, 분할 계획) 포함
⑤ 솔직한 조언: 아부 금지. "지금 매수해야 하는가?"에 대해 데이터 기반 직언.
   리스크와 기회를 모두 나열하고, 체크리스트 기반으로 결론 도출.
   예수금 ₩4,795,171 보유 중임을 전제로 구체적 판단 제시.

━━━ 출력: 순수 JSON (코드블록 없이) ━━━
{{
  "title": "날짜+시간 + 핵심 요약 (예: 2026.03.20 17:30 국내마감 — KOSPI +0.46%)",
  "market_status": "상승|하락|보합|혼조",
  "investment_decision": "매수실행|매도실행|보류|관망",
  "kospi": "5,789 (+0.46%)",
  "kosdaq": "1,161 (-0.27%)",
  "brent": "$102.81 (-5.4%)",
  "usdkrw": "₩1,497.76",
  "vix": "24.06 (-4.1%)",
  "keywords": "키1 / 키2 / 키3 / 키4 / 키5",
  "next_action": "다음 브리핑 전 2~3줄 액션",

  "market_summary": "리스크 먼저, 수치 중심, 400자 이상 상세 분석",

  "portfolio_rows": [
    {{
      "ticker": "종목코드",
      "name": "종목명",
      "price_display": "₩201,000 또는 $178.56 (통화 표기 필수)",
      "change_pct": "+0.25%",
      "change_display": "+₩500 또는 +$1.23 (통화 표기 필수)",
      "signal": "매수|매도|홀딩|관망",
      "reason": "수치+뉴스 기반 근거 2줄 이내"
    }}
  ],

  "new_picks": [
    {{
      "name": "종목명", "ticker": "코드",
      "reason": "추천 이유 (리스크 먼저)",
      "entry": "진입가 (통화 표기)", "target": "목표가", "stop": "손절가"
    }}
  ],

  "key_news": [
    {{"title": "뉴스 제목", "impact": "시장 영향 1~2줄"}}
  ],

  "strategy_buy": [
    {{
      "ticker": "코드", "name": "종목명",
      "urgency": "🔥강력|⚡적극|✅일반",
      "current_price": "₩201,000 (통화 표기)",
      "entry_price": "진입가 범위 (통화 표기)",
      "target_price": "목표가 (통화 + 상승률%)",
      "stop_loss": "손절가 (통화 + 하락률%)",
      "shares": "추천 매수 수량 (예: 5주, 10주). 예수금과 현재가 기반으로 구체적 주 수 제시",
      "position_pct": "포지션 비중 권장 (예: 전체의 15%)",
      "split_plan": "1차 50% @ ₩200,000 (장초반 9:00~9:30) / 2차 50% @ ₩195,000 (추가 하락 조건)",
      "timing": "진입 타이밍 — 구체적 시간대, 장중 조건, 거래량 확인 포인트",
      "risk_note": "리스크 한 줄 요약",
      "reason": "매수 근거 상세 (수치 + 뉴스 기반)"
    }}
  ],

  "strategy_sell": [
    {{
      "ticker": "코드", "name": "종목명",
      "urgency": "🔴즉시|🟠주의|🟡모니터링",
      "current_price": "현재가 (통화 표기)",
      "shares": "추천 매도 수량 (예: 전량, 절반(5주), 3주). 보유 수량 기반 구체적 제시",
      "take_profit": "익절 목표가 (통화 + 상승률%)",
      "stop_loss": "손절가 (통화 + 하락률%)",
      "timing": "매도 타이밍 — 조건, 시간대, 트리거 이벤트",
      "reason": "매도 근거 (리스크 수치 기반)"
    }}
  ],

  "strategy_summary": "오늘 가장 중요한 매수/매도 판단 요약. 예수금 사용 우선순위 포함. 300자 이상.",

  "advisor_verdict": "매수대기|소액분할|적극매수|매도고려 중 하나",
  "advisor_oneliner": "지금 이 시장에서 취해야 할 행동 한 문장 직언 (수치 포함, 아부 금지)",

  "advisor_checklist": [
    {{
      "condition": "체크 조건명 (예: 외국인 순매수 전환)",
      "status": "충족|미충족|부분충족",
      "detail": "현재 수치와 상황 설명 한 줄"
    }}
  ],

  "advisor_risks": ["리스크 항목 1 (수치 포함)", "리스크 항목 2", "리스크 항목 3"],
  "advisor_opportunities": ["기회 항목 1 (수치 포함)", "기회 항목 2"],

  "advisor_scenarios": [
    {{
      "label": "시나리오명 (예: A안 — 평화 전개)",
      "condition": "발동 조건",
      "action": "구체적 액션 (종목명+수량+금액)",
      "amount": "집행 금액 (예: ₩2,410,000)"
    }}
  ],

  "advisor_conclusion": "300자 이상 솔직한 종합 결론. 지금 당장 해야 할 것과 하지 말아야 할 것. 아부 없이 팩트 기반."
}}
""".strip()


def gather_news_with_gemini(mkt) -> str:
    """Step 1: Gemini 2.5 Pro + Google Search로 최신 뉴스/분석 수집."""
    print("🔍 [2.5/3] Gemini 2.5 Pro — Google Search로 정보 수집...")
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    stock_names = ", ".join(f"{nm}({tk})" for tk,nm in PORTFOLIO.items())
    gather_prompt = f"""현재 시각: {now}

다음 항목들을 Google Search로 검색하여 최신 정보를 수집해주세요:

1. 국내 증시 (코스피, 코스닥 오늘 동향, 외국인/기관 수급)
2. 미국 증시 (S&P500, 나스닥, 다우 동향)
3. 매크로 (금리, 환율, 유가, VIX, Fed 동향)
4. 포트폴리오 종목별 최신 뉴스: {stock_names}
5. Bloomberg, Reuters, WSJ, CNBC, FT 전문 분석
6. 증권사 리포트, 외국인/기관 매매 동향
7. 오늘 경제 캘린더 (실적 발표, 경제 지표)
8. 반도체/AI 관련 최신 뉴스

각 항목별로 핵심 내용을 정리해서 텍스트로 반환해주세요. 출처도 포함해주세요."""

    try:
        google_search_tool = types.Tool(google_search=types.GoogleSearch())
        response = gemini_client.models.generate_content(
            model="gemini-2.5-pro",
            contents=gather_prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                max_output_tokens=5000,
            ),
        )
        gathered = response.text.strip()
        print(f"  📄 수집 완료 ({len(gathered)}자)")
        return gathered
    except Exception as e:
        print(f"  ⚠️ Gemini 뉴스 수집 오류: {e}")
        return "(뉴스 수집 실패)"


def generate(mkt, news):
    """Step 2: 수집된 정보를 Claude Sonnet 4.6으로 분석."""
    # Gemini로 최신 뉴스 수집
    gathered_news = gather_news_with_gemini(mkt)

    print("🤖 [3/3] Claude Sonnet 4.6 — 전략 분석 생성...")
    prompt = build_prompt(mkt, news)
    # 수집된 뉴스를 프롬프트에 추가
    prompt = prompt.replace(
        "━━━ 실시간 뉴스 (Google Search로 직접 검색해주세요) ━━━",
        "━━━ 실시간 뉴스 (Gemini Google Search 수집 결과) ━━━"
    )
    prompt = prompt.replace(
        """아래 항목들을 Google Search 도구로 검색하여 최신 정보를 반영하세요:
1. 국내 증시 (코스피, 코스닥 오늘 동향)
2. 미국 증시 (S&P500, 나스닥, 다우 동향)
3. 매크로 (금리, 환율, 유가, VIX)
4. 포트폴리오 종목별 최신 뉴스 (삼성전자, 한화에어로스페이스, 엔비디아, 마이크론, 록히드마틴, 구글)
5. Bloomberg, Reuters, WSJ, CNBC, FT 전문 분석
6. 증권사 리포트, 외국인/기관 수급 동향
7. 오늘 경제 캘린더 (실적 발표, 경제 지표 발표)""",
        gathered_news,
    )

    response = claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=10000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    if "```" in raw:
        for p in raw.split("```"):
            p=p.strip().lstrip("json").strip()
            try: return json.loads(p)
            except: continue
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ⚠️ JSON 파싱 실패: {e}")
        print(f"  📄 원본 응답 (처음 500자): {raw[:500]}")
        raise


# ═══════════════════════════════════════════════════════
# 5. Notion 블록 빌더 — 채팅 시각화 스타일
# ═══════════════════════════════════════════════════════
def _rt(text, bold=False, color=None):
    ann={}
    if bold: ann["bold"]=True
    if color: ann["color"]=color
    item={"type":"text","text":{"content":str(text)[:2000]}}
    if ann: item["annotations"]=ann
    return [item]

def H1(txt, bg="blue_background"):
    return {"object":"block","type":"heading_1","heading_1":{"rich_text":_rt(txt),"color":bg}}
def H2(txt, bg="default"):
    return {"object":"block","type":"heading_2","heading_2":{"rich_text":_rt(txt),"color":bg}}
def H3(txt, bg="default"):
    return {"object":"block","type":"heading_3","heading_3":{"rich_text":_rt(txt),"color":bg}}
def P(txt, bold=False):
    return {"object":"block","type":"paragraph","paragraph":{"rich_text":_rt(txt,bold=bold)}}
def BUL(txt):
    return {"object":"block","type":"bulleted_list_item",
            "bulleted_list_item":{"rich_text":_rt(txt)}}
def NUM(txt):
    return {"object":"block","type":"numbered_list_item",
            "numbered_list_item":{"rich_text":_rt(txt)}}
def DIV():
    return {"object":"block","type":"divider","divider":{}}
def CALLOUT(txt, emoji="📌", bg="gray_background"):
    return {"object":"block","type":"callout",
            "callout":{"rich_text":_rt(txt),"icon":{"type":"emoji","emoji":emoji},"color":bg}}
def QUOTE(txt):
    return {"object":"block","type":"quote","quote":{"rich_text":_rt(txt)}}
def TOGGLE(title, children, color="default"):
    return {"object":"block","type":"toggle",
            "toggle":{"rich_text":_rt(title,bold=True),"color":color,"children":children}}

def TABLE(rows, has_header=True):
    """rows: list[list[str]]  첫 번째 행이 헤더"""
    if not rows: return P("(데이터 없음)")
    return {
        "object":"block","type":"table",
        "table":{
            "table_width":len(rows[0]),
            "has_column_header":has_header,
            "has_row_header":False,
            "children":[
                {"object":"block","type":"table_row",
                 "table_row":{"cells":[[{"type":"text","text":{"content":c}}] for c in row]}}
                for row in rows
            ]
        }
    }

# ── 섹션별 블록 생성 ──────────────────────────────────

def section_header_block(now_kst):
    """최상단 헤더 — 채팅 시각화 스타일"""
    return [
        CALLOUT(
            f"📅  {now_kst}   |   {LABEL}",
            "🚀", "yellow_background"),
        DIV(),
    ]

def section_market_overview(mkt):
    """시장 지수 + 매크로 — 카드형 테이블"""
    blocks = [H2("📈  시장 지수", "blue_background")]

    # 지수 테이블
    rows=[["지수","현재가","등락률","방향"]]
    for nm,v in mkt["indices"].items():
        if not v: continue
        arrow = "▲" if v["pct"]>=0 else "▼"
        color_txt = f"{arrow} {v['pct']:+.2f}%"
        rows.append([nm, f"{v['price']:,.2f}", color_txt, pct_bar(v["pct"])])
    blocks.append(TABLE(rows))

    # 매크로 테이블
    blocks.append(H2("🌐  매크로 지표", "gray_background"))
    mac_rows=[["지표","현재값","전일비","방향"]]
    for nm,v in mkt["macro"].items():
        if not v: continue
        # 원달러는 ₩ 표기
        if "원달러" in nm:
            val_str = f"₩{v['price']:,.2f}"
            chg_str = f"{'+' if v['pct']>=0 else ''}{v['pct']:+.2f}%"
        elif "VIX" in nm or "국채" in nm:
            val_str = f"{v['price']:.2f}"
            chg_str = f"{'+' if v['pct']>=0 else ''}{v['pct']:+.2f}%"
        else:
            val_str = f"${v['price']:,.2f}"
            chg_str = f"{'+' if v['pct']>=0 else ''}{v['pct']:+.2f}%"
        mac_rows.append([nm, val_str, chg_str, pct_bar(v["pct"])])
    blocks.append(TABLE(mac_rows))
    blocks.append(DIV())
    return blocks

def section_market_summary(briefing):
    blocks=[H2("📋  시장 요약", "blue_background")]
    raw = briefing.get("market_summary","")
    for line in raw.split("\n"):
        line=line.strip()
        if not line: continue
        if line.startswith("- ") or line.startswith("* "): blocks.append(BUL(line[2:]))
        elif line.startswith("> "): blocks.append(CALLOUT(line[2:], "📌"))
        elif line.startswith("## ") or line.startswith("# "): continue
        else: blocks.append(P(line))
    blocks.append(DIV())
    return blocks

def section_portfolio(briefing, mkt):
    """보유 종목 브리핑 — 신호 배지 + 통화 표기 테이블"""
    blocks=[H2("📋  보유 종목 브리핑", "blue_background")]

    rows=[["종목","현재가 (통화)","등락","신호","판단 근거"]]
    # Claude 가 생성한 portfolio_rows 우선 사용
    for r in briefing.get("portfolio_rows",[]):
        rows.append([
            f"{r.get('name','')}",
            r.get("price_display",""),
            f"{r.get('change_pct','')} ({r.get('change_display','')})",
            signal_badge(r.get("signal","관망")),
            r.get("reason","")[:80],
        ])

    # portfolio_rows 가 없으면 raw yfinance 데이터로 폴백
    if len(rows)==1:
        for tk,d in mkt["stocks"].items():
            rows.append([
                d["name"],
                fmt_price(tk, d["price"]),
                f"{d['pct']:+.2f}% ({fmt_change(tk,d['change'])})",
                "—",
                "—",
            ])
    blocks.append(TABLE(rows))
    blocks.append(DIV())
    return blocks

def section_new_picks(briefing):
    picks = briefing.get("new_picks",[])
    if not picks: return []
    blocks=[H2("💡  신규 추천 종목", "green_background")]
    for pick in picks:
        blocks.append(CALLOUT(
            f"🎯  {pick.get('name','')} ({pick.get('ticker','')})\n"
            f"진입가: {pick.get('entry','')}   목표가: {pick.get('target','')}   손절가: {pick.get('stop','')}",
            "💡","green_background"))
        reason = pick.get("reason","")
        for line in reason.split("\n"):
            if line.strip(): blocks.append(BUL(line.strip()))
    blocks.append(DIV())
    return blocks

def section_key_news(briefing):
    news_items = briefing.get("key_news",[])
    if not news_items: return []
    blocks=[H2("📰  오늘 반드시 확인할 뉴스 3가지", "orange_background")]
    for i,item in enumerate(news_items[:3], 1):
        title = item.get("title","")
        impact = item.get("impact","")
        blocks.append(CALLOUT(
            f"{i}.  {title}\n→  {impact}",
            "📌","gray_background"))
    blocks.append(DIV())
    return blocks

# ── 핵심: 매수/매도 전략 — 타이밍 포함 시각화 ──────────
def section_strategy(briefing):
    blocks = []

    # ▶ 전략 총평 callout (눈에 띄게)
    blocks.append(H1("🎯  매수 / 매도 전략", "red_background"))
    summary = briefing.get("strategy_summary","")
    if summary:
        blocks.append(CALLOUT(summary, "⚡", "yellow_background"))
    blocks.append(DIV())

    # ─ 🟢 매수 액션 ────────────────────────────────────────
    buys = briefing.get("strategy_buy",[])
    if buys:
        blocks.append(H2("🟢  매수 액션", "green_background"))

        # 매수 요약 테이블
        buy_rows=[["종목","긴급도","현재가","진입가","목표가","손절가","포지션"]]
        for b in buys:
            buy_rows.append([
                f"{b.get('name','')} ({b.get('ticker','')})",
                urgency_badge(b.get("urgency","")),
                b.get("current_price",""),
                b.get("entry_price",""),
                b.get("target_price",""),
                b.get("stop_loss",""),
                b.get("position_pct",""),
            ])
        blocks.append(TABLE(buy_rows))

        # 각 종목 상세 토글
        for b in buys:
            detail = []

            # 타이밍 callout (핵심!)
            timing = b.get("timing","")
            if timing:
                detail.append(CALLOUT(f"⏰  진입 타이밍\n{timing}", "⏰", "blue_background"))

            # 분할 계획 callout
            split = b.get("split_plan","")
            if split:
                detail.append(CALLOUT(f"📐  분할 매수 계획\n{split}", "📐", "purple_background"))

            # 리스크 경고
            risk = b.get("risk_note","")
            if risk:
                detail.append(CALLOUT(f"⚠️  리스크\n{risk}", "⚠️", "red_background"))

            # 상세 근거
            reason = b.get("reason","")
            if reason:
                detail.append(P("📌  매수 근거", bold=True))
                for line in reason.split("\n"):
                    if line.strip(): detail.append(BUL(line.strip()))

            if detail:
                blocks.append(TOGGLE(
                    f"▸  {b.get('name','')} ({b.get('ticker','')}) 상세 전략",
                    detail, "green"))
        blocks.append(DIV())

    # ─ 🔴 매도 / 주의 ────────────────────────────────────────
    sells = briefing.get("strategy_sell",[])
    if sells:
        blocks.append(H2("🔴  매도 / 주의 종목", "red_background"))

        sell_rows=[["종목","긴급도","현재가","익절가","손절가","매도 근거 요약"]]
        for s in sells:
            reason_short = s.get("reason","")
            sell_rows.append([
                f"{s.get('name','')} ({s.get('ticker','')})",
                urgency_badge(s.get("urgency","")),
                s.get("current_price",""),
                s.get("take_profit",""),
                s.get("stop_loss",""),
                reason_short[:60]+"…" if len(reason_short)>60 else reason_short,
            ])
        blocks.append(TABLE(sell_rows))

        for s in sells:
            detail=[]

            # 타이밍 callout
            timing=s.get("timing","")
            if timing:
                detail.append(CALLOUT(f"⏰  매도 타이밍 / 트리거\n{timing}","⏰","orange_background"))

            # 상세 근거
            reason=s.get("reason","")
            if reason:
                detail.append(P("📌  매도 근거",bold=True))
                for line in reason.split("\n"):
                    if line.strip(): detail.append(BUL(line.strip()))

            if detail:
                blocks.append(TOGGLE(
                    f"▸  {s.get('name','')} ({s.get('ticker','')}) 매도 상세",
                    detail,"red"))
        blocks.append(DIV())

    return blocks

def section_portfolio_raw(mkt):
    """포트폴리오 실시간 원데이터 — 통화 표기 포함"""
    blocks=[H2("📊  포트폴리오 실시간 현황 (yfinance)", "gray_background")]
    rows=[["종목 (티커)","구분","현재가","등락률","변동액","고가","저가"]]
    for tk,d in mkt["stocks"].items():
        if tk in KRW_TICKERS:
            cat = "국내주식" if tk=="012450.KS" or tk=="005930.KS" else "국내 ETF"
        else:
            cat = "미국주식"
        s="▲" if d["pct"]>=0 else "▼"
        rows.append([
            f"{d['name']} ({tk})",
            cat,
            fmt_price(tk, d["price"]),
            f"{s} {d['pct']:+.2f}%",
            fmt_change(tk, d["change"]),
            fmt_price(tk, d["high"]),
            fmt_price(tk, d["low"]),
        ])
    blocks.append(TABLE(rows))
    blocks.append(DIV())
    return blocks


def section_advisor(briefing):
    """솔직한 AI 조언 섹션 — 매수/대기 판단 + 체크리스트 + 시나리오"""
    verdict   = briefing.get("advisor_verdict", "")
    oneliner  = briefing.get("advisor_oneliner", "")
    checklist = briefing.get("advisor_checklist", [])
    risks     = briefing.get("advisor_risks", [])
    opps      = briefing.get("advisor_opportunities", [])
    scenarios = briefing.get("advisor_scenarios", [])
    conclusion= briefing.get("advisor_conclusion", "")

    if not verdict and not oneliner: return []

    # 판단 배경색 결정
    verdict_color_map = {
        "매수대기":   ("orange_background", "⏸️"),
        "소액분할":   ("blue_background",   "🔵"),
        "적극매수":   ("green_background",  "🟢"),
        "매도고려":   ("red_background",    "🔴"),
    }
    bg, emoji = verdict_color_map.get(verdict, ("yellow_background", "💡"))

    blocks = [H1(f"💬  AI 솔직한 조언 — {verdict}", bg)]

    # 한 줄 직언 callout
    if oneliner:
        blocks.append(CALLOUT(oneliner, emoji, bg))

    # 체크리스트 테이블
    if checklist:
        blocks.append(H2("✅  매수 조건 체크리스트", "gray_background"))
        status_icon = {"충족":"✅","미충족":"❌","부분충족":"🔶"}
        rows = [["조건","상태","현재 상황"]]
        for item in checklist:
            icon = status_icon.get(item.get("status",""), "—")
            rows.append([
                item.get("condition",""),
                f"{icon} {item.get('status','')}",
                item.get("detail",""),
            ])
        blocks.append(TABLE(rows))
        blocks.append(DIV())

    # 리스크 & 기회 나란히
    if risks or opps:
        blocks.append(H2("⚖️  리스크 vs 기회", "gray_background"))
        if risks:
            risk_txt = "\n".join(f"• {r}" for r in risks)
            blocks.append(CALLOUT(f"리스크\n{risk_txt}", "⚠️", "red_background"))
        if opps:
            opp_txt = "\n".join(f"• {o}" for o in opps)
            blocks.append(CALLOUT(f"기회\n{opp_txt}", "💡", "green_background"))
        blocks.append(DIV())

    # 시나리오 테이블
    if scenarios:
        blocks.append(H2("📅  시나리오별 액션 플랜", "blue_background"))
        sc_rows = [["시나리오","발동 조건","액션","집행 금액"]]
        for sc in scenarios:
            sc_rows.append([
                sc.get("label",""),
                sc.get("condition",""),
                sc.get("action",""),
                sc.get("amount",""),
            ])
        blocks.append(TABLE(sc_rows))
        blocks.append(DIV())

    # 종합 결론
    if conclusion:
        blocks.append(H2("📝  종합 결론 (직언)", "yellow_background"))
        for line in conclusion.split("\n"):
            line = line.strip()
            if not line: continue
            if line.startswith("- ") or line.startswith("* "):
                blocks.append(BUL(line[2:]))
            else:
                blocks.append(P(line))
        blocks.append(DIV())

    return blocks

def section_footer():
    return [CALLOUT(
        "본 브리핑은 AI 투자 파트너(Gemini)가 yfinance + Google Search + 프로젝트 지침을 기반으로 자동 생성합니다.\n"
        "최종 투자 판단은 본인 책임입니다.",
        "⚠️","red_background")]


def build_children(briefing, mkt):
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    B = []
    B += section_header_block(now_kst)
    B += section_market_overview(mkt)
    B += section_market_summary(briefing)
    B += section_portfolio(briefing, mkt)
    B += section_new_picks(briefing)
    B += section_key_news(briefing)
    B += section_advisor(briefing)
    B += section_strategy(briefing)
    B += section_portfolio_raw(mkt)
    B += section_footer()
    return B[:100]


# ═══════════════════════════════════════════════════════
# 6. Notion 저장 — datetime 포함
# ═══════════════════════════════════════════════════════
def save(briefing, mkt):
    print("📝 Notion 저장...")
    now_kst = datetime.now(KST)
    dt_iso  = now_kst.isoformat()  # 날짜+시간 ISO 형식
    children = build_children(briefing, mkt)

    def rt(s): return [{"type":"text","text":{"content":str(s)[:2000]}}]

    headers={"Authorization":f"Bearer {NOTION_API_KEY}",
             "Notion-Version":"2022-06-28","Content-Type":"application/json"}

    # 먼저 데이터베이스 스키마를 조회하여 실제 속성명 확인
    db_res = requests.get(f"https://api.notion.com/v1/databases/{NOTION_DB_ID}",
                          headers=headers, timeout=30)
    db_props = set()
    if db_res.status_code == 200:
        db_props = set(db_res.json().get("properties", {}).keys())
        print(f"  📋 DB 속성: {', '.join(sorted(db_props))}")

    # 전체 속성 매핑 (코드에서 사용하는 이름 → 값)
    all_props = {
        "브리핑 제목": {"title":     rt(briefing.get("title", f"{now_kst.strftime('%Y.%m.%d %H:%M')} 브리핑"))},
        "날짜":        {"date":      {"start": dt_iso}},
        "브리핑구분":  {"select":    {"name": LABEL}},
        "시장상황":    {"select":    {"name": briefing.get("market_status","혼조")}},
        "KOSPI":       {"rich_text": rt(briefing.get("kospi",""))},
        "코스닥":      {"rich_text": rt(briefing.get("kosdaq",""))},
        "브렌트유_유가":{"rich_text": rt(briefing.get("brent",""))},
        "원달러환율":  {"rich_text": rt(briefing.get("usdkrw",""))},
        "VIX":         {"rich_text": rt(briefing.get("vix",""))},
        "투자결정":    {"select":    {"name": briefing.get("investment_decision","관망")}},
        "핵심키워드":  {"rich_text": rt(briefing.get("keywords",""))},
        "다음액션":    {"rich_text": rt(briefing.get("next_action",""))},
        "AI조언":      {"select":    {"name": briefing.get("advisor_verdict","중립") if briefing.get("advisor_verdict","") in ["매수대기","소액분할","적극매수","매도고려","중립"] else "중립"}},
    }

    # DB에 실제 존재하는 속성만 사용 (스키마 조회 실패 시 전부 시도)
    if db_props:
        properties = {k: v for k, v in all_props.items() if k in db_props}
        # title 속성은 이름이 다를 수 있음 — DB에서 title 타입 속성 찾기
        title_prop = None
        for pname, pinfo in db_res.json().get("properties", {}).items():
            if pinfo.get("type") == "title":
                title_prop = pname
                break
        if title_prop and title_prop not in properties:
            properties[title_prop] = {"title": rt(briefing.get("title", f"{now_kst.strftime('%Y.%m.%d %H:%M')} 브리핑"))}
        skipped = set(all_props.keys()) - set(properties.keys())
        if skipped:
            print(f"  ⏭️  DB에 없는 속성 스킵: {', '.join(skipped)}")
    else:
        properties = all_props

    payload = {
        "parent":  {"database_id": NOTION_DB_ID},
        "icon":    {"type":"emoji","emoji":"📊"},
        "properties": properties,
        "children": children,
    }

    res=requests.post("https://api.notion.com/v1/pages",
                      headers=headers, json=payload, timeout=60)
    if res.status_code!=200:
        print(f"  ❌ {res.status_code}: {res.text[:400]}")
        res.raise_for_status()
    pid=res.json()["id"]
    print(f"  ✅ https://notion.so/{pid.replace('-','')}")
    return pid


# ═══════════════════════════════════════════════════════
# 7. 텔레그램 알림
# ═══════════════════════════════════════════════════════
def send_telegram(briefing, notion_page_id):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("  ⏭️  텔레그램 설정 없음 — 건너뜀")
        return
    print("📨 텔레그램 전송...")

    now_kst = datetime.now(KST)
    title = briefing.get("title", f"{now_kst.strftime('%Y.%m.%d %H:%M')} 브리핑")
    status = briefing.get("market_status", "혼조")
    verdict = briefing.get("advisor_verdict", "중립")
    oneliner = briefing.get("advisor_oneliner", "")
    next_action = briefing.get("next_action", "")
    notion_url = f"https://notion.so/{notion_page_id.replace('-', '')}"

    # ── 매수 전략 ──
    buy_lines = []
    for s in briefing.get("strategy_buy", []):
        name = s.get("name", s.get("ticker", ""))
        urgency = s.get("urgency", "")
        entry = s.get("entry_price", "")
        target = s.get("target_price", "")
        stop = s.get("stop_loss", "")
        shares = s.get("shares", "")
        line = f"{urgency} {name}"
        if shares:
            line += f" [{shares}]"
        line += f"\n▸ {entry} → {target} ✂ {stop}"
        buy_lines.append(line)

    # ── 매도 전략 ──
    sell_lines = []
    for s in briefing.get("strategy_sell", []):
        name = s.get("name", s.get("ticker", ""))
        urgency = s.get("urgency", "")
        tp = s.get("take_profit", "")
        sl = s.get("stop_loss", "")
        shares = s.get("shares", "")
        line = f"{urgency} {name}"
        if shares:
            line += f" [{shares}]"
        line += f"\n▸ 익절 {tp} ✂ {sl}"
        sell_lines.append(line)

    # ── 메시지 조립 ──
    msg = f"📊 {LABEL}\n{title}\n\n"

    if oneliner:
        msg += f"💬 {oneliner}\n\n"

    if buy_lines:
        msg += "🟢 매수\n" + "\n".join(buy_lines) + "\n\n"

    if sell_lines:
        msg += "🔴 매도\n" + "\n".join(sell_lines) + "\n\n"

    msg += f"🎯 AI: {verdict}\n▶ {next_action}\n\n"
    msg += f"📋 [Notion 상세보기]({notion_url})"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        res = requests.post(url, json=payload, timeout=30)
        if res.status_code == 200:
            print("  ✅ 텔레그램 전송 완료")
        else:
            print(f"  ⚠️ 텔레그램 전송 실패: {res.status_code} {res.text[:200]}")
    except Exception as e:
        print(f"  ⚠️ 텔레그램 전송 오류: {e}")


# ═══════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════
def main():
    now = datetime.now(KST)
    print(f"\n{'═'*56}")
    print(f"  🚀  {LABEL}")
    print(f"  🕐  {now.strftime('%Y-%m-%d %H:%M:%S KST')}")
    print(f"{'═'*56}\n")
    # 환경변수 진단
    print(f"  GEMINI_API_KEY: {'✅' if GEMINI_API_KEY else '❌ 없음'}")
    print(f"  CLAUDE_API_KEY: {'✅' if CLAUDE_API_KEY else '❌ 없음'}")
    print(f"  NOTION_API_KEY: {'✅' if NOTION_API_KEY else '❌ 없음'}")
    print(f"  NOTION_DB_ID:   {'✅' if NOTION_DB_ID else '❌ 없음'}")
    print(f"  BRIEFING_TYPE:  {BRIEFING_TYPE}")
    print()
    if not CLAUDE_API_KEY:
        print("❌ CLAUDE_API_KEY / ANTHROPIC_API_KEY 환경변수가 없습니다.")
        return
    if not NOTION_API_KEY or not NOTION_DB_ID:
        print("❌ NOTION_API_KEY 또는 NOTION_DB_ID 환경변수가 없습니다.")
        return
    try:
        mkt = fetch_market()
        news = fetch_news()
        briefing = generate(mkt, news)
        page_id = save(briefing, mkt)
        send_telegram(briefing, page_id)
        print(f"\n{'═'*56}")
        print("  ✅  브리핑 완료!")
        print(f"{'═'*56}\n")
    except Exception as e:
        print(f"\n❌ 브리핑 실패: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
