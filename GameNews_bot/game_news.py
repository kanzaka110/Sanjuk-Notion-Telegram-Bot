"""
🎮 게임뉴스 데일리 브리핑
━━━━━━━━━━━━━━━━━━━━━━━
Claude CLI (WebSearch 수집 + 분석)
매일 아침 9시 KST 텔레그램 전송

환경변수:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import html
import os
import re
import sys
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# shared_config에서 Claude CLI 유틸리티 로드
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared_config import claude_cli

# ─── 설정 ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("GAME_NEWS_BOT_TOKEN", os.environ.get("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
KST = timezone(timedelta(hours=9))


# ─── 뉴스 수집 (Claude CLI + WebSearch) ─────────────────
def fetch_news() -> str:
    """Claude CLI + WebSearch로 게임 뉴스 수집."""
    now = datetime.now(KST)
    today = now.strftime("%Y년 %m월 %d일")
    today_iso = now.strftime("%Y-%m-%d")
    today_dot = now.strftime("%Y.%m.%d")
    gather_prompt = f"""오늘은 {today} ({today_iso})입니다.

반드시 오늘({today_iso}) 게시된 게임 뉴스만 검색하세요.
어제({(now - timedelta(days=1)).strftime('%Y-%m-%d')}) 이전 기사는 절대 포함하지 마세요.

다음 검색어들을 각각 검색하세요. 검색 시 날짜를 포함하여 당일 기사만 찾으세요:

검색어 1: 게임 뉴스 {today_iso}
검색어 2: 넥슨 엔씨소프트 크래프톤 넷마블 {today_dot}
검색어 3: gaming news {today_iso}
검색어 4: Nintendo Sony Microsoft Xbox news {today_iso}
검색어 5: 신작 게임 출시 {today_dot}
검색어 6: e스포츠 대회 결과 {today_dot}
검색어 7: Steam 인기 게임 {today_dot}
검색어 8: 시프트업 김형태 스텔라블레이드 {today_dot}
검색어 9: SHIFT UP Stellar Blade {today_iso}

각 검색 결과마다 반드시 아래 형식으로 작성하세요. 최소 15개 이상 기사를 나열해주세요:

기사번호: [1부터 순서대로]
제목: [기사 제목 — 검색 결과에 나온 원본 제목 그대로]
URL: [실제 기사 URL — 검색 결과의 원본 링크 그대로]
출처: [매체명]
게시일: [기사 게시 날짜 — YYYY-MM-DD 형식]
요약: [한 줄 요약]

---

⚠️ 필수 규칙:
- 게시일이 {today_iso}인 기사만 포함. 그 외 날짜는 전부 제외
- 게시일을 확인할 수 없는 기사도 제외
- URL은 반드시 실제 검색에서 나온 원본 링크. URL을 만들어내지 마세요
- 제목과 URL이 반드시 같은 기사를 가리켜야 합니다"""

    result = claude_cli(gather_prompt, model="opus", web_search=True, timeout=600, effort="max")
    return result or "(검색 결과 없음)"


# ─── Claude CLI로 정리 ──────────────────────────────────
def summarize_news(gathered_text: str) -> str:
    now = datetime.now(KST)
    today = now.strftime("%Y년 %m월 %d일")
    today_iso = now.strftime("%Y-%m-%d")

    prompt = f"""오늘은 {today} ({today_iso})입니다.
아래 수집 결과에서 게시일이 {today_iso}인 기사만 골라서 정리해주세요.

━━━ 수집된 뉴스 ━━━
{gathered_text}

출력 형식 (그대로 출력):

⭐ 시프트업 (SHIFT UP)

▸ <a href="URL">기사 제목</a>

🏢 게임회사

▸ <a href="URL">기사 제목</a>

🎮 게임

▸ <a href="URL">기사 제목</a>

📌 한 줄 요약

규칙:
- 게시일이 {today_iso}인 기사만 포함. 어제 이전 기사는 전부 제외
- 한국어, 게임회사/게임 카테고리는 최대 5개
- ⭐ 시프트업 섹션: 시프트업, 김형태 대표, 스텔라 블레이드 관련 기사. 없으면 "오늘 관련 기사 없음"
- 수집된 기사가 1개라도 있으면 반드시 출력. 생략하지 말 것
- 제목만 한 줄로 (요약 불필요)
- 각 기사 사이에 반드시 빈 줄 하나
- ⚠️ URL 규칙:
  - 수집 결과에 있는 URL만 사용할 것
  - URL을 만들거나 추측하지 말 것
- URL이 없는 뉴스는 제외
- 중복 제거"""

    raw = claude_cli(prompt, model="opus", timeout=180, effort="max")
    if not raw:
        return "뉴스 정리에 실패했습니다."
    # <a> 태그 내 텍스트의 HTML 특수문자 이스케이프
    def _escape_link_text(m: re.Match) -> str:
        return f'{m.group(1)}{html.escape(m.group(2))}</a>'
    return re.sub(r'(<a\s+href="[^"]*">)(.*?)</a>', _escape_link_text, raw)


# ─── 텔레그램 전송 ────────────────────────────────────
def send_telegram(text: str) -> None:
    today = datetime.now(KST).strftime("%Y.%m.%d")
    msg = f"🎮 게임뉴스 데일리\n{today} 아침 브리핑\n\n{text}"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
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

    # 1. Claude CLI로 뉴스 수집
    print("🔍 Claude CLI + WebSearch로 게임 뉴스 수집...")
    gathered = fetch_news()
    print(f"  → 수집 완료 ({len(gathered)}자)\n")

    if not gathered or gathered == "(검색 결과 없음)":
        print("❌ 뉴스를 찾지 못했습니다.")
        send_telegram("오늘은 수집된 게임 뉴스가 없습니다.")
        return

    # 2. Claude CLI로 정리
    print("🤖 Claude CLI로 정리 중...")
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
