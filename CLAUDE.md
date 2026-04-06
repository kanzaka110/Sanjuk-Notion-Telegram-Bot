# CLAUDE.md

## 프로젝트 개요

Notion 자동화 시스템 + 텔레그램 봇 4개의 구축 가이드, 소스 코드, GCP 운영 스크립트 모음.
(주식 관련 기능은 [Sanjuk-Stock-Simulator](https://github.com/kanzaka110/Sanjuk-Stock-Simulator)로 분리됨)

## 구조

- **Chat_bot/** — 산적 수다방 봇 코드 (Gemini 하이브리드, SQLite, 테스트 포함)
- **Luck_bot/** — 나의 운세 봇 코드 (사주 역학 v3, Claude Sonnet)
- **UE_bot/** — UE5 가이드 비서 코드 (UE 애니메이션 브리핑 + 챗봇)
- **GameNews_bot/** — 게임뉴스 봇 코드 (게임뉴스 수집 + 챗봇)
- **.github/workflows/** — GitHub Actions 워크플로우 (브리핑 스케줄)
- **봇 설명 문서** — 각 봇별 설정/구조 설명 (telegram_setup_guide.md 등)
- **운영 스크립트** — GCP 이전, cron 설정, 자동 업데이트

## 봇 4개 현황

| 봇 | 사용자명 | GitHub 코드 | GCP 서비스 |
|----|---------|-------------|-----------|
| UE5 가이드 | @Sanjuk_UE5_Guide_bot | 이 리포 UE_bot/ | ue-bot |
| 게임뉴스 | @Sanjuk_GameNews_bot | 이 리포 GameNews_bot/ | game-news-bot |
| 나의 운세 | @Sanjuk_Luck_bot | 이 리포 Luck_bot/ | luck-bot |
| 산적 수다방 | @Sanjuk_Talk_bot | 이 리포 Chat_bot/ | chatbot |

> 산적주식비서는 별도 리포 [Sanjuk-Stock-Simulator](https://github.com/kanzaka110/Sanjuk-Stock-Simulator)에서 관리

## AI 모델 사용 패턴

```
정보 수집: Gemini 3.1 Pro / 2.5 Pro + Google Search
분석/전략: Claude Sonnet 4.6
챗봇 대화: Gemini 2.5 Flash/Pro, 3 Flash (무료)
```

## GCP 관리

- 인스턴스: sanjuk-project (e2-micro, us-central1-b, 고정 IP: 35.238.77.143)
- 리소스: RAM 1GB + Swap 2GB = 총 3GB (봇 7-9개 수용 가능)
- 서비스 관리: `sudo systemctl status/restart/stop <서비스명>`
- 로그 확인: `sudo journalctl -u <서비스명> -f`
- 모든 서비스가 `~/Sanjuk-Notion-Telegram-Bot/` 통합 리포에서 실행 (2026-04-05 마이그레이션 완료)
- venv: `~/Sanjuk-Notion-Telegram-Bot/venv/` (전체 봇 공유)
- .env 파일 위치: 각 봇 디렉토리 루트 (봇별 TELEGRAM_BOT_TOKEN이 다르므로 개별 .env 필수)
  - `Luck_bot/.env` — luck-bot 서비스
  - `Chat_bot/.env` — chatbot 서비스
  - 루트 `.env` — ue-bot, game-news-bot 서비스
- GitHub Actions: schedule 비활성화, workflow_dispatch(수동 테스트)만 사용

## 브리핑 운영 방침 (공통)

- 당일 기준 또는 봇별 설정된 기간 내 신규 정보를 수집
- 신규 정보가 없으면 "없음"으로 스킵 (억지로 오래된 내용 채우지 않음)
- URL은 반드시 Gemini grounding_metadata에서 검증된 것만 사용 (AI hallucination 방지)

### UE_bot 브리핑
- **최근 3일 내 신규 정보** 수집 (주말에도 콘텐츠 확보)
- 기본 3개 카테고리/일 (13개 카테고리에서 랜덤 선택)
- 카테고리: Animation Blueprint, Control Rig, Motion Matching, UAF/AnimNext, MetaHuman, Sequencer, Live Link, ML Deformer, GASP, Mover Plugin, **AI Animation Tech**, **Physics/Simulation**, **GitHub/Open Source**
- 검색 소스: YouTube (UE 유튜버들), 80.lv, Reddit, Twitter/X, Fab, FocalRig, Epic 공식, **GitHub** 등 다양한 매체
- 애니메이션 전반 폭넓게 검색: Control Rig, Motion Matching, AnimNext, Physics Simulation, Ragdoll, Cloth, Live Link, ML Deformer, GASP, Mover, IK, Procedural Animation 등
- **AI 기술 포함**: Neural Animation, Motion Diffusion, AI Retargeting, ML 기반 애니메이션 도구
- **GitHub 포함**: UE 플러그인, 애니메이션 도구, AI+게임 관련 신규 릴리스
- FocalRig (focalrig.com) — Procedural Look & Aim Control Rig 플러그인 소스 포함
- 신규 정보 없을 때도 텔레그램 "새로운 업데이트 없음" 전송

### GameNews_bot 브리핑
- **당일 게시된 기사만** 수집 (어제 이전 기사 제외)
- 기사 제목과 URL이 반드시 같은 기사를 가리키도록 (제목-URL 매칭 필수)
- ⭐ 시프트업(SHIFT UP) 전용 섹션 최상단 배치

### 브리핑 cron 구조 (GCP)
- 래퍼 스크립트: `~/run_*.sh` (python -u, 통합 리포 경로, 공유 venv)
- UE_bot/GameNews_bot 래퍼: 루트 `.env` 사용
- 로그: `~/logs/briefing/*.log`

## GCP 디스크 관리

- 디스크 10GB (e2-micro 기본), 80% 이상 시 정리 필요
- 정리 명령어: `sudo apt-get clean && sudo journalctl --vacuum-time=3d`
- 추가 정리: `/var/log`의 `.gz`, `.1` 파일 삭제, ops-agent 로그 truncate
- pip 캐시: `rm -rf ~/.cache/pip`

## 개발 참고

- Chat_bot 테스트: `cd Chat_bot && python -m pytest tests/`
- 텔레그램 Chat ID: `8799420252`
- 같은 봇의 폴링 인스턴스는 1개만 (409 Conflict 주의)
- 문서는 한국어로 작성
