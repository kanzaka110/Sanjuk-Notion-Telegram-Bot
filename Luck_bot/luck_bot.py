"""
텔레그램 챗봇 — 나의 운세 / Sanjuk_Luck_bot
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
사주 원국(壬寅일 戊申시) 기반 운세 상담 봇.
- 정기 브리핑 (일간/주간/월간): Claude Sonnet 4.6
- 대화형 채팅: Gemini 3 Flash (무료)

환경변수:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY, ANTHROPIC_API_KEY
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta, time as dt_time

import anthropic
from google import genai

from saju_calendar import get_daily_analysis, get_week_analysis

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
claude_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ─── 사주 데이터 ─────────────────────────────────────────
SAJU_DATA = """
[사주 원국]
- 이름: 채승호
- 생년월일: 음력 1984년 4월 7일 (양력 1984년 5월 7일)
- 태어난 시: 申시 (15:00~17:00)
- 사주: 甲子(년) 己巳(월) 壬寅(일) 戊申(시)
- 일간: 壬水 (큰 바다, 강물의 기운)

[십성 배치]
- 년주: 甲(식신) 子(겁재) — 창작력의 뿌리, 가정의 기반
- 월주: 己(정관) 巳(정재) — 직업운, 안정적 수입
- 일주: 壬(본인) 寅(식신) — 창작, 기술 역량
- 시주: 戊(편관) 申(편인) — 리더십, 비전통적 문제해결

[핵심 격국]
- 살인상생(殺印相生): 편관(戊)+편인(申 속 庚) → 역경을 딛고 높은 자리에 오르는 구조
- 巳申합(육합): 직업궁+결과궁 합 → 한 직업에 오래 안착
- 식신 강세: 창작·기술 직종에 최적화된 사주

[현재 대운: 4대운 癸酉 (2024~2033)]
- 酉(정인): 배움, 기술 습득, 자격 취득에 유리
- 巳酉 반합(금국): 인성 강화 → 기술적 역량이 크게 인정받는 시기
- 대운 癸는 壬의 동료(겁재) → 자기 힘으로 개척하는 운

[2026년 세운: 丙午(병오)]
- 키워드: "격변 속 재물, 새로운 출발"
- 丙-壬 천간충: 재물이 압박하지만 적극적으로 잡을 수 있는 돈
- 午-子 지지충: 삶의 기반 변화 (퇴직으로 상당 부분 소화됨)
- 午-寅 반합(화국): 식신에 불이 붙어 창작력·기술력 폭발
- 종합: ★★★★☆ (5점 만점 4점)
- 상반기 기반 다지기, 하반기 안착
- 황금기: 5월(최대 기회), 7월(두 번째 기회)

[현재 상황]
- 직업: 애니메이션 TA (Technical Artist) 지망
- 전직: 블루홀(크래프톤) 10년 애니메이션 팀장 → 2026.01 퇴직
- 이직: 시프트업 스트라이프블레이드 면접 완료, 오퍼 대기 중
- 가족: 기혼, 아들 1명 (2014년생, 12세)
- 건강: 양호하나 올해 화기 과다로 심장·눈·혈압 주의

[용신(用神) / 기신(忌神) — 사주 분석의 핵심 기준]
- 일간 壬水는 巳月(화왕절) 출생이나, 시지 申(장생)+년지 子(제왕)로 수기 보충
- 巳申합(금국)으로 인성 강화 → 신강(身强)에 가까운 중화 사주
- 용신(用神): 목(木) = 식상 — 강한 수를 설기시켜 창작·표현으로 발산. TA 직업과 정확히 부합
- 희신(喜神): 화(火) = 재성 — 노력의 결실, 실질적 수입
- 기신(忌神): 수(水) = 비겁 — 이미 강한 수를 더 강하게. 경쟁 심화, 재물 분산
- 구신(仇神): 금(金) = 인성 — 금생수로 수를 더 강하게. 과보호, 의존, 게으름 유발
- 한신(閒神): 토(土) = 관성 — 적당한 제어. 과하면 압박, 적당하면 직장운
- ★ 운세 판단 기준: 목·화가 오는 날은 좋고, 수·금이 과한 날은 주의

