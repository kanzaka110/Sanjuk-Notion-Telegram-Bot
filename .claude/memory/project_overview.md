---
name: Project Overview
description: Sanjuk-Notion-Telegram-Bot 프로젝트 구조와 봇 5개 개요
type: project
---

Notion 자동화 + 텔레그램 봇 5개를 단일 리포에서 관리하는 프로젝트.

**봇 구성:**
- Chat_bot (산적 수다방) — Gemini 하이브리드 AI 수다 컴패니언
- Luck_bot (나의 운세) — Claude Sonnet 사주 역학 분석
- Stock_bot (산적주식비서) — Notion 주가 업데이트 + AI 브리핑
- UE_bot (UE5 가이드) — UE 애니메이션 브리핑 + 챗봇
- GameNews_bot (게임뉴스) — 게임뉴스 수집 + 챗봇

**인프라:**
- GCP 인스턴스: sanjuk-project (e2-micro, us-central1-b, 고정 IP: 35.238.77.143)
- RAM 1GB + Swap 2GB = 총 3GB (봇 7-9개 수용 가능)
- GitHub Actions: schedule 비활성화, workflow_dispatch(수동 테스트)만 사용

**GCP 서비스 구조 (2026-04-05 통합 완료):**
- 모든 서비스가 `~/Sanjuk-Notion-Telegram-Bot/` 통합 리포에서 실행
- venv: `~/Sanjuk-Notion-Telegram-Bot/venv/` (공유)
- .env: 봇별 개별 파일 (Stock_bot/.env, Luck_bot/.env, Chat_bot/.env, 루트 .env는 UE_bot/GameNews_bot용)

**Why:** 원래 분산되어 있던 리포들을 통합하여 유지보수 효율화
**How to apply:** 봇별 독립 디렉토리 구조 유지, GCP 서비스 수정 시 통합 리포 경로 사용
