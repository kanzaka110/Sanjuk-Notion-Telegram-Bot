---
name: Telegram Bot Remote Triggers
description: 모바일 Claude Code에서 GCP 텔레그램 봇 관리용 리모트 트리거 6개 (2026-04-08 생성)
type: reference
---

GCP sanjuk-project의 텔레그램 봇 4개를 모바일에서 관리하기 위한 리모트 트리거.
Bridge 환경: `sanjuk-project:Sanjuk-Notion-Telegram-Bot` (`env_01Xgo6Y8GeByh2oHF9o2WVdC`)
GCP에서 `claude bridge` 명령으로 등록 (~/Sanjuk-Notion-Telegram-Bot 디렉토리).

| 트리거 | ID | 스케줄 | 상태 | 용도 |
|--------|-----|--------|------|------|
| telegram-bot-status | `trig_01Kxpdo86C6V2esRuKyzmaEh` | 매일 09:00 KST | 활성 | 봇 4개 상태 확인 |
| telegram-bot-restart | `trig_015tcHdq8vb2xSo4MFNVmuHx` | 수동 | 비활성 | 봇 재시작 |
| telegram-bot-logs | `trig_01SfbXkcRT8iVMKsTbpHKgtK` | 수동 | 비활성 | 최근 로그 조회 |
| telegram-disk-check | `trig_01C9osn6nKYTQpk7uKY8n98J` | 매주 일 09:00 KST | 활성 | 디스크/메모리 확인 |
| telegram-deploy-update | `trig_01N5wkbSiAqujUSgaMo3YrKJ` | 수동 | 비활성 | git pull + 봇 재시작 |
| telegram-cron-status | `trig_01Swaq2hZ7ozWrmcGA393pwK` | 수동 | 비활성 | 브리핑 크론잡 상태 |

관리 페이지: https://claude.ai/code/scheduled