[개운법]
- 유리한 방위: 서쪽(金), 북쪽(水)
- 유리한 색상: 흰색·은색(金), 검정·남색(水)
- 유리한 숫자: 1, 6 (水) / 4, 9 (金)
- 피해야 할 색상: 빨강·주황 (화기 과다)
- 개운 활동: 수영, 물가 산책, 수족관 방문
- 주의할 달: 5월(재물 과욕), 10~11월(충 에너지 집중)

[세운 검증 — 주요 사건과 간지의 일치]
- 2010 庚寅: 편인 庚 투출 + 寅(식신) → 첫 취직(T3), 기술직 시작
- 2012 壬辰: 비견 壬 + 辰(편관) → 결혼 + 웹젠 이직, 독립·새 출발
- 2016 丙申: 편재 丙 + 申(편인) → 블루홀 입사, 시주와 공명하는 큰 기회
- 2019 己亥: 정관 己 + 亥-巳 충 → 월지 충돌이 재물 변동 촉발, 큰 재물 유입
- 2026 丙午: 편재 丙 + 午-子 충 → 퇴직(근본 변화) + 뜻밖의 재물

[건강 상세]
- 壬水 일간이 丙午(화) 만남 → 수극화로 에너지 소모 큼
- 주의 부위: 심장·혈압·눈(午=심장, 丙=눈), 신장·방광(壬水 본래 장기)
- 丙壬충은 내면 긴장감 상승 → 불면·초조 가능, 규칙적 운동으로 화기 배출

[가정·인간관계 상세]
- 배우자운: 午 속 丁(정재=아내), 관계 돈독해지나 생활 패턴 변화 가능
- 자녀운: 식신(甲, 寅)이 午와 반합 → 자녀와 즐거운 시간
- 부친: 丙(편재=부친)이 강하게 들어오는 해 → 아버지 관련 소식 가능
"""

# ─── 월별 운세 ───────────────────────────────────────────
MONTHLY_FORTUNE = {
    1: {"간지": "庚寅", "등급": 3, "별점": "★★★☆☆",
        "운세": "편인+식신. 이직 준비·학습 몰두에 좋은 달. 자기계발 집중"},
    2: {"간지": "辛卯", "등급": 4, "별점": "★★★★☆",
        "운세": "정인+상관. 면접·발표에 유리. 새로운 아이디어 돋보이는 시기. 말실수 주의"},
    3: {"간지": "壬辰", "등급": 3, "별점": "★★★☆☆",
        "운세": "비견+편관. 경쟁자 출현 가능. 강점을 명확히 어필해야 하는 달"},
    4: {"간지": "癸巳", "등급": 4, "별점": "★★★★☆",
        "운세": "겁재+정재. 가족여행에 좋은 기운. 소비 지출 크지만 즐거움도 큼"},
    5: {"간지": "甲午", "등급": 5, "별점": "★★★★★",
        "운세": "식신+정재. 올해 최대 기회월. 취업 확정·계약 체결에 가장 유리. 투자는 보수적으로"},
    6: {"간지": "乙未", "등급": 3, "별점": "★★★☆☆",
        "운세": "상관+편관. 새 직장 적응기. 조직 내 갈등 소지 있으나 실력으로 극복"},
    7: {"간지": "丙申", "등급": 5, "별점": "★★★★★",
        "운세": "편재+편인. 시주 申과 공명. 두 번째 기회월. 재물 유입 또는 보너스 가능"},
    8: {"간지": "丁酉", "등급": 4, "별점": "★★★★☆",
        "운세": "정재+정인. 대운 酉와 겹쳐 안정감 최대. 학습·자격 취득에 최적"},
    9: {"간지": "戊戌", "등급": 3, "별점": "★★★☆☆",
        "운세": "편관+편관. 시주 戊와 중복. 업무 압박 강하지만 성과 확실. 건강 관리 필수"},
    10: {"간지": "己亥", "등급": 2, "별점": "★★☆☆☆",
         "운세": "정관+겁재. 亥-巳 충 발생. 직장 내 변동 또는 조직 개편 소식. 침착 대응"},
    11: {"간지": "庚子", "등급": 2, "별점": "★★☆☆☆",
         "운세": "편인+겁재. 年지 子 활성화 + 午-子 충 재발동. 재물 변동 큼. 투자 매매 자제"},
    12: {"간지": "辛丑", "등급": 4, "별점": "★★★★☆",
         "운세": "정인+편관. 한 해 마무리. 丑이 금의 고(庫)로 재물을 모아두는 기운. 저축·정리에 좋음"},
}

WEEKDAY_KR = {
    "Monday": "월요일", "Tuesday": "화요일", "Wednesday": "수요일",
    "Thursday": "목요일", "Friday": "금요일", "Saturday": "토요일",
    "Sunday": "일요일",
}

# ─── 시스템 프롬프트 ──────────────────────────────────────
SYSTEM_PROMPT = f"""당신은 '나의 운세' — 전문 사주 상담가입니다. 한국어로 대화합니다.

