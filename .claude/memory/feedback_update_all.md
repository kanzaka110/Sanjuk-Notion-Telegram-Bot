---
name: Push/Pull Sync Commands
description: "푸시"=전체 동기화 아웃바운드, "풀"=외부→로컬 동기화, "최신업데이트"=푸시와 동일
type: feedback
originSessionId: abf5e759-3aed-4827-a22e-aa37455b2978
---
## "푸시" (또는 "최신업데이트")

로컬 → 외부 전체 동기화. 묻지 않고 순서대로 실행:

1. **메모리** — 변경/추가할 메모리 저장 (MEMORY.md 인덱스 포함)
2. **GitHub** — 변경사항 git add + commit + push origin master
3. **GCP 코드** — SSH로 git pull + 변경된 봇 재시작 (코드 변경 있을 때만)
   ```
   cmd.exe //c "C:\dev\Sanjuk-Notion-Telegram-Bot\gcp-ssh.cmd" "sudo -u kanzaka110 bash -c 'cd ~/Sanjuk-Notion-Telegram-Bot && git pull origin master'"
   ```
4. **GCP 메모리** — Claude Code 메모리+규칙을 GCP에 동기화
   ```
   cmd.exe //c "C:\dev\Sanjuk-Notion-Telegram-Bot\scripts\claude-config-push.cmd"
   ```
5. **모바일** — 리모트 트리거 설정 변경 있으면 업데이트

## "풀"

외부 → 로컬 동기화:

1. **GitHub** — git fetch + 원격 변경사항 확인 + git pull
2. **GCP** — SSH로 GCP 상태 확인 (로컬에 없는 변경사항 체크)
   ```
   cmd.exe //c "C:\dev\Sanjuk-Notion-Telegram-Bot\gcp-ssh.cmd" "cd ~/Sanjuk-Notion-Telegram-Bot && git log --oneline -5"
   ```
3. **동기화** — 차이가 있으면 로컬에 반영, 메모리 업데이트

**Why:** 매번 세 곳을 따로 요청하는 것이 번거로움. 한 마디로 전부 처리되길 원함.
**How to apply:** "푸시", "풀", "최신업데이트" 또는 유사 표현 사용 시 묻지 않고 해당 워크플로우 실행.
