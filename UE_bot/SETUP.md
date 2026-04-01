# 🎮 UE 애니메이션 데일리 브리핑 — 설정 가이드

## GitHub Actions 자동 브리핑 설정 (3단계)

### 1단계. Notion Integration 생성

1. https://www.notion.so/my-integrations 접속
2. **+ 새 통합** 클릭
3. 이름: `UE Animation Briefing`
4. **제출** → **Internal Integration Token** 복사 (secret_...)
5. 노션 데이터베이스 페이지로 이동
6. 우측 상단 `···` → **Connections** → 방금 만든 통합 추가

### 2단계. GitHub Secrets 등록

GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 이름 | 값 | 설명 |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | https://console.anthropic.com/settings/keys |
| `NOTION_API_KEY` | `secret_...` | 1단계에서 복사한 토큰 |
| `NOTION_DATABASE_ID` | `4fd756cb968d4439b9e80bbc69184a57` | 노션 데이터베이스 ID |

### 3단계. 워크플로우 활성화 확인

1. GitHub 저장소 → **Actions** 탭
2. `🎮 UE 애니메이션 데일리 브리핑` 워크플로우 확인
3. **Run workflow** 버튼으로 수동 테스트

---

## 실행 스케줄

- **자동 실행**: 매일 오전 9:00 KST (UTC 00:00)
- **수동 실행**: GitHub Actions → Run workflow

## 로컬 테스트

```bash
cd briefing
cp .env.example .env
# .env 파일에 API 키 입력 후:
pip install -r requirements.txt
python briefing.py --count 1
```

## 카테고리 목록

| 카테고리 | 설명 |
|---|---|
| Animation Blueprint | AnimGraph, State Machine, Blend Space |
| Control Rig | 런타임 리깅, IK, 절차적 애니메이션 |
| Motion Matching | 데이터베이스 기반 포즈 매칭 |
| UAF/AnimNext | 차세대 애니메이션 프레임워크 |
| MetaHuman | 고품질 디지털 휴먼 및 페이셜 애니메이션 |
| Sequencer | 시네마틱 및 키프레임 애니메이션 편집기 |
| Live Link | 모션 캡처 실시간 스트리밍 |
| ML Deformer | 머신러닝 기반 캐릭터 변형 |
| GASP | Game Animation Sample Project |
| Mover Plugin | 차세대 캐릭터 이동 컴포넌트 |
