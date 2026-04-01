#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GCP 봇 통합 이전 스크립트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# 단일 리포(Sanjuk-Notion-Telegram-Bot)에서 봇 5개 배포
# 사전 조건: GCP e2-micro 인스턴스
#
# 사용법: bash migrate_to_gcp.sh
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -euo pipefail

echo "━━━ GCP 봇 통합 이전 시작 ━━━"
echo ""

# GitHub PAT 입력
read -p "GitHub PAT 토큰: " GH_TOKEN
echo ""

# ─── 공통 환경변수 ─────────────────────────
read -p "TELEGRAM_CHAT_ID [8799420252]: " CHAT_ID
CHAT_ID=${CHAT_ID:-8799420252}

read -p "GEMINI_API_KEY: " GEMINI_KEY
read -p "ANTHROPIC_API_KEY: " ANTHROPIC_KEY
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 리포 클론
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━ [1/6] 리포 클론 ━━━"

REPO_DIR="$HOME/Sanjuk-Notion-Telegram-Bot"
if [ ! -d "$REPO_DIR" ]; then
    git clone --depth 1 "https://${GH_TOKEN}@github.com/kanzaka110/Sanjuk-Notion-Telegram-Bot.git" "$REPO_DIR"
else
    echo "이미 존재합니다. pull합니다..."
    cd "$REPO_DIR" && git pull
fi

echo "리포 클론 완료!"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 각 봇별 venv 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━ [2/6] 가상환경 생성 ━━━"

for bot_dir in Chat_bot Stock_bot UE_bot GameNews_bot Luck_bot; do
    BOT_PATH="$REPO_DIR/$bot_dir"
    if [ -f "$BOT_PATH/requirements.txt" ]; then
        echo "  $bot_dir venv 생성 중..."
        python3 -m venv "$BOT_PATH/venv"
        "$BOT_PATH/venv/bin/pip" install --quiet -r "$BOT_PATH/requirements.txt"
    fi
done

echo "가상환경 생성 완료!"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 봇 토큰 입력
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━ [3/6] 봇 토큰 입력 ━━━"

read -p "산적 수다방 TELEGRAM_BOT_TOKEN: " CHAT_BOT_TOKEN
read -p "산적주식비서 TELEGRAM_BOT_TOKEN: " STOCK_BOT_TOKEN
read -p "UE5 가이드 TELEGRAM_BOT_TOKEN: " UE_BOT_TOKEN
read -p "게임뉴스 GAME_NEWS_BOT_TOKEN: " GAME_NEWS_BOT_TOKEN
read -p "나의 운세 TELEGRAM_BOT_TOKEN: " LUCK_BOT_TOKEN
read -p "GITHUB_TOKEN (메모리 push용): " GH_PUSH_TOKEN
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. .env 파일 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━ [4/6] .env 파일 생성 ━━━"

# 각 봇별 .env
cat > "$REPO_DIR/Chat_bot/.env" << EOL
TELEGRAM_BOT_TOKEN=${CHAT_BOT_TOKEN}
TELEGRAM_CHAT_ID=${CHAT_ID}
GEMINI_API_KEY=${GEMINI_KEY}
GITHUB_TOKEN=${GH_PUSH_TOKEN}
GITHUB_REPO=kanzaka110/Sanjuk-Notion-Telegram-Bot
EOL

