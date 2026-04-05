---
name: GCP Service Migration 2026-04-05
description: GCP systemd 서비스 3개를 옛 경로에서 통합 리포로 마이그레이션 완료
type: project
---

2026-04-05 GCP systemd 서비스 경로를 통합 리포로 일괄 마이그레이션.

**변경된 서비스:**
- stock-bot: `~/notion-stock-update/` → `~/Sanjuk-Notion-Telegram-Bot/Stock_bot/`
- luck-bot: `~/luck-bot/` → `~/Sanjuk-Notion-Telegram-Bot/Luck_bot/`
- chatbot: `~/Sanjuk-Claude-Code/Project/.../Chat_bot/` → `~/Sanjuk-Notion-Telegram-Bot/Chat_bot/`

**이미 통합 리포였던 서비스:** ue-bot, game-news-bot

**삭제된 옛 디렉토리:** notion-stock-update (296MB), luck-bot (91MB), Sanjuk-Claude-Code (170MB) — 총 557MB 확보

**환경변수 구조:**
- Stock_bot/.env: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, CLAUDE_API_KEY, NOTION_API_KEY, NOTION_DB_ID 등
- Luck_bot/.env: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, ANTHROPIC_API_KEY
- Chat_bot/.env: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, GITHUB_TOKEN, GITHUB_REPO
- 루트 .env: UE_bot/GameNews_bot용 (ANTHROPIC_API_KEY, NOTION_API_KEY, NOTION_DATABASE_ID 등)
- 각 봇의 TELEGRAM_BOT_TOKEN이 다르므로 봇별 .env 필수

**주의:** GitHub Actions에는 NOTION_DB_ID (Stock_bot용) Secret이 미등록 상태. GCP에서만 실행하므로 문제없음.

**Why:** 옛 경로 참조 제거, 단일 리포에서 코드+서비스 일관성 확보
**How to apply:** 서비스 수정 시 `/etc/systemd/system/<서비스>.service` 편집 후 `sudo systemctl daemon-reload && sudo systemctl restart <서비스>`
