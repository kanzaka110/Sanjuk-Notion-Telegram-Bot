#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GitHub → GCP 자동 동기화
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# cron으로 매 10분마다 실행.
# 단일 리포(Sanjuk-Notion-Telegram-Bot)를 pull하고
# 변경이 있으면 모든 봇 서비스를 재시작.

LOG="/tmp/auto_update.log"
REPO_DIR="$HOME/Sanjuk-Notion-Telegram-Bot"

echo "$(date '+%Y-%m-%d %H:%M:%S') 동기화 시작" >> "$LOG"

if [ ! -d "$REPO_DIR" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') 리포 디렉토리 없음: $REPO_DIR" >> "$LOG"
    exit 1
fi

cd "$REPO_DIR"
git fetch origin --quiet 2>/dev/null

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/master 2>/dev/null || git rev-parse origin/main 2>/dev/null)

if [ "$LOCAL" != "$REMOTE" ]; then
    git pull --quiet origin master 2>/dev/null || git pull --quiet origin main 2>/dev/null
    echo "$(date '+%Y-%m-%d %H:%M:%S') 코드 업데이트 감지, 봇 재시작..." >> "$LOG"

    for svc in chatbot game-news-bot luck-bot; do
        sudo systemctl restart "$svc"
        echo "$(date '+%Y-%m-%d %H:%M:%S') $svc 재시작" >> "$LOG"
    done
fi