cat > "$REPO_DIR/Stock_bot/.env" << EOL
TELEGRAM_BOT_TOKEN=${STOCK_BOT_TOKEN}
TELEGRAM_CHAT_ID=${CHAT_ID}
GEMINI_API_KEY=${GEMINI_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
EOL

cat > "$REPO_DIR/UE_bot/.env" << EOL
TELEGRAM_BOT_TOKEN=${UE_BOT_TOKEN}
TELEGRAM_CHAT_ID=${CHAT_ID}
GEMINI_API_KEY=${GEMINI_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
EOL

cat > "$REPO_DIR/GameNews_bot/.env" << EOL
TELEGRAM_BOT_TOKEN=${GAME_NEWS_BOT_TOKEN}
TELEGRAM_CHAT_ID=${CHAT_ID}
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
EOL

cat > "$REPO_DIR/Luck_bot/.env" << EOL
TELEGRAM_BOT_TOKEN=${LUCK_BOT_TOKEN}
TELEGRAM_CHAT_ID=${CHAT_ID}
GEMINI_API_KEY=${GEMINI_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
EOL

echo ".env 파일 생성 완료!"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. systemd 서비스 등록
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━ [5/6] systemd 서비스 등록 ━━━"

USERNAME=$(whoami)

# 산적 수다방
sudo tee /etc/systemd/system/chatbot.service > /dev/null << EOL
[Unit]
Description=Telegram Bot - 산적 수다방
After=network.target
[Service]
Type=simple
User=${USERNAME}
WorkingDirectory=${REPO_DIR}/Chat_bot
EnvironmentFile=${REPO_DIR}/Chat_bot/.env
ExecStart=${REPO_DIR}/Chat_bot/venv/bin/python chat_bot.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOL

# 산적주식비서
sudo tee /etc/systemd/system/stock-bot.service > /dev/null << EOL
[Unit]
Description=Telegram Bot - 산적주식비서
After=network.target
[Service]
Type=simple
User=${USERNAME}
WorkingDirectory=${REPO_DIR}/Stock_bot
EnvironmentFile=${REPO_DIR}/Stock_bot/.env
ExecStart=${REPO_DIR}/Stock_bot/venv/bin/python scripts/telegram_bot.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOL

# UE5 가이드
sudo tee /etc/systemd/system/ue-bot.service > /dev/null << EOL
[Unit]
Description=Telegram Bot - UE5 가이드
After=network.target
[Service]
Type=simple
User=${USERNAME}
WorkingDirectory=${REPO_DIR}/UE_bot
EnvironmentFile=${REPO_DIR}/UE_bot/.env
ExecStart=${REPO_DIR}/UE_bot/venv/bin/python telegram_bot.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOL

# 게임뉴스
sudo tee /etc/systemd/system/game-news-bot.service > /dev/null << EOL
[Unit]
Description=Telegram Bot - 게임뉴스
After=network.target
[Service]
Type=simple
User=${USERNAME}
WorkingDirectory=${REPO_DIR}/GameNews_bot
EnvironmentFile=${REPO_DIR}/GameNews_bot/.env
ExecStart=${REPO_DIR}/GameNews_bot/venv/bin/python game_news_bot.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOL

# 나의 운세
sudo tee /etc/systemd/system/luck-bot.service > /dev/null << EOL
[Unit]
Description=Telegram Bot - 나의 운세
After=network.target
[Service]
Type=simple
User=${USERNAME}
WorkingDirectory=${REPO_DIR}/Luck_bot
EnvironmentFile=${REPO_DIR}/Luck_bot/.env
ExecStart=${REPO_DIR}/Luck_bot/venv/bin/python luck_bot.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOL

echo "서비스 등록 완료!"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. 서비스 시작
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━ [6/6] 서비스 시작 ━━━"

sudo systemctl daemon-reload

for svc in chatbot stock-bot ue-bot game-news-bot luck-bot; do
    sudo systemctl enable "$svc"
    sudo systemctl start "$svc"
    echo "$svc: $(sudo systemctl is-active $svc)"
done

echo ""
echo "━━━ 이전 완료! ━━━"
echo ""
echo "상태 확인:"
echo "  sudo systemctl status chatbot"
echo "  sudo systemctl status stock-bot"
echo "  sudo systemctl status ue-bot"
echo "  sudo systemctl status game-news-bot"
echo "  sudo systemctl status luck-bot"
echo ""
echo "전체 로그:"
echo "  sudo journalctl -u chatbot -f"
echo "  sudo journalctl -u stock-bot -f"
echo "  sudo journalctl -u ue-bot -f"
echo "  sudo journalctl -u game-news-bot -f"
echo "  sudo journalctl -u luck-bot -f"