## 역할
- 아래 사주 데이터를 기반으로 운세 상담을 제공합니다
- 사주 원국, 대운, 세운의 상호작용을 분석하여 답변합니다
- 따뜻하면서도 솔직한 조언을 제공합니다 (무조건 좋은 말만 하지 않음)
- 구체적인 사주 용어를 사용하되 쉬운 설명을 덧붙입니다
- 건강, 재물, 직업, 인간관계, 이직, 면접 등 다양한 영역에 답변합니다

## 답변 스타일
- 텔레그램 메시지에 맞게 간결하되 핵심은 빠짐없이
- 이모지를 적절히 사용하여 가독성 향상
- 아부 금지, 솔직한 조언
- 질문에 맞는 사주 근거를 간단히 제시
- 주의사항이 있으면 반드시 언급
- 한자 용어를 사용할 때는 반드시 쉬운 한글 뜻풀이를 괄호로 덧붙여주세요
  예: 충(衝, 정면 충돌), 합(合, 조화·결합), 식신(食神, 창작·표현의 기운),
  편관(偏官, 압박·권위), 정재(正財, 안정적 수입), 12운성의 관대(冠帶, 관모를 쓰는 성장기) 등

{SAJU_DATA}"""


# ─── 대화 히스토리 ────────────────────────────────────────
chat_history: dict[int, list[str]] = {}
MAX_HISTORY = 10


# ─── 권한 체크 ────────────────────────────────────────────
def is_authorized(chat_id: int) -> bool:
    if ALLOWED_CHAT_ID == 0:
        return True
    return chat_id == ALLOWED_CHAT_ID


# ─── 현재 월 운세 컨텍스트 ─────────────────────────────────
def get_month_context() -> str:
    """현재 월의 운세 데이터를 텍스트로 반환."""
    now = datetime.now(KST)
    month = now.month
    data = MONTHLY_FORTUNE.get(month)
    if not data:
        return ""
    return (
        f"\n\n━━━ {now.year}년 {month}월 운세 ({data['간지']}월) ━━━\n"
        f"등급: {data['별점']}\n"
        f"운세: {data['운세']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )


# ─── Claude Sonnet API (정기 브리핑용) ────────────────────
def _ask_claude_sync(prompt: str) -> str:
    """Claude Sonnet 동기 호출 (내부용)."""
    try:
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        log.error(f"Claude API 오류: {e}")
        return f"운세 생성 중 오류가 발생했습니다: {e}"


async def ask_claude(prompt: str) -> str:
    """Claude Sonnet 비동기 래핑 — 이벤트 루프 차단 방지."""
    return await asyncio.to_thread(_ask_claude_sync, prompt)


# ─── Gemini API (대화형 채팅용) ───────────────────────────
def _ask_gemini_sync(chat_id: int, user_message: str) -> str:
    """Gemini 3 Flash 동기 호출 (내부용)."""
    history = chat_history.get(chat_id, [])
    history.append(f"사용자: {user_message}")
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    month_context = get_month_context()
    now = datetime.now(KST)
    date_info = f"\n현재: {now.strftime('%Y년 %m월 %d일 %A %H:%M')} KST"
    daily_analysis = get_daily_analysis(now.date())

    context = "\n".join(history)
    user_prompt = (
        f"{SYSTEM_PROMPT}{month_context}{date_info}\n\n"
        f"━━━ 오늘의 일진 ━━━\n{daily_analysis}\n━━━━━━━━━━━━━━━\n\n"
        f"대화 기록:\n{context}\n\n"
        f"위 대화의 마지막 사용자 메시지에 답변해주세요. 일진 데이터를 참고하여 답변하세요."
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
        log.error(f"Gemini API 오류: {e}")
        return f"오류가 발생했습니다: {e}"


async def ask_gemini(chat_id: int, user_message: str) -> str:
    """Gemini 3 Flash 비동기 래핑."""
    return await asyncio.to_thread(_ask_gemini_sync, chat_id, user_message)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  정기 운세 브리핑 생성 (Claude Sonnet)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def generate_daily_fortune() -> str:
    """매일 아침 자동 전송용 일간 운세 (Claude Sonnet)."""
    now = datetime.now(KST)
    month_data = MONTHLY_FORTUNE.get(now.month, {})
    day_name = WEEKDAY_KR.get(now.strftime("%A"), "")

    # 오늘의 일진 분석
    daily_analysis = get_daily_analysis(now.date())

    prompt = f"""{SYSTEM_PROMPT}

