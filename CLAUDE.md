# CLAUDE.md

## 프로젝트 개요

Notion 자동화 시스템 + 텔레그램 봇 5개의 구축 가이드, 소스 코드, GCP 운영 스크립트 모음.

## 구조

- **Chat_bot/** — 산적 수다방 봇 코드 (Gemini 하이브리드, SQLite, 테스트 포함)
- **Luck_bot/** — 나의 운세 봇 코드 (사주 역학 v3, Claude Sonnet)
- **Stock_bot/** — 산적주식비서 코드 (Notion 주가 업데이트 + AI 브리핑)
- **UE_bot/** — UE5 가이드 비서 코드 (UE 애니메이션 브리핑 + 챗봇)
- **GameNews_bot/** — 게임뉴스 봇 코드 (게임뉴스 수집 + 챗봇)
- **.github/workflows/** — GitHub Actions 워크플로우 (브리핑 스케줄)
- **봇 설명 문서** — 각 봇별 설정/구조 설명 (telegram_setup_guide.md 등)
- **운영 스크립트** — GCP 이전, cron 설정, 자동 업데이트

## 봇 5개 현황

| 봇 | 사용자명 | GitHub 코드 | GCP 서비스 |
|----|---------|-------------|-----------|
| 산적주식비서 | - | 이 리포 Stock_bot/ | stock-bot |
| UE5 가이드 | @Sanjuk_UE5_Guide_bot | 이 리포 UE_bot/ | ue-bot |
| 게임뉴스 | @Sanjuk_GameNews_bot | 이 리포 GameNews_bot/ | game-news-bot |
| 나의 운세 | @Sanjuk_Luck_bot | 이 리포 Luck_bot/ | luck-bot |
| 산적 수다방 | @Sanjuk_Talk_bot | 이 리포 Chat_bot/ | chatbot |

## AI 모델 사용 패턴

```
정보 수집: Gemini 3.1 Pro / 2.5 Pro + Google Search
분석/전략: Claude Sonnet 4.6
챗봇 대화: Gemini 2.5 Flash/Pro, 3 Flash (무료)
```

## GCP 관리

- 인스턴스: e2-micro (봇 5개 24/7)
- 서비스 관리: `sudo systemctl status/restart/stop <서비스명>`
- 로그 확인: `sudo journalctl -u <서비스명> -f`
- 모든 서비스가 `~/Sanjuk-Notion-Telegram-Bot/` 통합 리포에서 실행 (2026-04-05 마이그레이션 완료)
- venv: `~/Sanjuk-Notion-Telegram-Bot/venv/` (전체 봇 공유)
- .env 파일 위치: 각 봇 디렉토리 루트 (봇별 TELEGRAM_BOT_TOKEN이 다르므로 개별 .env 필수)
  - `Stock_bot/.env` — stock-bot 서비스
  - `Luck_bot/.env` — luck-bot 서비스
  - `Chat_bot/.env` — chatbot 서비스
  - 루트 `.env` — ue-bot, game-news-bot 서비스
- GitHub Actions: schedule 비활성화, workflow_dispatch(수동 테스트)만 사용

## 브리핑 운영 방침 (공통)

**모든 봇의 브리핑은 실행 당일 기준으로만 정보를 수집한다.**
- 어제 이미 브리핑을 받았으므로, 이전 날짜의 콘텐츠는 중복이라 필요 없음
- 당일 신규 정보가 없으면 "없음"으로 스킵 (억지로 오래된 내용 채우지 않음)

### UE_bot 브리핑
- **당일 신규 정보만** 수집 (어제 이전 콘텐츠 제외)
- 신규 정보 없으면 "없음"으로 스킵 (억지로 오래된 내용 채우지 않음)
- 검색 소스: YouTube (UE 유튜버들), 80.lv, Reddit, Twitter/X, Fab, FocalRig, Epic 공식 등 다양한 매체
- 애니메이션 전반 폭넓게 검색: Control Rig, Motion Matching, AnimNext, Physics Simulation, Ragdoll, Cloth, Live Link, ML Deformer, GASP, Mover, IK, Procedural Animation 등
- FocalRig (focalrig.com) — Procedural Look & Aim Control Rig 플러그인 소스 포함

### GameNews_bot 브리핑
- **당일 게시된 기사만** 수집 (어제 이전 기사 제외)
- 기사 제목과 URL이 반드시 같은 기사를 가리키도록 (제목-URL 매칭 필수)

## 개발 참고

- Chat_bot 테스트: `cd Chat_bot && python -m pytest tests/`
- 텔레그램 Chat ID: `8799420252`
- 같은 봇의 폴링 인스턴스는 1개만 (409 Conflict 주의)
- 문서는 한국어로 작성
