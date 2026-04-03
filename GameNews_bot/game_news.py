"""
🎮 게임뉴스 데일리 브리핑
━━━━━━━━━━━━━━━━━━━━━━━
Gemini 3.1 Pro (Google Search 수집) + Claude Sonnet 4.6 (분석)
매일 아침 9시 KST 텔레그램 전송

환경변수:
  GEMINI_API_KEY, CLAUDE_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta

from google import genai
from google.genai import types as genai_types
import anthropic

# ─── 설정 ──────────────────────────────────────────────
GEMINI_API_KEY     = os.environ["GEMINI_API_KEY"]
CLAUDE_API_KEY     = os.environ.get("CLAUDE_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
KST = timezone(timedelta(hours=9))
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# ─── 뉴스 수집 (Gemini 3.1 Pro + Google Search) ──────
def fetch_news_with_gemini() -> str:
    """Gemini 3.1 Pro + Google Search로 게임 뉴스 수집."""
    today = datetime.now(KST).strftime("%Y년 %m월 %d일")
    gather_prompt = f"""오늘({today}) 게임 관련 뉴스를 Google에서 검색하세요.

⚠️ 중요: 반드시 오늘({today}) 게시된 기사만 수집하세요.
어제 이전에 게시된 기사는 절대 포함하지 마세요.
검색 결과에서 기사의 게시 날짜를 확인하고, 오늘 날짜가 아닌 기사는 제외하세요.

다음 검색어들을 각각 검색하고, 오늘 게시된 기사만 나열해주세요:

검색어 1: "게임 뉴스 오늘" (한국어 뉴스)
검색어 2: "넥슨 엔씨소프트 크래프톤 넷마블 뉴스"
검색어 3: "gaming news today 2026"
검색어 4: "Nintendo Sony Microsoft Xbox news"
검색어 5: "신작 게임 출시 2026"
검색어 6: "e스포츠 대회 결과"
검색어 7: "Steam 인기 게임 신작"

각 검색 결과마다 반드시 아래 형식으로 작성하세요. 최소 15개 이상 기사를 나열해주세요:

기사번호: [1부터 순서대로]
제목: [기사 제목 — 검색 결과에 나온 원본 제목 그대로]
URL: [실제 기사 URL — 검색 결과의 원본 링크 그대로]
출처: [매체명]
게시일: [기사 게시 날짜]
요약: [한 줄 요약]

---

⚠️ 필수 규칙:
- URL은 반드시 실제 검색에서 나온 원본 링크여야 합니다. 절대로 URL을 생략하거나 만들어내지 마세요.
- 제목과 URL이 반드시 같은 기사를 가리켜야 합니다. 제목은 A기사인데 URL은 B기사인 경우가 없도록 하세요.
- 오늘({today}) 게시된 기사가 아니면 제외하세요."""

    google_search_tool = genai_types.Tool(google_search=genai_types.GoogleSearch())
    response = gemini_client.models.generate_content(
        model="gemini-2.5-pro",
        contents=gather_prompt,
        config=genai_types.GenerateContentConfig(
            tools=[google_search_tool],
            max_output_tokens=8000,
        ),
    )

    # Gemini 텍스트 응답
    result_text = response.text.strip()

    # grounding_metadata에서 실제 검색 결과 URL 추출
    grounding_urls = []
    try:
        for candidate in response.candidates:
            gm = getattr(candidate, "grounding_metadata", None)
            if not gm:
                continue
            chunks = getattr(gm, "grounding_chunks", None) or []
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                if web and getattr(web, "uri", None):
                    title = getattr(web, "title", "") or ""
                    grounding_urls.append(f"[검증된 URL] 제목: {title} | URL: {web.uri}")
    except Exception as e:
        print(f"  ⚠️ grounding metadata 추출 실패: {e}")

    if grounding_urls:
        url_section = "\n".join(grounding_urls)
        result_text += f"\n\n━━━ Google Search 검증된 URL 목록 ━━━\n{url_section}"
        print(f"  📎 검증된 URL {len(grounding_urls)}개 추출")

    return result_text


# ─── Claude Sonnet으로 정리 ──────────────────────────
def summarize_news(gathered_text: str) -> str:
    today = datetime.now(KST).strftime("%Y년 %m월 %d일")

    prompt = f"""오늘({today}) 게임 뉴스를 아래 수집 결과를 바탕으로 정리해주세요.