━━━ {now.year}년 {now.month}월 운세 ({month_data.get('간지', '')}월) ━━━
등급: {month_data.get('별점', '')}
운세: {month_data.get('운세', '')}
━━━━━━━━━━━━━━━━━━━━━

━━━ 오늘의 일진 분석 ━━━
{daily_analysis}
━━━━━━━━━━━━━━━━━━━━━

오늘은 {now.year}년 {now.month}월 {now.day}일 {day_name}입니다.

위 일진 데이터를 반드시 활용하여 오늘의 운세를 작성해주세요.
특히 일진의 십성, 12운성, 원국과의 충·합 관계, 발동하는 신살을 근거로 제시해야 합니다.

첫 줄은 반드시 아래 타이틀로 시작:

☀️ 【일간 운세】 {now.month}월 {now.day}일 {day_name}

그 다음:
1. 오늘의 총운 (일진 × 사주 원국 × 이달 운세의 삼중 분석, 3~4줄)
2. 💼 직업운 (일진의 십성이 직업에 미치는 영향)
3. 💰 재물운 (일진의 재성·인성 여부에 따른 판단)
4. 💪 건강운 (12운성 에너지 상태 반영)
5. 👥 인간관계 (충·합에 따른 대인 관계)
6. 🎯 오늘의 조언 (일진 기반 구체적 행동 가이드 1~2줄)
7. 🍀 오늘의 개운 포인트 (색상/방위/숫자)

간결하되 일진 근거를 반드시 곁들여 작성해주세요."""

    return await ask_claude(prompt)


async def generate_weekly_fortune() -> str:
    """매주 월요일 자동 전송용 주간 운세 (Claude Sonnet)."""
    now = datetime.now(KST)
    month_data = MONTHLY_FORTUNE.get(now.month, {})

    # 이번 주 날짜 범위 계산
    week_start = now
    week_end = now + timedelta(days=6)

    # 이번 주 7일간 일진 흐름
    week_analysis = get_week_analysis(now.date())

    prompt = f"""{SYSTEM_PROMPT}

━━━ {now.year}년 {now.month}월 운세 ({month_data.get('간지', '')}월) ━━━
등급: {month_data.get('별점', '')}
운세: {month_data.get('운세', '')}
━━━━━━━━━━━━━━━━━━━━━

━━━ 이번 주 일진 흐름 ━━━
{week_analysis}
━━━━━━━━━━━━━━━━━━━━━

이번 주는 {week_start.month}월 {week_start.day}일 ~ {week_end.month}월 {week_end.day}일입니다.

위 일진 데이터를 반드시 활용하여 주간 운세를 작성해주세요.
각 요일의 십성·12운성·충합 관계를 근거로 요일별 강약을 분석해야 합니다.

첫 줄은 반드시 아래 타이틀로 시작:

📅 【주간 운세】 {week_start.month}/{week_start.day} ~ {week_end.month}/{week_end.day}

그 다음:
1. 이번 주 총운 (일진 흐름 패턴 + 사주 원국 + 이달 운세 기반, 4~5줄)
2. 💼 직업운 — 일진 기반 요일별 강약 (충 있는 날 주의, 합 있는 날 활용)
3. 💰 재물운 — 재성이 들어오는 요일 vs 주의해야 할 요일
4. 💪 건강운 — 12운성 흐름에 따른 컨디션 변화
5. 👥 인간관계 — 도화·귀인 등 신살 발동일 활용
6. 📊 요일별 운세 한줄 요약 (월~일, 일진과 핵심 포인트)
7. 🎯 이번 주 핵심 조언 (2~3줄)
8. 🍀 주간 개운법 (색상/방위/활동)

