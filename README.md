# Sanjuk-Notion-Telegram-Bot

Notion 자동화 + 텔레그램 봇 구축 가이드, 코드, 운영 스크립트 모음

## 구조

```
Sanjuk-Notion-Telegram-Bot/
├── Chat_bot/                        # 산적 수다방 (@Sanjuk_Talk_bot)
│   ├── chat_bot.py                  # 메인 봇 (Claude CLI)
│   ├── gemini_client.py             # Claude CLI 클라이언트
│   ├── database.py                  # SQLite 대화 저장
│   ├── summarizer.py                # 매일 23시 대화 요약
│   ├── mood.py                      # 감정 인식
│   ├── context_loader.py            # 컨텍스트 로딩
│   ├── config.py                    # 설정
│   └── tests/                       # 테스트 스위트
├── Luck_bot/                        # 나의 운세 (@Sanjuk_Luck_bot)
│   ├── luck_bot.py                  # 사주 분석 봇 (Claude CLI)
│   └── saju_calendar.py             # 사주 달력 계산
├── GameNews_bot/                    # 게임뉴스 (@Sanjuk_GameNews_bot)
│   ├── game_news.py                 # 게임뉴스 데일리 수집
│   ├── game_news_bot.py             # 대화형 게임뉴스 챗봇
│   └── requirements.txt             # 의존성
├── shared_config.py                 # 공통 설정 모듈 (Claude CLI 유틸 포함)
├── tests/                           # 공통 모듈 테스트
├── scripts/                         # GCP 운영 스크립트
│   ├── gcp-doctor.sh                # 상태 점검
│   ├── gcp-setup-remote.sh          # 리모트 세션 설정
│   └── gcp-restart-remote.sh        # 리모트 세션 재시작
├── .github/workflows/               # GitHub Actions 워크플로우
│   └── game-news.yml                # 게임뉴스 (수동 실행)
├── telegram_setup_guide.md          # 텔레그램 봇 셋업 가이드
├── game_news_bot.md                 # 게임뉴스 봇 설명
├── migrate_to_gcp.sh               # GCP 이전 스크립트
├── setup_briefing_cron.sh           # 브리핑 cron 설정
├── auto_update.sh                   # 자동 업데이트
└── disable_actions_schedules.sh     # Actions 스케줄 비활성화
```

> UE5 가이드 봇은 [Sanjuk-Unreal](https://github.com/kanzaka110/Sanjuk-Unreal) 리포로 분리됨
> 산적주식비서는 [Sanjuk-Stock-Simulator](https://github.com/kanzaka110/Sanjuk-Stock-Simulator) 리포로 분리됨

## 봇 목록 (3개)

| 봇 | 용도 | AI 모델 | 호스팅 |
|----|------|---------|--------|
| 산적 수다방 | AI 수다 컴패니언 | Claude CLI | GCP |
| 게임뉴스 | 게임 뉴스 요약 | Claude CLI | GCP |
| 나의 운세 | 사주 역학 브리핑 + 상담 | Claude CLI | GCP |

## 인프라

- **GCP e2-micro**: 봇 3개 24/7 운영 (무료 티어)
- **AI 비용**: $0 (Claude CLI subprocess, Claude Code 구독 내 포함)
