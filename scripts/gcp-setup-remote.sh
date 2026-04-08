#!/bin/bash
# GCP VM에서 Sanjuk-Telegram-Bot 원격 세션 설정
# 실행: gcloud compute ssh sanjuk-project --zone=us-central1-b < scripts/gcp-setup-remote.sh

set -e

REPO_DIR="$HOME/Sanjuk-Notion-Telegram-Bot"
TMUX_SESSION="telegram"
SESSION_NAME="Sanjuk-Telegram-Bot (GCP)"

echo "=== Sanjuk-Telegram-Bot GCP Remote Setup ==="

# 1. 레포 업데이트
if [ -d "$REPO_DIR" ]; then
    echo "[1/4] 기존 레포 업데이트..."
    cd "$REPO_DIR"
    git pull origin master
else
    echo "[1/4] 레포 클론..."
    git clone https://github.com/kanzaka110/Sanjuk-Notion-Telegram-Bot.git "$REPO_DIR"
    cd "$REPO_DIR"
fi

# 2. Claude Code 설치 확인
echo "[2/4] Claude Code 확인..."
if command -v claude &>/dev/null; then
    echo "  Claude Code: $(claude --version 2>/dev/null || echo 'installed')"
else
    echo "  Claude Code 미설치 — 설치 중..."
    curl -fsSL https://claude.ai/install.sh | bash
fi

# 3. 기존 tmux 세션 정리
echo "[3/4] tmux 세션 설정..."
if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    echo "  기존 '$TMUX_SESSION' 세션 종료..."
    tmux kill-session -t "$TMUX_SESSION"
fi

# 4. 새 tmux 세션에서 remote-control 실행
echo "[4/4] remote-control 시작..."
tmux new-session -d -s "$TMUX_SESSION" -c "$REPO_DIR" \
    "claude remote-control --name '$SESSION_NAME'"

echo ""
echo "=== 설정 완료 ==="
echo "  tmux 세션: $TMUX_SESSION"
echo "  Claude 세션명: $SESSION_NAME"
echo "  확인: tmux attach -t $TMUX_SESSION"
echo "  모바일: claude.ai/code 에서 '$SESSION_NAME' 선택"
