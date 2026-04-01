# 🎮 언리얼 튜토리얼 가이드 비서 — 구현 내역

> 마지막 업데이트: 2026-03-26

---

## 구성 요약

| 기능 | 실행 환경 | AI 엔진 | 비용 |
|------|-----------|---------|------|
| 데일리 브리핑 알림 | GitHub Actions | Anthropic API | API 사용량 |
| 대화형 챗봇 | 로컬 PC | Claude Max (CLI) | 무료 (구독 포함) |

---

## 1. 데일리 브리핑 알림

### 동작 흐름
```
GitHub Actions cron (매일 09:00 KST)
→ briefing.py 실행
→ Claude API 웹검색으로 UE 애니메이션 최신 정보 수집
→ Notion 페이지 생성 → 텔레그램 요약 전송
```

### 스케줄
| 시간 (KST) | cron (UTC) | 내용 |
|------------|-----------|------|
| 매일 09:00 | `0 0 * * *` | 자동 선택 3개 카테고리 브리핑 |

### 10개 카테고리
Animation Blueprint, Control Rig, Motion Matching, UAF/AnimNext, MetaHuman, Sequencer, Live Link, ML Deformer, GASP, Mover Plugin

### 텔레그램 메시지 형식
```
🎮 언리얼 튜토리얼 가이드 비서
2026.03.26 업데이트

📂 Control Rig | UE 5.6 | 중급
▸ Control Rig으로 절차적 IK 체인 구현하기
  UE 5.6의 새로운 Full Body IK 솔버를 활용한...
  🔗 https://dev.epicgames.com/...

📋 Notion
```

### 수동 실행
```bash
export PATH="/c/Program Files/GitHub CLI:$PATH"
gh workflow run ue-animation-briefing.yml --repo kanzaka110/desktop-tutorial -f count=1
```

### 주요 옵션
- `-f count=5` — 5개 카테고리
- `-f all_categories=true` — 전체 10개
- `-f category="Control Rig"` — 특정 카테고리
- `-f force=true` — 중복 체크 무시

---

## 2. 대화형 챗봇 (Claude Max)

### 동작 흐름
```
텔레그램 메시지 → telegram_bot.py (폴링)
→ claude --print (CLI) → 응답 → 텔레그램 전송
```

### 실행 방법
```bash
set TELEGRAM_BOT_TOKEN=8190582482:AAFfbp9UaZM4tvwx3hcObejAayBGx6oR9Ys
set TELEGRAM_CHAT_ID=8799420252
cd "C:\Users\ohmil\OneDrive\바탕 화면\desktop-tutorial"
python scripts/telegram_bot.py
```

### 봇 명령어
| 명령어 | 설명 |
|--------|------|
| `/start` | 봇 시작 인사 |
| `/clear` | 대화 기록 초기화 |
| `/help` | 도움말 |
| 일반 메시지 | Claude가 답변 (UE5 전문) |

### 전문 분야
Animation Blueprint, Control Rig, Motion Matching, MetaHuman, Sequencer, Live Link, ML Deformer, GASP, Mover Plugin, UAF/AnimNext

---

## 3. 인프라 정보

### 봇 정보
- 봇 이름: 언리얼 튜토리얼 가이드 비서
- 사용자명: @Sanjuk_UE5_Guide_bot

### GitHub Secrets (kanzaka110/desktop-tutorial)
| 이름 | 용도 |
|------|------|
| `ANTHROPIC_API_KEY` | 브리핑 AI 분석 |
| `NOTION_API_KEY` | Notion 페이지 생성 |
| `NOTION_DATABASE_ID` | Notion DB ID |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 인증 (UE 전용) |
| `TELEGRAM_CHAT_ID` | 메시지 수신 대상 |

### 관련 파일
| 파일 | 용도 |
|------|------|
| `briefing/briefing.py` | 브리핑 생성 + 텔레그램 전송 |
| `scripts/telegram_bot.py` | 대화형 챗봇 (로컬 실행) |
| `.github/workflows/ue-animation-briefing.yml` | 자동 브리핑 cron |

### 프로젝트 경로
- 로컬: `C:\Users\ohmil\OneDrive\바탕 화면\desktop-tutorial`
- GitHub: `https://github.com/kanzaka110/desktop-tutorial`

---

## 4. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-03-26 | 텔레그램 브리핑 알림 연동 (send_telegram) |
| 2026-03-26 | 별도 봇 토큰 분리 (@Sanjuk_UE5_Guide_bot) |
| 2026-03-26 | 대화형 챗봇 추가 — Claude Max CLI 기반 |
