---
name: GCP SSH from local
description: 로컬 Windows에서 GCP VM에 SSH 접속하는 방법 — ohmil(기본)/kanzaka110(서비스) 유저
type: reference
---

gcloud CLI 설치 완료 (2026-04-05). 프로젝트: sanjuk-talk-bot. 경로에 공백이 있어 bash에서 직접 호출 시 --command 인자 파싱 문제 발생.

**해결책:** `gcp-ssh.cmd` 래퍼 사용

```bash
cmd.exe //c "C:\\dev\\Sanjuk-Notion-Telegram-Bot\\gcp-ssh.cmd" "원격 명령어"
```

**gcloud 직접 호출 (단순 명령만 가능):**
```bash
GCLOUD='C:/Users/ohmil/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd'
"$GCLOUD" compute ssh sanjuk-talk-bot --zone=us-central1-b --command="hostname"
```
- 단순 명령(인자 없는)은 bash 변수 방식으로 작동
- --command에 공백/특수문자가 포함되면 cmd.exe 래퍼 필수

**GCP VM 정보:**
- 프로젝트: sanjuk-talk-bot
- 인스턴스: sanjuk-project (2026-04-05 sanjuk-talk-bot에서 이름 변경)
- Zone: us-central1-b
- External IP: 35.238.77.143 (고정 IP: sanjuk-static-ip)
