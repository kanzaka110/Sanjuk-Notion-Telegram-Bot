# 📊 투자 브리핑 자동화 시스템

매일 스케줄에 따라 한국장/미국장 시작 전후 투자 브리핑을 자동 생성하여
Notion 데이터베이스에 저장합니다.

---

## 📂 프로젝트 위치

| 항목 | 경로 / URL |
|------|-----------|
| **로컬 코드** | `C:\dev\Sanjuk-Notion-Telegram-Bot\Stock_bot\` |
| **GitHub repo** | `kanzaka110/Sanjuk-Notion-Telegram-Bot` (Stock_bot/) |
| **Notion 브리핑 DB** | [📊 AI 투자 브리핑](https://www.notion.so/329d934c75b380158283d74a60c51d51) |
| **Notion 포트폴리오 DB** | `2a1d934c-75b3-8146-8087-fe82dce5dc49` (Sanjuk 나의 투자 현황) |

---

## 📁 핵심 파일 구조

```
Sanjuk-Notion-Telegram-Bot/
├── .github/workflows/
│   └── briefing.yml                 ← GitHub Actions (4개 스케줄)
├── Stock_bot/
│   ├── scripts/
│   │   ├── briefing.py              ← 메인 브리핑 스크립트 (Claude API + yfinance + Notion)
│   │   └── fix_briefing_labels.py   ← 기존 브리핑 구분 라벨 일괄 수정
│   ├── update_price.py              ← 주가 업데이트
│   └── requirements.txt             ← yfinance, requests, ddgs, duckduckgo-search
```

---

## 🚀 실행 방법

### Claude Code에서 바로 실행

```bash
export PATH="/c/Program Files/GitHub CLI:$PATH"
GH_TOKEN="<토큰>" gh workflow run briefing.yml \
  --repo kanzaka110/Sanjuk-Notion-Telegram-Bot -f briefing_type=US_BEFORE
```

### 브리핑 타입

| 타입 | 설명 | KST | UTC |
|------|------|-----|-----|
| `KR_BEFORE` | 국내장 시작 전 | 08:30 | 23:30 (전날) |
| `KR_AFTER` | 국내장 마감 후 | 15:30 | 06:30 |
| `US_BEFORE` | 미국장 시작 전 | 22:30 | 13:30 (EST) |
| `US_AFTER` | 미국장 마감 후 | 06:30 | 21:30 (EST) |
| `MANUAL` | 수동 브리핑 | - | - |

### 자동 스케줄 (cron)

```
30 23 * * 0-4   → KR_BEFORE (KST 08:30)
30 6  * * 1-5   → KR_AFTER  (KST 15:30)
30 13 * * 1-5   → US_BEFORE (KST 22:30, EST 기준)
30 21 * * 1-5   → US_AFTER  (KST 06:30, EST 기준)
```

> ※ 서머타임(3~11월)에는 US 시간이 1시간 앞당겨짐

---

## 📋 포트폴리오 종목

### 🇰🇷 국내

| 티커 | 종목명 |
|------|--------|
| 005930.KS | 삼성전자 |
| 012450.KS | 한화에어로스페이스 |
| 133690.KS | TIGER 미국나스닥100 |
| 360750.KS | TIGER 미국S&P500 |
| 251350.KS | KODEX MSCI선진국 |
| 161510.KS | PLUS 고배당주 |
| 329200.KS | TIGER 리츠부동산인프라 |
| 192090.KS | TIGER 차이나CSI300 |

### 🇺🇸 미국

| 티커 | 종목명 |
|------|--------|
| NVDA | 엔비디아 |
| GOOGL | 구글(알파벳A) |
| MU | 마이크론 |
| LMT | 록히드마틴 |

### 📈 지수 & 매크로

- KOSPI, KOSDAQ, S&P500, NASDAQ, DOW
- 브렌트유, WTI, 원달러, VIX, 미10년국채, 금

---

## 🔧 브리핑 생성 과정

```
[1] yfinance로 포트폴리오 시세 + 지수 + 매크로 데이터 수집
[2] DuckDuckGo 검색으로 최신 뉴스 수집
[3] Claude API로 종합 분석 + 매수/매도 전략 생성
[4] Notion 페이지 생성 (상태 배지, 가격 카드, 신호 강도 바)
```

---

## 🔑 GitHub Secrets (등록 완료)

| Secret | 용도 |
|--------|------|
| `CLAUDE_API_KEY` | Claude API |
| `NOTION_API_KEY` | Notion 통합 토큰 |
| `NOTION_DB_ID` | 브리핑 DB (`329d934c75b380158283d74a60c51d51`) |

---

## 🛠️ 유지보수 기록

### 2026-03-25: 브리핑 구분 수정
- US_BEFORE/US_AFTER cron 시간 수정 (실제 미국장 시간에 맞춤)
- `fix_briefing_labels.py`로 기존 17개 페이지 중 9개 라벨 재분류
- 브리핑 타입 판별 로직에 서머타임 대응 (hour 12/20 추가)

---

## ⚠️ 주의사항

- Notion DB에 **"주식 분석 봇" 통합이 연결**되어 있어야 함
- 브리핑 DB ID (`329d934c...`)와 포트폴리오 DB ID (`2a1d934c...`)는 다름 — 혼동 주의
- GitHub PAT, Notion 토큰 노출 시 즉시 로테이션
- 서머타임 전환 시 US 브리핑 시간 확인 필요
