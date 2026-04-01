#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 산적 수다방 - GCP e2-micro 원클릭 세팅
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# 사용법:
#   1. GCP Console → Compute Engine → VM 인스턴스 생성
#      - 이름: sanjuk-talk-bot
#      - 리전: us-central1 (무료 티어)
#      - 머신 유형: e2-micro
#      - OS: Debian 12
#   2. SSH 접속
#   3. 이 스크립트 실행:
#      curl -sL https://raw.githubusercontent.com/kanzaka110/Sanjuk-Claude-Code/main/Project/Telegram_Bot/Chat_bot/setup_gcp.sh | bash
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -euo pipefail

echo "━━━ 산적 수다방 GCP 세팅 시작 ━━━"

# ─── 1. 시스템 패키지 ───────────────────────
echo "[1/6] 시스템 패키지 업데이트..."
sudo apt update -y && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git

PYTHON=$(command -v python3)
echo "Python: $($PYTHON --version)"

# ─── 2. 프로젝트 클론 ──────────────────────
echo "[2/6] 프로젝트 클론..."
WORK_DIR="$HOME/Sanjuk-Claude-Code"
if [ -d "$WORK_DIR" ]; then
    echo "이미 존재합니다. pull합니다..."
    cd "$WORK_DIR" && git pull
else
    read -p "GitHub PAT 토큰 입력: " GH_TOKEN
    git clone "https://${GH_TOKEN}@github.com/kanzaka110/Sanjuk-Claude-Code.git" "$WORK_DIR"
fi

BOT_DIR="$WORK_DIR/Project/Telegram_Bot/Chat_bot"
cd "$BOT_DIR"

# ─── 3. 가상환경 + 의존성 ──────────────────
echo "[3/6] 가상환경 생성 및 의존성 설치..."
$PYTHON -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ─── 4. 환경변수 파일 ──────────────────────
echo "[4/6] 환경변수 설정..."
ENV_FILE="$BOT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo ".env 파일을 생성합니다."
    read -p "TELEGRAM_BOT_TOKEN: " TG_TOKEN
    read -p "TELEGRAM_CHAT_ID: " TG_CHAT_ID
    read -p "GEMINI_API_KEY: " GEMINI_KEY
    read -p "GITHUB_TOKEN (메모리 push용): " GH_PUSH_TOKEN

    cat > "$ENV_FILE" <<EOL
TELEGRAM_BOT_TOKEN=${TG_TOKEN}
TELEGRAM_CHAT_ID=${TG_CHAT_ID}
GEMINI_API_KEY=${GEMINI_KEY}
GITHUB_TOKEN=${GH_PUSH_TOKEN}
GITHUB_REPO=kanzaka110/Sanjuk-Claude-Code
EOL
    echo ".env 생성 완료!"
else
    echo ".env 이미 존재합니다."
fi

# ─── 5. systemd 서비스 등록 ────────────────
echo "[5/6] systemd 서비스 등록..."
SERVICE_FILE="/etc/systemd/system/chatbot.service"
USERNAME=$(whoami)

sudo tee "$SERVICE_FILE" > /dev/null <<EOL
[Unit]
Description=Telegram Chat Bot - 산적 수다방
After=network.target

[Service]
Type=simple
User=${USERNAME}
WorkingDirectory=${BOT_DIR}
EnvironmentFile=${BOT_DIR}/.env
ExecStart=${BOT_DIR}/venv/bin/python chat_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOL

sudo systemctl daemon-reload
sudo systemctl enable chatbot
sudo systemctl start chatbot

# ─── 6. 상태 확인 ─────────────────────────
echo "[6/6] 상태 확인..."
sleep 3
sudo systemctl status chatbot --no-pager

echo ""
echo "━━━ 세팅 완료! ━━━"
echo ""
echo "유용한 명령어:"
echo "  상태 확인:  sudo systemctl status chatbot"
echo "  로그 보기:  sudo journalctl -u chatbot -f"
echo "  재시작:     sudo systemctl restart chatbot"
echo "  중지:       sudo systemctl stop chatbot"
