---
name: GCP Service Migration 2026-04-05
description: GCP systemd 서비스 마이그레이션 + 2026-04-06 주식 서비스 분리
type: project
---

2026-04-05 GCP systemd 서비스 경로를 통합 리포로 일괄 마이그레이션.
2026-04-06 주식 관련 서비스를 Sanjuk-Stock-Simulator 별도 리포로 분리.

**현재 서비스 (2026-04-06):**
- chatbot: `~/Sanjuk-Notion-Telegram-Bot/Chat_bot/` — 산적 수다방
- luck-bot: `~/Sanjuk-Notion-Telegram-Bot/Luck_bot/` — 나의 운세
- ue-bot: `~/Sanjuk-Notion-Telegram-Bot/UE_bot/` — UE5 가이드
- game-news-bot: `~/Sanjuk-Notion-Telegram-Bot/GameNews_bot/` — 게임뉴스
- stock-chatbot-new: `~/Sanjuk-Stock-Simulator/` — 산적주식비서 (별도 리포)
- stock-bot: **비활성화** (stock-chatbot-new로 대체)

**cron 래퍼 (2026-04-06):**
- `~/run_stock_briefing_kr.sh`, `~/run_stock_briefing_us.sh`, `~/run_stock_update.sh` → Sanjuk-Stock-Simulator 가리킴
- `~/run_ue_briefing.sh`, `~/run_game_news.sh` → Sanjuk-Notion-Telegram-Bot 가리킴

**환경변수 구조:**
- Luck_bot/.env, Chat_bot/.env: 봇별 개별
- 루트 .env: UE_bot/GameNews_bot용
- ~/Sanjuk-Stock-Simulator/.env: 주식 전용 (Stock_bot/.env에서 복사)

**Why:** 주식 기능을 인터랙티브 터미널로 확장하면서 독립 리포로 분리
**How to apply:** 주식 서비스 수정 시 Sanjuk-Stock-Simulator 리포, 나머지는 기존 통합 리포
