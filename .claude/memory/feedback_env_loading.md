---
name: GCP .env loading method
description: GCP에서 .env 파일 로딩 시 source 대신 export xargs 사용 필요
type: feedback
---

GCP의 .env 파일에는 `export` 접두사가 없어서 `source .env`로는 환경변수가 설정되지 않는다.

**Why:** .env 파일이 `KEY=value` 형식이라 bash source로는 환경변수로 export되지 않음
**How to apply:** GCP에서 .env 로딩 시 `export $(grep -v '^#' .env | xargs)` 사용. systemd 서비스는 `EnvironmentFile=`로 직접 로드하므로 문제없음.
