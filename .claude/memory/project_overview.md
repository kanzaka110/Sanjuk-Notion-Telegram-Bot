---
name: Project Overview
description: Sanjuk-Notion-Telegram-Bot 프로젝트 — 텔레그램 봇 3개 + Claude CLI 기반 (UE봇은 Sanjuk-Unreal로 분리)
type: project
originSessionId: 5b51174a-9d89-468b-969a-23fab840d5b3
---
Notion 자동화 + 텔레그램 봇 3개를 단일 리포에서 관리하는 프로젝트.
- UE5 가이드 봇은 [Sanjuk-Unreal](https://github.com/kanzaka110/Sanjuk-Unreal) 리포로 2026-04-12 분리.
- 주식은 [Sanjuk-Stock-Simulator](https://github.com/kanzaka110/Sanjuk-Stock-Simulator) 별도 리포.

**봇 구성 (3개):**
- Chat_bot (산적 수다방) — Claude CLI subprocess 챗봇
- Luck_bot (나의 운세) — Claude CLI 사주 역학 분석
- GameNews_bot (게임뉴스) — Claude CLI 게임뉴스 수집 + 챗봇 (시프트업 전용 섹션 포함)

**AI 모델 패턴 (2026-04-12~):**
- 전체 봇이 Claude CLI subprocess 호출 (API 비용 $0, Claude Code 구독 내 포함)
- 정보 수집: Claude CLI + WebSearch
- 분석/전략: Claude CLI (--model sonnet)
- 챗봇 대화: Claude CLI (--model sonnet, --system-prompt)
- 공통 유틸: shared_config.claude_cli()

**인프라:**
- GCP 인스턴스: sanjuk-project (e2-micro, us-central1-b, 고정 IP: 35.238.77.143)
- GCP SSH 유저: kanzaka110 (서비스), ohmil (gcloud 기본)
- RAM 1GB + Swap 2GB = 총 3GB
- GitHub Actions: schedule 비활성화, workflow_dispatch(수동 테스트)만 사용

**GCP 서비스 구조:**
- 3개 봇이 `~/Sanjuk-Notion-Telegram-Bot/` 통합 리포에서 실행
- venv: `~/Sanjuk-Notion-Telegram-Bot/venv/` (공유)
- .env: Luck_bot/.env, Chat_bot/.env, 루트 .env (GameNews_bot용)

**브리핑 cron:**
- GameNews_bot 래퍼만 이 리포 관리 (주식 cron은 Sanjuk-Stock-Simulator, UE는 Sanjuk-Unreal)

**Why:** 원래 분산되어 있던 리포들을 통합하여 유지보수 효율화
**How to apply:** 봇별 독립 디렉토리 구조 유지, GCP 서비스 수정 시 통합 리포 경로 사용
