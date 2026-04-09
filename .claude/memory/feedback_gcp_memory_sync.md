---
name: GCP memory auto-sync
description: 메모리 변경 시 자동으로 GCP에 푸시 — 다른 환경에서도 동일한 Claude Code 경험 유지
type: feedback
originSessionId: abf5e759-3aed-4827-a22e-aa37455b2978
---
메모리가 업데이트될 때마다 GCP에 자동 동기화해야 한다. PostToolUse 훅으로 자동화되어 있지만, 훅이 실패하거나 수동으로 필요할 때는 `scripts\claude-config-push.cmd` 실행.

**Why:** 사용자가 GCP, 다른 PC 등 여러 환경에서 Claude Code를 사용하며, 모든 환경에서 동일한 메모리/규칙으로 작업하길 원함.

**How to apply:** 
- 메모리 파일 작성/수정 후 GCP 동기화가 자동으로 일어남 (PostToolUse 훅)
- 새 환경 추가 시 push 스크립트의 경로 매핑 업데이트 필요
- GCP 프로젝트 메모리 경로: `/home/ohmil/.claude/projects/-home-ohmil-Sanjuk-Notion-Telegram-Bot/memory/`
- 로컬 프로젝트 메모리 경로: `C:\Users\ohmil\.claude\projects\C--dev-Sanjuk-Notion-Telegram-Bot\memory\`
