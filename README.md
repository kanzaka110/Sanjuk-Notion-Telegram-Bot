# Sanjuk-Notion-Telegram-Bot

Notion 자동화 + 텔레그램 봇 구축 가이드, 코드, 운영 스크립트 모음

## 구조

```
Sanjuk-Notion-Telegram-Bot/
├── Chat_bot/                        # 산적 수다방 (@Sanjuk_Talk_bot)
│   ├── chat_bot.py                  # 메인 봇 (Gemini 하이브리드)
│   ├── gemini_client.py             # Gemini API 클라이언트
│   ├── database.py                  # SQLite 대화 저장
│   ├── summarizer.py                # 매일 23시 대화 요약
│   ├── mood.py                      # 감정 인식
│   ├── context_loader.py            # 컨텍스트 로딩
│   ├── config.py                    # 설정
│   ├── vector_memory.py             # 벡터 메모리
│   └── tests/                       # 테스트 스위트
├── Luck_bot/                        # 나의 운세 (@Sanjuk_Luck_bot)
│   ├── luck_bot.py                  # 사주 분석 봇 (Claude Sonnet)
│   └── saju_calendar.py             # 사주 달력 계산
├── Stock_bot/                       # 산적주식비서 (notion-stock-update)
│   ├── update_price.py              # Notion DB 주가 자동 업데이트
│   ├── scripts/briefing.py          # AI 투자 브리핑 + 텔레그램 전송
│   ├── scripts/telegram_bot.py      # 대화형 주식 챗봇
│   ├── scripts/chat_db.py           # 챗봇 DB
│   ├── scripts/fix_briefing_labels.py # 브리핑 라벨 수정 유틸
│   └── .github/workflows/          # GitHub Actions (브리핑 스케줄)
├── investment_briefing_system.md    # 주식 브리핑 Notion 자동화 시스템 설명
├── investment_briefing_bot.md       # 산적주식비서 봇 설명
├── telegram_setup_guide.md          # 텔레그램 봇 셋업 가이드
├── ue_tutorial_bot.md               # UE5 가이드 봇 설명
├── game_news_bot.md                 # 게임뉴스 봇 설명
├── migrate_to_gcp.sh               # GCP 이전 스크립트
├── setup_briefing_cron.sh           # 브리핑 cron 설정
├── auto_update.sh                   # 자동 업데이트
└── disable_actions_schedules.sh     # Actions 스케줄 비활성화
```

## 봇 목록 (5개)

| 봇 | 용도 | AI 모델 | 호스팅 |
|----|------|---------|--------|
| 산적주식비서 | 한국/미국 주식 브리핑 | Gemini Pro + Sonnet | GitHub Actions + GCP |
| UE5 가이드 | UE 애니메이션 데일리 브리핑 | Gemini Pro + Sonnet | GitHub Actions + GCP |
| 게임뉴스 | 게임 뉴스 요약 | Gemini Pro + Sonnet | GitHub Actions + GCP |
| 나의 운세 | 사주 역학 브리핑 + 상담 | Sonnet + Gemini Flash | GCP |
| 산적 수다방 | AI 수다 컴패니언 | Gemini Flash/Pro | GCP |

## 관련 리포지토리

- [desktop-tutorial](https://github.com/kanzaka110/desktop-tutorial) — UE 브리핑 + 게임뉴스 코드

## 인프라

- **GCP e2-micro**: 봇 5개 24/7 운영 (무료 티어)
- **GitHub Actions**: 브리핑 스케줄 실행
- **월 비용**: ~$15.5 (API 비용만, 호스팅 $0)
