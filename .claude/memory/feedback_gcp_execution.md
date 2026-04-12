---
name: GCP execution preference
description: 봇 관련 모든 작업(브리핑, 테스트, 스크립트 실행)은 로컬이 아닌 GCP에서 실행
type: feedback
originSessionId: 5b51174a-9d89-468b-969a-23fab840d5b3
---
봇 관련 작업은 항상 GCP에서 실행해야 한다. 로컬에서 실행하지 않는다.

**Why:** 로컬(Windows)에는 claude CLI 경로, 환경변수(.env), venv가 GCP와 다르고, 봇 토큰도 GCP에만 있음. GCP가 실제 운영 환경이므로 테스트도 GCP에서 해야 의미가 있다.

**How to apply:**
- 브리핑 테스트, 봇 스크립트 실행, 패키지 설치 등 모든 실행 작업은 `gcloud compute ssh kanzaka110@sanjuk-project --zone=us-central1-b --command="..."` 로 GCP에서 수행
- 코드 편집/커밋은 로컬에서, 실행/테스트는 GCP에서
- .env 로딩: `export $(grep -v '^#' .env | xargs)` 방식 사용