━━━ 수집된 뉴스 ━━━
{gathered_text}

출력 형식 (그대로 출력):

🏢 게임회사

▸ 기사 제목 한 줄
URL
▸ 기사 제목 한 줄
URL

🎮 게임

▸ 기사 제목 한 줄
URL
▸ 기사 제목 한 줄
URL

📌 한 줄 요약

규칙:
- 한국어, 각 카테고리 최대 5개 (5개 미만이면 있는 만큼 모두 출력)
- 수집된 기사가 1개라도 있으면 반드시 출력할 것. 갯수가 부족하다고 생략하지 말 것
- 제목만 한 줄로 (요약 불필요)
- ⚠️ 오늘({today}) 게시된 기사만 포함. 어제 이전 기사는 반드시 제외
- ⚠️ URL 규칙 (가장 중요):
  - "Google Search 검증된 URL 목록"이 있으면, 반드시 그 목록의 URL만 사용할 것
  - 검증된 URL 목록의 제목과 URL 쌍을 그대로 사용할 것
  - 검증된 URL 목록에 없는 URL은 절대 사용하지 말 것
  - URL을 임의로 만들거나 추측하지 말 것
  - URL을 수정하거나 다른 URL로 대체하지 말 것
- URL이 없는 뉴스는 제외
- 중복 제거"""

    response = claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ─── 텔레그램 전송 ────────────────────────────────────
def send_telegram(text: str) -> None:
    today = datetime.now(KST).strftime("%Y.%m.%d")
    msg = f"🎮 게임뉴스 데일리\n{today} 아침 브리핑\n\n{text}"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "disable_web_page_preview": True,
    }

    # 텔레그램 4096자 제한
    if len(msg) > 4000:
        for i in range(0, len(msg), 4000):
            chunk_payload = {**payload, "text": msg[i:i + 4000]}
            requests.post(url, json=chunk_payload, timeout=30)
    else:
        res = requests.post(url, json=payload, timeout=30)
        if res.status_code == 200:
            print("  ✅ 텔레그램 전송 완료")
        else:
            print(f"  ⚠️ 전송 실패: {res.status_code} {res.text[:200]}")


# ─── 메인 ─────────────────────────────────────────────
def main():
    now = datetime.now(KST)
    print(f"\n{'='*50}")
    print(f"🎮 게임뉴스 데일리 브리핑")
    print(f"🕐 {now.strftime('%Y-%m-%d %H:%M:%S KST')}")
    print(f"{'='*50}\n")

    # 1. Gemini로 뉴스 수집
    print("🔍 Gemini 3.1 Pro — Google Search로 게임 뉴스 수집...")
    gathered = fetch_news_with_gemini()
    print(f"  → 수집 완료 ({len(gathered)}자)\n")

    if not gathered or gathered == "(검색 결과 없음)":
        print("❌ 뉴스를 찾지 못했습니다.")
        send_telegram("오늘은 수집된 게임 뉴스가 없습니다.")
        return

    # 2. Sonnet으로 정리
    print("🤖 Claude Sonnet 4.6으로 정리 중...")
    summary = summarize_news(gathered)
    print(f"  → 정리 완료 ({len(summary)}자)\n")

    # 3. 텔레그램 전송
    print("📨 텔레그램 전송...")
    send_telegram(summary)

    print(f"\n{'='*50}")
    print("  ✅ 게임뉴스 브리핑 완료!")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
