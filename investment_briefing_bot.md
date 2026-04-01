# 📊 투자 브리핑 텔레그램 봇 — 구현 내역

> 마지막 업데이트: 2026-03-26

---

## 구성 요약

| 기능 | 실행 환경 | AI 엔진 | 비용 |
|------|-----------|---------|------|
| 자동 브리핑 알림 | GitHub Actions | Anthropic API | API 사용량 |
| 대화형 챗봇 | 로컬 PC | Claude Max (CLI) | 무료 (구독 포함) |

---

## 1. 자동 브리핑 알림

### 동작 흐름
```
GitHub Actions cron → briefing.py 실행
→ yfinance 데이터 수집 → Claude API 분석
→ Notion 저장 → 텔레그램 요약 전송
```

### 스케줄 (KST)
| 브리핑 | 시간 | cron (UTC) |
|--------|------|-----------|
| 🇰🇷 국내장 시작 전 | 08:30 | `30 23 * * 0-4` |
| 🇺🇸 미국장 시작 전 | 22:30 | `30 13 * * 1-5` |

> 마감 후 브리핑(KR_AFTER, US_AFTER)은 2026-03-26 폐지

### 텔레그램 메시지 형식
```
📊 🇰🇷 국내장 시작 전
2026.03.26 08:30 — KOSPI +0.46%

💬 삼성전자 장초반 분할 진입 권장

🟢 매수
🔥강력 삼성전자
▸ ₩58,000~₩59,000 → ₩63,000(+8%) ✂ ₩56,000(-3.5%)

🔴 매도
🟠주의 마이크론
▸ 익절 $112(+5%) ✂ $100(-6%)

🎯 AI: 소액분할
▶ 장중 외국인 동향 확인 후 2차 진입

📋 Notion 상세보기
```

### 관련 파일
- `scripts/briefing.py` → `send_telegram()` 함수
- `.github/workflows/briefing.yml` → 스케줄 및 시크릿 전달

### 수동 실행
```bash
export PATH="/c/Program Files/GitHub CLI:$PATH"
gh workflow run briefing.yml --repo kanzaka110/Sanjuk-Notion-Telegram-Bot -f briefing_type=MANUAL
```

---

## 2. 대화형 챗봇 (Claude Max)

### 동작 흐름
```
텔레그램 메시지 수신 → telegram_bot.py (폴링)
→ claude --print (CLI) → 응답 → 텔레그램 전송
```

- Anthropic API 사용하지 않음 — Claude Max 구독으로 무료
- 로컬 PC에서만 실행 가능 (CLI 인증 필요)

### 실행 방법
```bash
set TELEGRAM_BOT_TOKEN=<봇토큰>
set TELEGRAM_CHAT_ID=<챗ID>
cd "C:\dev\Sanjuk-Notion-Telegram-Bot\Stock_bot"
python scripts/telegram_bot.py
```

### 봇 명령어
| 명령어 | 설명 |
|--------|------|
| `/start` | 봇 시작 인사 |
| `/clear` | 대화 기록 초기화 |
| `/help` | 도움말 |
| 일반 메시지 | Claude가 답변 |

### 설정
- 대화 히스토리: 메모리 내 최대 10턴
- 권한: TELEGRAM_CHAT_ID와 일치하는 사용자만 응답
- Claude 모델: sonnet (`--model sonnet`)

### 관련 파일
- `scripts/telegram_bot.py`

---

## 3. 인프라 정보

### GitHub Secrets
| 이름 | 용도 |
|------|------|
| `CLAUDE_API_KEY` | 브리핑 AI 분석 (Anthropic API) |
| `NOTION_API_KEY` | Notion 페이지 생성 |
| `NOTION_DB_ID` | Notion 데이터베이스 ID |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 인증 |
| `TELEGRAM_CHAT_ID` | 메시지 수신 대상 |

### GitHub Actions 워크플로우
| 파일 | 상태 | 용도 |
|------|------|------|
| `briefing.yml` | 활성 | 자동 브리핑 (cron) |
| `telegram-bot.yml` | 비활성 | 상시 봇 (로컬로 전환됨) |

### 프로젝트 경로
- 로컬: `C:\dev\Sanjuk-Notion-Telegram-Bot\Stock_bot`
- GitHub: `https://github.com/kanzaka110/Sanjuk-Notion-Telegram-Bot` (Stock_bot/)

---

## 4. 주의사항

- **봇 인스턴스 1개만**: 로컬 봇과 GitHub Actions 봇 동시 실행 시 409 Conflict 발생
- `telegram-bot.yml` 워크플로우는 비활성 상태 유지할 것
- 봇 토큰은 비밀번호와 같음 — 절대 공개 금지
- 브리핑 시간 감지: GitHub Actions cron 지연(최대 20분) 고려하여 시간 범위로 판별
  - `23` 또는 `00` UTC → KR_BEFORE
  - `12`, `13`, `14` UTC → US_BEFORE

---

## 5. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-03-26 | 텔레그램 브리핑 알림 연동 (`send_telegram()`) |
| 2026-03-26 | 마감 후 브리핑(KR_AFTER, US_AFTER) 폐지 |
| 2026-03-26 | cron 시간 감지 로직 범위 확장 (수시브리핑 오분류 수정) |
| 2026-03-26 | 대화형 챗봇 추가 — Claude Max CLI 기반 |
| 2026-03-26 | 텔레그램 메시지 매수/매도 전략 중심으로 간결화 |
