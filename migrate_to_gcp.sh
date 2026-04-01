#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Railway → GCP 봇 통합 이전 스크립트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# 대상: 산적주식비서, UE5 가이드, 운세 봇
# 사전 조건: GCP e2-micro에 수다봇이 이미 실행 중
#
# 사용법: bash migrate_to_gcp.sh
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -euo pipefail

echo "━━━ Railway → GCP 봇 이전 시작 ━━━"
echo ""

# GitHub PAT 입력
read -p "GitHub PAT 토큰: " GH_TOKEN
echo ""

# ─── 공통 환경변수 ─────────────────────────
read -p "TELEGRAM_CHAT_ID [8799420252]: " CHAT_ID
CHAT_ID=${CHAT_ID:-8799420252}

read -p "GEMINI_API_KEY: " GEMINI_KEY
echo ""

HOME_DIR="$HOME"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 산적주식비서 챗봇
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━ [1/3] 산적주식비서 챗봇 ━━━"

STOCK_DIR="$HOME_DIR/notion-stock-update"
if [ ! -d "$STOCK_DIR" ]; then
    git clone --depth 1 "https://${GH_TOKEN}@github.com/kanzaka110/notion-stock-update.git" "$STOCK_DIR"
else
    echo "이미 존재합니다. pull합니다..."
    cd "$STOCK_DIR" && git pull
fi

cd "$STOCK_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --quiet -r requirements.txt
deactivate

read -p "산적주식비서 TELEGRAM_BOT_TOKEN: " STOCK_BOT_TOKEN

cat > "$STOCK_DIR/.env" << EOL
TELEGRAM_BOT_TOKEN=${STOCK_BOT_TOKEN}
TELEGRAM_CHAT_ID=${CHAT_ID}
GEMINI_API_KEY=${GEMINI_KEY}
EOL

sudo tee /etc/systemd/system/stock-bot.service > /dev/null << EOL
[Unit]
Description=Telegram Bot - 산적주식비서
After=network.target
[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${STOCK_DIR}
EnvironmentFile=${STOCK_DIR}/.env
ExecStart=${STOCK_DIR}/venv/bin/python scripts/telegram_bot.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOL

echo "산적주식비서 완료!"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. UE5 가이드 챗봇
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━ [2/3] UE5 가이드 챗봇 ━━━"

UE_DIR="$HOME_DIR/desktop-tutorial"
if [ ! -d "$UE_DIR" ]; then
    git clone --depth 1 "https://${GH_TOKEN}@github.com/kanzaka110/desktop-tutorial.git" "$UE_DIR"
else
    echo "이미 존재합니다. pull합니다..."
    cd "$UE_DIR" && git pull
fi

cd "$UE_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --quiet -r requirements.txt
deactivate

read -p "UE5 가이드 TELEGRAM_BOT_TOKEN: " UE_BOT_TOKEN

cat > "$UE_DIR/.env" << EOL
TELEGRAM_BOT_TOKEN=${UE_BOT_TOKEN}
TELEGRAM_CHAT_ID=${CHAT_ID}
GEMINI_API_KEY=${GEMINI_KEY}
EOL

sudo tee /etc/systemd/system/ue-bot.service > /dev/null << EOL
[Unit]
Description=Telegram Bot - UE5 가이드
After=network.target
[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${UE_DIR}
EnvironmentFile=${UE_DIR}/.env
ExecStart=${UE_DIR}/venv/bin/python scripts/telegram_bot.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOL

echo "UE5 가이드 완료!"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 운세 봇
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━ [3/3] 운세 봇 ━━━"

LUCK_DIR="$HOME_DIR/luck-bot"
if [ ! -d "$LUCK_DIR" ]; then
    git clone --depth 1 "https://${GH_TOKEN}@github.com/kanzaka110/luck-bot.git" "$LUCK_DIR"
else
    echo "이미 존재합니다. pull합니다..."
    cd "$LUCK_DIR" && git pull
fi

cd "$LUCK_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --quiet -r requirements.txt
deactivate

read -p "운세 봇 TELEGRAM_BOT_TOKEN: " LUCK_BOT_TOKEN
read -p "ANTHROPIC_API_KEY (Sonnet 브리핑용): " ANTHROPIC_KEY

cat > "$LUCK_DIR/.env" << EOL
TELEGRAM_BOT_TOKEN=${LUCK_BOT_TOKEN}
TELEGRAM_CHAT_ID=${CHAT_ID}
GEMINI_API_KEY=${GEMINI_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
EOL

sudo tee /etc/systemd/system/luck-bot.service > /dev/null << EOL
[Unit]
Description=Telegram Bot - 나의 운세
After=network.target
[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${LUCK_DIR}
EnvironmentFile=${LUCK_DIR}/.env
ExecStart=${LUCK_DIR}/venv/bin/python luck_bot.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOL

echo "운세 봇 완료!"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 서비스 시작
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "━━━ 서비스 등록 및 시작 ━━━"

sudo systemctl daemon-reload

for svc in stock-bot ue-bot luck-bot; do
    sudo systemctl enable "$svc"
    sudo systemctl start "$svc"
    echo "$svc: $(sudo systemctl is-active $svc)"
done

echo ""
echo "━━━ 이전 완료! ━━━"
echo ""
echo "상태 확인:"
echo "  sudo systemctl status stock-bot"
echo "  sudo systemctl status ue-bot"
echo "  sudo systemctl status luck-bot"
echo "  sudo systemctl status chatbot"
echo ""
echo "전체 로그:"
echo "  sudo journalctl -u stock-bot -f"
echo "  sudo journalctl -u ue-bot -f"
echo "  sudo journalctl -u luck-bot -f"
echo ""
echo "⚠️  Railway 서비스를 중지하는 것을 잊지 마세요!"
