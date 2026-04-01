# 산적 수다방 (Sanjuk_Talk_bot)

텔레그램 수다 챗봇. Gemini 하이브리드(Flash/Pro) 기반.
매일 23시 대화 요약을 GitHub memory/에 push하여 Claude Code 메모리에 누적.

## 아키텍처

```
사용자 ↔ 텔레그램 봇 (GCP e2-micro)
            ├─ 기본: Gemini 2.5 Flash (무료)
            ├─ /deep: Gemini 2.5 Pro (무료, 100 RPD)
            ├─ SQLite (대화 저장)
            └─ 매일 23:00 → GitHub memory/ push
```

## 명령어

| 명령어 | 설명 |
|--------|------|
| `/start` | 봇 소개 |
| `/deep` | Pro 모드 전환 |
| `/casual` | Flash 모드 복귀 |
| `/status` | 모델 상태 + 대화 수 |
| `/clear` | 대화 컨텍스트 초기화 |
| `/summary` | 오늘 대화 수동 요약 |
| `/help` | 도움말 |

## 로컬 실행

```bash
# 환경변수 설정
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="8799420252"
export GEMINI_API_KEY="..."
export GITHUB_TOKEN="..."
export GITHUB_REPO="kanzaka110/Sanjuk-Notion-Telegram-Bot"

# 의존성 설치
pip install -r requirements.txt

# 실행
python chat_bot.py
```

## GCP 배포

```bash
# SSH 접속 후 원클릭 세팅
curl -sL https://raw.githubusercontent.com/kanzaka110/Sanjuk-Notion-Telegram-Bot/master/Chat_bot/setup_gcp.sh | bash
```

## 환경변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `TELEGRAM_BOT_TOKEN` | O | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | O | 허용할 Chat ID |
| `GEMINI_API_KEY` | O | Google AI Studio API 키 |
| `GITHUB_TOKEN` | X | GitHub PAT (메모리 push) |
| `GITHUB_REPO` | X | GitHub 레포 (기본: kanzaka110/Sanjuk-Notion-Telegram-Bot) |

## 파일 구조

```
Chat_bot/
├── chat_bot.py         # 메인 봇
├── config.py           # 설정
├── database.py         # SQLite 대화 저장
├── gemini_client.py    # Gemini Flash/Pro 클라이언트
├── summarizer.py       # 요약 + GitHub push
├── setup_gcp.sh        # GCP 세팅 스크립트
├── requirements.txt
├── data/               # SQLite DB (gitignore)
└── tests/
```
