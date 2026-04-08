#!/bin/bash
# GCP VM에서 remote-control 재시작 (레포 pull + tmux 재시작)
# 실행: gcloud compute ssh sanjuk-project --zone=us-central1-b < scripts/gcp-restart-remote.sh

REPO_DIR="$HOME/Sanjuk-Notion-Telegram-Bot"
TMUX_SESSION="telegram"
SESSION_NAME="Sanjuk-Telegram-Bot (GCP)"

# 레포 최신화
cd "$REPO_DIR" && git pull origin master 2>/dev/null

# 기존 세션 정리 후 재시작
tmux kill-session -t "$TMUX_SESSION" 2>/dev/null
tmux new-session -d -s "$TMUX_SESSION" -c "$REPO_DIR" \
    "claude remote-control --name '$SESSION_NAME'"

echo "remote-control 재시작 완료 — 모바일에서 '$SESSION_NAME' 접속 가능"
