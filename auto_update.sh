#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GitHub → GCP 자동 동기화
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# cron으로 매 10분마다 실행.
# 변경이 있는 레포만 pull하고 해당 봇만 재시작.

LOG="/tmp/auto_update.log"
echo "$(date '+%Y-%m-%d %H:%M:%S') 동기화 시작" >> "$LOG"

restart_if_changed() {
    local repo_dir="$1"
    local service="$2"

    if [ ! -d "$repo_dir" ]; then
        return
    fi

    cd "$repo_dir"
    git fetch origin --quiet 2>/dev/null

    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master 2>/dev/null)

    if [ "$LOCAL" != "$REMOTE" ]; then
        git pull --quiet origin main 2>/dev/null || git pull --quiet origin master 2>/dev/null
        sudo systemctl restart "$service"
        echo "$(date '+%Y-%m-%d %H:%M:%S') $service 업데이트 + 재시작" >> "$LOG"
    fi
}

restart_if_changed "$HOME/Sanjuk-Claude-Code" "chatbot"
restart_if_changed "$HOME/notion-stock-update" "stock-bot"
restart_if_changed "$HOME/desktop-tutorial" "ue-bot"
restart_if_changed "$HOME/desktop-tutorial" "game-news-bot"
restart_if_changed "$HOME/luck-bot" "luck-bot"