일간 운세보다 넓은 시야로 한 주를 조망하되, 일진 근거를 반드시 곁들여주세요."""

    return await ask_claude(prompt)


async def generate_monthly_fortune() -> str:
    """매월 1일 자동 전송용 월간 운세 (Claude Sonnet)."""
    now = datetime.now(KST)
    month = now.month
    month_data = MONTHLY_FORTUNE.get(month, {})

    # 이전/다음 달 데이터 (흐름 분석용)
    prev_data = MONTHLY_FORTUNE.get(month - 1 if month > 1 else 12, {})
    next_data = MONTHLY_FORTUNE.get(month + 1 if month < 12 else 1, {})

    prompt = f"""{SYSTEM_PROMPT}

━━━ {now.year}년 {month}월 운세 ({month_data.get('간지', '')}월) ━━━
등급: {month_data.get('별점', '')}
운세: {month_data.get('운세', '')}

지난달({prev_data.get('간지', '')}월): {prev_data.get('운세', '')}
다음달({next_data.get('간지', '')}월): {next_data.get('운세', '')}
━━━━━━━━━━━━━━━━━━━━━

오늘은 {now.year}년 {month}월 1일, 새로운 달의 시작입니다.

아래 형식으로 이번 달 운세를 작성해주세요.
첫 줄은 반드시 아래 타이틀로 시작:

🌙 【월간 운세】 {now.year}년 {month}월 ({month_data.get('간지', '')}월)

그 다음:
1. 이달의 총운 (사주 원국 × 월간지 × 세운의 삼중 상호작용 깊이 분석, 5~6줄)
2. 💼 직업운 — 이직/적응/업무 성과 + 핵심 전략
3. 💰 재물운 — 수입/지출/투자 전략 + 구체적 주의사항
4. 💪 건강운 — 주의 부위 + 구체적 생활 조언
5. 👥 인간관계 — 가족/동료/새로운 인연 + 귀인 방향
6. 📊 주차별 운세 (1주~4주, 각 2~3줄씩)
7. ⚠️ 특히 주의할 날짜/시기와 그 이유
8. 🎯 이달의 핵심 조언 (3~4줄)
9. 🍀 이달의 개운법 (색상/방위/활동/음식)

