---
name: Project Overview
description: Sanjuk-Notion-Telegram-Bot 프로젝트 구조와 봇 4개 개요 (주식은 별도 리포)
type: project
---

Notion 자동화 + 텔레그램 봇 4개를 단일 리포에서 관리하는 프로젝트.
(주식 관련은 Sanjuk-Stock-Simulator 별도 리포로 2026-04-06 이전 완료)

**봇 구성 (4개):**
- Chat_bot (산적 수다방) — Gemini 하이브리드 AI 수다 컴패니언
- Luck_bot (나의 운세) — Claude Sonnet 사주 역학 분석, job_queue.run_daily로 08:00 KST 자동 전송
- UE_bot (UE5 가이드) — UE 애니메이션 브리핑 + 챗봇
- GameNews_bot (게임뉴스) — 게임뉴스 수집 + 챗봇 (시프트업 전용 섹션 포함)

**인프라:**
- GCP 인스턴스: sanjuk-project (e2-micro, us-central1-b, 고정 IP: 35.238.77.143)
- GCP SSH 유저: kanzaka110 (서비스), ohmil (gcloud 기본)
- RAM 1GB + Swap 2GB = 총 3GB
- GitHub Actions: schedule 비활성화, workflow_dispatch(수동 테스트)만 사용

**GCP 서비스 구조:**
- 4개 봇이 `~/Sanjuk-Notion-Telegram-Bot/` 통합 리포에서 실행
- venv: `~/Sanjuk-Notion-Telegram-Bot/venv/` (공유)
- .env: Luck_bot/.env, Chat_bot/.env, 루트 .env (UE_bot/GameNews_bot용)

**브리핑 cron:**
- UE_bot/GameNews_bot 래퍼만 이 리포 관리 (주식 cron은 Sanjuk-Stock-Simulator로 이전)
- 스케줄: UE 09:00, 게임뉴스 09:15

**Why:** 원래 분산되어 있던 리포들을 통합하여 유지보수 효율화
**How to apply:** 봇별 독립 디렉토리 구조 유지, GCP 서비스 수정 시 통합 리포 경로 사용
