---
name: GCP Service Migration
description: GCP systemd 서비스 구성 — 3봇 체제 (UE봇 Sanjuk-Unreal 분리, 주식 Sanjuk-Stock-Simulator 분리)
type: project
originSessionId: 5b51174a-9d89-468b-969a-23fab840d5b3
---
2026-04-05 GCP systemd 서비스 경로를 통합 리포로 일괄 마이그레이션.
2026-04-06 주식 관련 서비스를 Sanjuk-Stock-Simulator 별도 리포로 분리.
2026-04-12 UE_bot을 Sanjuk-Unreal 별도 리포로 분리, Claude CLI 전환.

**현재 서비스 (2026-04-12):**
- chatbot: `~/Sanjuk-Notion-Telegram-Bot/Chat_bot/` — 산적 수다방 (Claude CLI)
- luck-bot: `~/Sanjuk-Notion-Telegram-Bot/Luck_bot/` — 나의 운세 (Claude CLI)
- game-news-bot: `~/Sanjuk-Notion-Telegram-Bot/GameNews_bot/` — 게임뉴스 (Claude CLI)
- ue-bot: `~/Sanjuk-Unreal/UE_bot/` — UE5 가이드 (**별도 리포**)
- stock-chatbot-new: `~/Sanjuk-Stock-Simulator/` — 산적주식비서 (**별도 리포**)
- stock-bot: **비활성화** (stock-chatbot-new로 대체)

**cron 래퍼:**
- `~/run_game_news.sh` → Sanjuk-Notion-Telegram-Bot
- `~/run_ue_briefing.sh` → Sanjuk-Unreal (분리됨)
- `~/run_stock_briefing_kr.sh`, `~/run_stock_briefing_us.sh`, `~/run_stock_update.sh` → Sanjuk-Stock-Simulator

**환경변수 구조:**
- Luck_bot/.env, Chat_bot/.env: 봇별 개별
- 루트 .env: GameNews_bot용
- ~/Sanjuk-Unreal/.env: UE봇 전용
- ~/Sanjuk-Stock-Simulator/.env: 주식 전용

**Why:** 프로젝트 성장에 따라 도메인별 리포 분리로 관리 효율화
**How to apply:** 이 리포는 Chat_bot/Luck_bot/GameNews_bot 3개만 관리. UE/주식은 각 리포에서.
