#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 브리핑 cron 설정 스크립트
# GitHub Actions → GCP cron 이전
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 사용법: bash setup_briefing_cron.sh
# GCP e2-micro 인스턴스에서 실행 (Asia/Seoul 타임존 기준)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -euo pipefail

# ── 경로 설정 (통합 리포 단일 경로) ───────────────────────
REPO_DIR="$HOME/Sanjuk-Notion-Telegram-Bot"
UE_DIR="$REPO_DIR/UE_bot"
GAMENEWS_DIR="$REPO_DIR/GameNews_bot"
LOG_DIR="$HOME/logs/briefing"
# 주식 관련은 Sanjuk-Stock-Simulator 별도 리포로 이전됨

# ── 사전 검증 ──────────────────────────────────────────────
echo "🔍 사전 검증 중..."

if [ ! -d "$REPO_DIR" ]; then
    echo "❌ 리포 디렉토리 없음: $REPO_DIR"
    exit 1
fi

for dir in "$UE_DIR" "$GAMENEWS_DIR"; do
    if [ ! -d "$dir" ]; then
        echo "❌ 디렉토리 없음: $dir"
        exit 1
    fi
done

if [ ! -f "$REPO_DIR/.env" ]; then
    echo "⚠️  .env 파일 없음: $REPO_DIR/.env"
    echo "   API 키가 설정되어 있는지 확인하세요."
    exit 1
fi

# ── 로그 디렉토리 생성 ────────────────────────────────────
mkdir -p "$LOG_DIR"

# ── venv 및 패키지 확인 ───────────────────────────────────
echo "📦 패키지 확인 중..."

# UE_bot
if [ ! -d "$UE_DIR/venv" ]; then
    echo "  → UE_bot venv 생성..."
    python3 -m venv "$UE_DIR/venv"
fi
"$UE_DIR/venv/bin/pip" install -q -r "$UE_DIR/requirements.txt"

# GameNews_bot
if [ ! -d "$GAMENEWS_DIR/venv" ]; then
    echo "  → GameNews_bot venv 생성..."
    python3 -m venv "$GAMENEWS_DIR/venv"
fi
"$GAMENEWS_DIR/venv/bin/pip" install -q -r "$GAMENEWS_DIR/requirements.txt"

# ── 브리핑 래퍼 스크립트 생성 ─────────────────────────────
# 각 브리핑마다 .env 로딩 + venv 활성화 + 스크립트 실행

REPO_ENV="$REPO_DIR/.env"

# 주식 브리핑/주가 업데이트는 Sanjuk-Stock-Simulator에서 관리
# ~/run_stock_briefing_kr.sh, ~/run_stock_briefing_us.sh, ~/run_stock_update.sh
# → Sanjuk-Stock-Simulator/deploy/ 래퍼 사용

# 1) UE 애니메이션 브리핑
cat > "$HOME/run_ue_briefing.sh" << SCRIPT
#!/bin/bash
cd "$UE_DIR"
set -a; source "$REPO_ENV"; set +a
./venv/bin/python briefing.py >> "$LOG_DIR/ue_briefing.log" 2>&1
SCRIPT
chmod +x "$HOME/run_ue_briefing.sh"

# 5) 게임뉴스 브리핑
cat > "$HOME/run_game_news.sh" << SCRIPT
#!/bin/bash
cd "$GAMENEWS_DIR"
set -a; source "$REPO_ENV"; set +a
export TELEGRAM_BOT_TOKEN="\$GAME_NEWS_BOT_TOKEN"
./venv/bin/python game_news.py >> "$LOG_DIR/game_news.log" 2>&1
SCRIPT
chmod +x "$HOME/run_game_news.sh"

echo "✅ 래퍼 스크립트 2개 생성 완료 (주식 관련은 Sanjuk-Stock-Simulator에서 관리)"

# ── crontab 등록 ──────────────────────────────────────────
# 타임존: Asia/Seoul (KST)
# ※ GCP 인스턴스 타임존이 UTC인 경우 TZ=Asia/Seoul 사용

echo "⏰ crontab 등록 중..."

# 기존 crontab 보존 (브리핑 관련 항목만 교체)
CURRENT_CRON=$(crontab -l 2>/dev/null || true)
FILTERED_CRON=$(echo "$CURRENT_CRON" | grep -v "run_stock_briefing\|run_stock_update\|run_ue_briefing\|run_game_news\|briefing.py" || true)

# 새 cron 항목 추가
NEW_CRON="$FILTERED_CRON

# ━━━ 브리핑 자동화 (GitHub Actions 대체) ━━━
# GCP 서버는 UTC 기준. KST = UTC + 9시간
# cron의 TZ= 변수는 스케줄 시간에 영향 없음 → UTC로 직접 계산

# 📊 투자 브리핑 - 국내장 시작 전 (KST 08:30 = UTC 23:30 전날, 월~금)
30 23 * * 0-4 $HOME/run_stock_briefing_kr.sh

# 📊 투자 브리핑 - 미국장 시작 전 (KST 22:30 = UTC 13:30, 월~금)
30 13 * * 1-5 $HOME/run_stock_briefing_us.sh

# 💹 주가 업데이트 - 국내 개장 (KST 09:00 = UTC 00:00)
0 0 * * * $HOME/run_stock_update.sh

# 💹 주가 업데이트 - 국내 마감 (KST 15:30 = UTC 06:30)
30 6 * * * $HOME/run_stock_update.sh

# 💹 주가 업데이트 - 미국 개장 (KST 22:30 = UTC 13:30)
30 13 * * * $HOME/run_stock_update.sh

# 💹 주가 업데이트 - 미국 마감 (KST 05:00 = UTC 20:00)
0 20 * * * $HOME/run_stock_update.sh

# 🎮 UE 애니메이션 데일리 브리핑 (KST 09:00 = UTC 00:00, 매일)
0 0 * * * $HOME/run_ue_briefing.sh

# 🕹️ 게임뉴스 데일리 브리핑 (KST 09:15 = UTC 00:15, 매일)
15 0 * * * $HOME/run_game_news.sh
"

echo "$NEW_CRON" | crontab -

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 브리핑 cron 설정 완료!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 등록된 스케줄:"
echo "  📊 투자 KR 브리핑  : 월~금 08:30 KST"
echo "  📊 투자 US 브리핑  : 월~금 22:30 KST"
echo "  💹 주가 업데이트    : 09:00, 15:30, 22:30, 05:00 KST"
echo "  🎮 UE 브리핑       : 매일 09:00 KST"
echo "  🕹️ 게임뉴스        : 매일 09:15 KST"
echo ""
echo "📁 로그: $LOG_DIR/"
echo "📋 확인: crontab -l"
echo ""
echo "⚠️  중요: $REPO_DIR/.env 파일에 아래 키가 모두 있는지 확인하세요:"
echo ""
echo "  GEMINI_API_KEY, CLAUDE_API_KEY, ANTHROPIC_API_KEY"
echo "  NOTION_API_KEY, NOTION_DB_ID, NOTION_DATABASE_ID"
echo "  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID"
echo "  GAME_NEWS_BOT_TOKEN"
echo ""
