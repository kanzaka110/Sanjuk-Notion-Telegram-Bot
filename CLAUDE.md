# CLAUDE.md

## 프로젝트 개요

Notion 자동화 시스템 + 텔레그램 봇 5개의 구축 가이드, 소스 코드, GCP 운영 스크립트 모음.

## 구조

- **Chat_bot/** — 산적 수다방 봇 코드 (Gemini 하이브리드, SQLite, 테스트 포함)
- **Luck_bot/** — 나의 운세 봇 코드 (사주 역학 v3, Claude Sonnet)
- **investment_briefing_system.md** — 주식 브리핑 Notion 자동화 시스템 (Notion DB 연동)
- **봇 설명 문서** — 각 봇별 설정/구조 설명 (telegram_setup_guide.md 등)
- **운영 스크립트** — GCP 이전, cron 설정, 자동 업데이트

## 봇 5개 현황

| 봇 | 사용자명 | GitHub 코드 | GCP 서비스 |
|----|---------|-------------|-----------|
| 산적주식비서 | - | kanzaka110/notion-stock-update | stock-bot |
| UE5 가이드 | @Sanjuk_UE5_Guide_bot | kanzaka110/desktop-tutorial | ue-bot |
| 게임뉴스 | @Sanjuk_GameNews_bot | kanzaka110/desktop-tutorial | game-news-bot |
| 나의 운세 | @Sanjuk_Luck_bot | kanzaka110/luck-bot | luck-bot |
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
- .env 파일 위치: 각 봇 디렉토리 루트

## 개발 참고

- Chat_bot 테스트: `cd Chat_bot && python -m pytest tests/`
- 텔레그램 Chat ID: `8799420252`
- 같은 봇의 폴링 인스턴스는 1개만 (409 Conflict 주의)
- 문서는 한국어로 작성
