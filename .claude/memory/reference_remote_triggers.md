---
name: Remote Triggers & Sessions
description: 모바일 Claude Code용 리모트 트리거 + GCP 대화형 세션 정보 (2026-04-12 업데이트)
type: reference
originSessionId: 5b51174a-9d89-468b-969a-23fab840d5b3
---
## 대화형 리모트 세션 (모바일)

| 세션명 | GCP tmux | 유저 | 환경 ID | 리포 |
|--------|----------|------|---------|------|
| Sanjuk-Telegram-Bot (GCP) | telegram | kanzaka110 | `env_01GwXAyvF4UAttLzRo5UiT9r` | Sanjuk-Notion-Telegram-Bot |
| Sanjuk-Stock-Simulator (GCP) | claude | ohmil | `env_01JceVCDtJ5t9XJdbxSpm3ZE` | Sanjuk-Stock-Simulator |
| Sanjuk-Unreal (GCP) | unreal | ohmil | — | Sanjuk-Unreal |
| 3dsmax-mcp-GCP | max3d | ohmil | — | — |

**스크립트:** `scripts/gcp-setup-remote.sh` (kanzaka110 유저로 실행 필요), `scripts/gcp-restart-remote.sh`

## 리모트 트리거 (스케줄/수동)

| 트리거 | ID | 스케줄 | 상태 | 용도 |
|--------|-----|--------|------|------|
| telegram-bot-status | `trig_01Kxpdo86C6V2esRuKyzmaEh` | 매일 09:00 KST | 활성 | 봇 상태 확인 |
| telegram-bot-restart | `trig_015tcHdq8vb2xSo4MFNVmuHx` | 수동 | 비활성 | 봇 재시작 |
| telegram-bot-logs | `trig_01SfbXkcRT8iVMKsTbpHKgtK` | 수동 | 비활성 | 최근 로그 조회 |
| telegram-disk-check | `trig_01C9osn6nKYTQpk7uKY8n98J` | 매주 일 09:00 KST | 비활성 | 디스크/메모리 확인 |
| telegram-deploy-update | `trig_01N5wkbSiAqujUSgaMo3YrKJ` | 수동 | 비활성 | git pull + 봇 재시작 |
| telegram-cron-status | `trig_01Swaq2hZ7ozWrmcGA393pwK` | 수동 | 비활성 | 브리핑 크론잡 상태 |
| 한국장 브리핑 (CLI) | `trig_01MSRmeQnXk6bkyGDtoN7t3E` | 평일 08:30 KST | 활성 | Stock-Simulator |
| 미국장 브리핑 (CLI) | `trig_0199WXwCFyHAc74Ryay7nHag` | 평일 21:00 KST | 활성 | Stock-Simulator |

관리 페이지: https://claude.ai/code/scheduled