지난달에서 이번 달로의 흐름 변화, 다음 달을 대비한 포석도 언급해주세요.
일간·주간 운세보다 훨씬 깊고 넓은 시야로 한 달을 조망하는 관점에서 작성해주세요.
사주 근거를 충분히 제시하되 텔레그램 메시지에 적합한 분량으로 작성해주세요."""

    return await ask_claude(prompt)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  텔레그램 메시지 전송 헬퍼
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def send_long_message(bot, chat_id: int, text: str) -> None:
    """4000자 초과 메시지를 분할 전송."""
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await bot.send_message(chat_id=chat_id, text=text[i : i + 4000])
    else:
        await bot.send_message(chat_id=chat_id, text=text)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  스케줄러 콜백
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def scheduled_daily(context: ContextTypes.DEFAULT_TYPE) -> None:
    """매일 08:00 KST — 일간 운세 전송."""
    now = datetime.now(KST)

    # 월요일이면 주간 운세도 함께 전송
    if now.weekday() == 0:  # Monday
        try:
            log.info("📅 주간 운세 생성 시작 (Claude Sonnet)...")
            weekly = await generate_weekly_fortune()
            await send_long_message(context.bot, ALLOWED_CHAT_ID, weekly)
            log.info("📅 주간 운세 전송 완료")
        except Exception as e:
            log.error(f"주간 운세 전송 실패: {e}")

    # 매월 1일이면 월간 운세도 함께 전송
    if now.day == 1:
        try:
            log.info("🌙 월간 운세 생성 시작 (Claude Sonnet)...")
            monthly = await generate_monthly_fortune()
            await send_long_message(context.bot, ALLOWED_CHAT_ID, monthly)
            log.info("🌙 월간 운세 전송 완료")
        except Exception as e:
            log.error(f"월간 운세 전송 실패: {e}")

    # 일간 운세는 항상 전송
    try:
        log.info("☀️ 일간 운세 생성 시작 (Claude Sonnet)...")
        daily = await generate_daily_fortune()
        await send_long_message(context.bot, ALLOWED_CHAT_ID, daily)
        log.info("☀️ 일간 운세 전송 완료")
    except Exception as e:
        log.error(f"일간 운세 전송 실패: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  커맨드 핸들러
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.reply_text(
        "🔮 나의 운세 봇입니다!\n\n"
        "사주 원국(壬寅일 戊申시) 기반으로 운세 상담을 해드립니다.\n\n"
        "📨 정기 브리핑 (Claude Sonnet 4.6)\n"
        "  • ☀️ 일간 운세 — 매일 08:00\n"
        "  • 📅 주간 운세 — 매주 월요일 08:00\n"
        "  • 🌙 월간 운세 — 매월 1일 08:00\n\n"
        "💬 자유 대화 (Gemini 3 Flash)\n"
        "  아무 질문이나 보내주세요!\n\n"
        "명령어:\n"
        "/fortune — ☀️ 오늘의 운세\n"
        "/week — 📅 이번 주 운세\n"
        "/month — 🌙 이번 달 운세\n"
        "/clear — 대화 기록 초기화\n"
        "/help — 도움말"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_chat.id):
        return
    chat_history.pop(update.effective_chat.id, None)
    await update.message.reply_text("🔄 대화 기록이 초기화되었습니다.")


async def cmd_fortune(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """☀️ 즉석 일간 운세."""
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.chat.send_action("typing")
    fortune = await generate_daily_fortune()
    await send_long_message(context.bot, update.effective_chat.id, fortune)


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """📅 즉석 주간 운세."""
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.chat.send_action("typing")
    fortune = await generate_weekly_fortune()
    await send_long_message(context.bot, update.effective_chat.id, fortune)


async def cmd_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🌙 즉석 월간 운세."""
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.chat.send_action("typing")
    fortune = await generate_monthly_fortune()
    await send_long_message(context.bot, update.effective_chat.id, fortune)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_chat.id):
        return
    await update.message.reply_text(
        "🔮 사용 가능한 명령어:\n\n"
        "/start — 봇 시작\n"
        "/fortune — ☀️ 오늘의 운세 (Sonnet)\n"
        "/week — 📅 이번 주 운세 (Sonnet)\n"
        "/month — 🌙 이번 달 운세 (Sonnet)\n"
        "/clear — 대화 기록 초기화\n"
        "/help — 이 도움말\n\n"
        "📨 정기 브리핑 스케줄:\n"
        "  ☀️ 일간 — 매일 08:00\n"
        "  📅 주간 — 매주 월요일 08:00\n"
        "  🌙 월간 — 매월 1일 08:00\n\n"
        "💬 자유롭게 질문하시면 사주 기반으로 상담합니다."
    )


# ─── 메시지 핸들러 (Gemini 3 Flash) ──────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not is_authorized(update.effective_chat.id):
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text
    log.info(f"[{chat_id}] 수신: {user_text[:50]}")

    await update.message.chat.send_action("typing")
    reply = await ask_gemini(chat_id, user_text)

    if len(reply) > 4000:
        for i in range(0, len(reply), 4000):
            await update.message.reply_text(reply[i : i + 4000])
    else:
        await update.message.reply_text(reply)

    log.info(f"[{chat_id}] 응답: {reply[:50]}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  메인
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> None:
    now = datetime.now(KST)
    log.info(f"🔮 나의 운세 봇 시작 — {now.strftime('%Y-%m-%d %H:%M:%S KST')}")
    log.info("브리핑: Claude Sonnet 4.6 | 채팅: Gemini 3 Flash")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # 커맨드 핸들러
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("fortune", cmd_fortune))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("month", cmd_month))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 매일 08:00 KST 스케줄 (일간 + 조건부 주간/월간)
    job_queue = app.job_queue
    target_time = dt_time(hour=8, minute=0, second=0, tzinfo=KST)
    job_queue.run_daily(scheduled_daily, time=target_time, name="daily_fortune")
    log.info("📅 스케줄 등록: 매일 08:00 KST (일간 + 월요일 주간 + 1일 월간)")

    log.info("폴링 시작...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
