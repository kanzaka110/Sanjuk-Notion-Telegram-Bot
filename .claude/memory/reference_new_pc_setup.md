---
name: New PC Setup Guide
description: 새 PC에서 개발환경 셋업하는 전체 절차 (클론부터 GCP 접근까지)
type: reference
---

## 새 PC 셋업 절차

### 1. 리포 클론
```bash
git clone https://github.com/kanzaka110/Sanjuk-Notion-Telegram-Bot.git
cd Sanjuk-Notion-Telegram-Bot
```

### 2. 셋업 스크립트 실행
```bash
bash setup.sh
```
- Claude 메모리를 리포 → 로컬 Claude 경로로 junction/symlink 연결
- GCP SSH 래퍼(gcp-ssh.cmd) 자동 생성

### 3. GCP gcloud CLI 설��� (미설치 시)
```bash
winget install Google.CloudSDK
```
설치 후 셸 재시작 필요.

### 4. GCP 인증 (최초 1회)
```bash
gcloud auth login
gcloud config set project sanjuk-talk-bot
```
브���우저에서 Google 계정(kanzaka110@gmail.com) 로그인.

### 5. GCP SSH 최초 접속 (호스트 키 등록)
```bash
gcloud compute ssh sanjuk-project --zone=us-central1-b --command="hostname"
```
`Store key in cache?` → `y` 입력.

### 6. Claude Code 실행
프로젝트 디렉토리에서 Claude Code 시작하면 메모리가 자동 로드됨.

### 메모��� 동기화
- 메모리 변경 후: `git add .claude/memory/ && git commit && git push`
- 다른 PC에서: `git pull` → 즉시 반영
