# 🎮 게임뉴스 데일리 봇 — 구현 내역

> 마지막 업데이트: 2026-03-26

---

## 구성 요약

| 항목 | 내용 |
|------|------|
| 봇 이름 | 게임뉴스 |
| 사용자명 | @Sanjuk_GameNews_bot |
| 스케줄 | 매일 09:00 KST |
| 검색 | DuckDuckGo (무료) |
| 요약 | Claude Haiku (~$1~2/월) |

---

## 동작 흐름

```
GitHub Actions cron (매일 09:00 KST)
→ DuckDuckGo 뉴스 검색 (게임회사 + 게임 소식)
→ Claude Haiku로 정리 및 분류
→ 텔레그램 전송
```

## 검색 키워드

### 게임회사 관련
- 넥슨, 엔씨소프트, 크래프톤, 넷마블 주가
- Nintendo, Sony, Microsoft, Xbox
- EA, Ubisoft, Activision Blizzard
- 게임업계 실적, 투자, 인수합병

### 게임 관련
- 신작 게임 출시
- 게임 업데이트, 패치, 이벤트
- e스포츠 대회 결과
- Steam, Epic Games 인기 게임

## 메시지 형식

```
🎮 게임뉴스 데일리
2026.03.26 아침 브리핑

🏢 게임회사 소식

1. [넥슨 1분기 실적 서프라이즈]
   매출 1.2조원 달성, 전년 대비 15% 성장
   출처: 게임메카

2. ...

🎮 게임 소식

1. [엘든링 DLC 두 번째 확장팩 발표]
   프롬소프트웨어, 2026년 하반기 출시 예정
   출처: IGN

2. ...

📌 오늘의 핵심
넥슨 실적 서프라이즈로 게임주 전반 강세
```

---

## 인프라

### GitHub Secrets (kanzaka110/Sanjuk-Notion-Telegram-Bot)
| 이름 | 용도 |
|------|------|
| `ANTHROPIC_API_KEY` | Claude Haiku 요약 |
| `GAME_NEWS_BOT_TOKEN` | 게임뉴스 봇 전용 토큰 |
| `TELEGRAM_CHAT_ID` | 메시지 수신 대상 |

### 관련 파일
| 파일 | 용도 |
|------|------|
| `GameNews_bot/game_news.py` | 뉴스 수집 + 요약 + 전송 |
| `.github/workflows/game-news.yml` | 매일 09:00 KST 자동 실행 |

### 수동 실행
```bash
export PATH="/c/Program Files/GitHub CLI:$PATH"
gh workflow run game-news.yml --repo kanzaka110/Sanjuk-Notion-Telegram-Bot
```

---

## 비용

- DuckDuckGo 검색: 무료
- Claude Haiku 요약: ~$1~2/월 (1일 1회, 입출력 합계 ~3,000토큰)

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-03-26 | 게임뉴스 봇 신규 생성 |
