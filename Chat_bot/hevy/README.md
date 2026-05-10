# Hevy 운동 통합

수다봇이 Hevy(헬스 트래킹 앱) 데이터를 활용하기 위한 모듈.

## 구조
```
hevy/
├── __init__.py
├── client.py        # Hevy API 비동기 클라이언트 (httpx)
├── analytics.py     # PR/볼륨/추세 분석 (외부 의존성 없음)
├── sync.py          # API → 캐시(.json) + PR 누적(.sqlite)
├── jobs.py          # PTB JobQueue 콜백 4종
└── data/
    ├── hevy_cache.json    (gitignore)
    └── hevy_prs.sqlite    (gitignore)
```

## 환경변수
```
HEVY_API_KEY=...   # Hevy Pro 구독 필수. Settings → Account → Developer
```

## 자동 푸시 (KST)
| 시간 | 잡 | 트리거 |
|---|---|---|
| 04:00 | hevy_sync | 매일 |
| 08:00 | morning_workout | 어제 운동 있을 때만 |
| 21:00 | workout_nudge | 오늘 X & 이번주 < 3회 |
| 월 08:05 | weekly_workout_report | 매주 |

`chat_bot.py`의 `main()`에 모두 등록 완료.

## 수동 실행
```bash
# 단발 sync (캐시 갱신만)
python -m hevy.sync

# 테스트
python -m pytest tests/test_hevy_*.py -v
```

## 알고리즘 노트
- **PR 정의**: 동일 종목 `max(weight_kg)`, 동률 시 `max(reps)`. Warmup 세트 제외.
- **휴식일 인정**: 이번주 운동 횟수 ≥ `WEEKLY_THRESHOLD`(=3)이면 21:00 nudge 스킵.
- **시간대**: 모든 비교는 KST(`timezone(timedelta(hours=9))`) 기준.
- **캐시 윈도우**: 30일. 주간 리포트 7일은 그 안에서 필터.

## MCP와의 관계
이 Python 모듈은 **cron 자동 푸시 전용**. 사용자/봇이 Claude CLI를 통해 운동 데이터를 인터랙티브하게 조회할 때는 별도 MCP 서버(`chrisdoc/hevy-mcp`, npx)를 사용. 둘은 같은 Hevy API를 다른 경로로 호출할 뿐 충돌 없음.
