# CLAUDE.md

## 프로젝트 개요

Notion 자동화 시스템 + 텔레그램 봇 4개의 구축 가이드, 소스 코드, GCP 운영 스크립트 모음.

## 구조

- **Chat_bot/** — 산적 수다방 봇 코드 (Claude CLI, SQLite, 테스트 포함)
- **Luck_bot/** — 나의 운세 봇 코드 (사주 역학 v3, Claude CLI)
- **UE_bot/** — UE5 가이드 비서 코드 (UE 애니메이션 브리핑 + 챗봇, Claude CLI)
- **GameNews_bot/** — 게임뉴스 봇 코드 (게임뉴스 수집 + 챗봇, Claude CLI)
- **.github/workflows/** — GitHub Actions 워크플로우 (브리핑 스케줄)
- **shared_config.py** — 공통 설정 모듈 (타임존, 환경변수 검증, 봇별 요구사항 정의)
- **tests/** — 공통 모듈 테스트 (shared_config 등)
- **봇 설명 문서** — 각 봇별 설정/구조 설명 (telegram_setup_guide.md 등)
- **운영 스크립트** — GCP 이전, cron 설정, 자동 업데이트, 상태 점검(doctor)

## 봇 4개 현황

| 봇 | 사용자명 | GitHub 코드 | GCP 서비스 |
|----|---------|-------------|-----------|
| UE5 가이드 | @Sanjuk_UE5_Guide_bot | 이 리포 UE_bot/ | ue-bot |
| 게임뉴스 | @Sanjuk_GameNews_bot | 이 리포 GameNews_bot/ | game-news-bot |
| 나의 운세 | @Sanjuk_Luck_bot | 이 리포 Luck_bot/ | luck-bot |
| 산적 수다방 | @Sanjuk_Talk_bot | 이 리포 Chat_bot/ | chatbot |

## AI 모델 사용 패턴

```
전체: Claude CLI subprocess 호출 (API 비용 $0, Claude Code 구독 내 포함)
정보 수집: Claude CLI + WebSearch (--allowedTools WebSearch,WebFetch)
분석/전략: Claude CLI (--model sonnet)
챗봇 대화: Claude CLI (--model sonnet, --system-prompt)
공통 유틸: shared_config.claude_cli() — 전체 봇 공유
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

## 설정 관리 구조

```
계층 1: shared_config.py     — 공통 상수, KST, validate_env()
계층 2: 봇별 .env            — 봇별 시크릿 (TELEGRAM_BOT_TOKEN 등)
계층 3: 봇별 config.py       — 봇별 설정, 프롬프트
```

- `shared_config.validate_env("봇이름")` — 봇 시작 전 필수 환경변수 검증
- `shared_config.load_bot_env("봇디렉토리")` — .env 로드 (봇별 → 루트 폴백)

## GCP 상태 점검

```bash
# GCP에서 직접 실행
bash ~/Sanjuk-Notion-Telegram-Bot/scripts/gcp-doctor.sh

# 로컬에서 SSH로 실행
gcloud compute ssh sanjuk-project --zone=us-central1-b < scripts/gcp-doctor.sh
```

점검 항목: systemd 서비스, 에러 로그, .env 파일, 디스크/메모리, Git 동기화
