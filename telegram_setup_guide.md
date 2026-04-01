# 📱 텔레그램 주식 브리핑 연동 가이드

기존 `kanzaka110/notion-stock-update` 프로젝트의 주식 브리핑을 텔레그램으로도 받아보기 위한 **단계별 설정 가이드**입니다.

> [!NOTE]
> 이 작업은 기존 Notion 브리핑에 **추가**하는 것이므로, 클로드 API 토큰 비용은 증가하지 않습니다.
> 이미 생성된 브리핑 텍스트를 텔레그램으로 한 번 더 전송하는 것뿐입니다.

---

## 📌 전체 흐름 요약

```
[1] 텔레그램 앱 설치
[2] BotFather로 봇 생성 → 봇 토큰 획득
[3] 봇에게 메시지 전송 → Chat ID 확인
[4] GitHub Secrets에 토큰 & Chat ID 등록
[5] briefing.py에 텔레그램 전송 함수 추가
[6] briefing.yml에 환경 변수 전달 추가
[7] 테스트 실행 및 확인
```

---

## STEP 1. 텔레그램 앱 설치

### PC (Windows)

1. 웹 브라우저에서 [https://desktop.telegram.org](https://desktop.telegram.org) 접속
2. **"Get Telegram for Windows x64"** 클릭하여 설치 파일 다운로드
3. 다운로드된 `tsetup-x.x.x.exe` 실행 → 설치 완료
4. 앱 실행 후 **본인 휴대폰 번호로 로그인** (인증 코드는 SMS 또는 기존 텔레그램 앱으로 수신)

### 모바일 (선택)

- **Android**: Google Play 스토어에서 "Telegram" 검색 → 설치
- **iPhone**: App Store에서 "Telegram" 검색 → 설치

> [!TIP]
> PC와 모바일 모두 **같은 전화번호**로 로그인하면 동기화됩니다.
> 둘 다 설치하시면 PC에서 설정하고, 모바일로 알림을 받아보실 수 있습니다.

---

## STEP 2. 텔레그램 봇(Bot) 생성

텔레그램 봇은 자동으로 메시지를 보내주는 "로봇 계정"입니다.

### 2-1. BotFather 찾기

1. 텔레그램 앱 상단의 **검색창**에 `BotFather` 입력
2. 파란색 체크 표시(✓)가 있는 공식 **BotFather**를 선택
3. 대화창에서 **"시작"** 또는 **"Start"** 버튼 클릭

### 2-2. 봇 생성 명령어 입력

대화창에 아래 명령어를 순서대로 입력합니다:

```
/newbot
```

BotFather가 질문하는 대로 답변합니다:

| 질문 | 입력 예시 | 설명 |
|------|-----------|------|
| 봇의 이름을 정해주세요 | `주식브리핑봇` | 사람에게 보이는 표시 이름 (한글 가능) |
| 봇의 사용자명을 정해주세요 | `my_stock_briefing_bot` | **반드시 영어**이고, **`_bot`으로 끝나야** 합니다 |

### 2-3. 봇 토큰 저장 ⚠️

생성이 완료되면 BotFather가 아래와 같은 형식의 메시지를 보냅니다:

```
Use this token to access the HTTP API:
7123456789:AAHxyz_어쩌구저쩌구_긴문자열
```

> [!CAUTION]
> 이 토큰은 봇의 **비밀번호**와 같습니다.
> **반드시 메모장 등에 안전하게 복사해 두세요.** 절대 공개하지 마세요.

---

## STEP 3. Chat ID 확인

봇이 **어디로** 메시지를 보낼지 목적지(Chat ID)를 알아내야 합니다.

### 3-1. 봇에게 아무 메시지 보내기

1. 텔레그램 검색창에 방금 만든 봇 사용자명(예: `my_stock_briefing_bot`)을 검색
2. 봇과의 대화를 열고 **"시작"** 또는 **"/start"** 클릭
3. 아무 메시지나 입력 (예: `hello`)

### 3-2. 브라우저에서 Chat ID 확인

웹 브라우저 주소창에 아래 URL을 입력합니다 (**토큰 부분을 교체**):

```
https://api.telegram.org/bot여기에_봇_토큰_붙여넣기/getUpdates
```

결과 JSON에서 `"chat":{"id": 숫자}` 부분을 찾습니다:

```json
{
  "message": {
    "chat": {
      "id": 123456789,    ← 이 숫자가 Chat ID입니다!
      "first_name": "홍길동",
      "type": "private"
    }
  }
}
```

> [!IMPORTANT]
> 이 **Chat ID 숫자**도 메모장에 저장해 두세요.

---

## STEP 4. GitHub Secrets에 등록

1. GitHub에서 저장소 접속
2. **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
3. 아래 2개를 각각 등록:

| Secret 이름 | 값 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | STEP 2에서 받은 봇 토큰 |
| `TELEGRAM_CHAT_ID` | STEP 3에서 확인한 Chat ID 숫자 |

---

## 💡 참고 사항

- **텔레그램 메시지 길이 제한**: 한 번에 최대 4,096자까지 전송 가능
- **Markdown 포맷**: 텔레그램은 기본 Markdown(볼드, 이탤릭, 코드블록) 지원
- **알림 설정**: 텔레그램 앱 → 봇 대화 → 상단 봇 이름 → 알림 커스터마이즈 가능
- **그룹 채팅방**: 여러 사람이 받으려면 그룹에 봇 초대 후 그룹 Chat ID 사용
