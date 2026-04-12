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
GAMENEWS_DIR="$REPO_DIR/GameNews_bot"
LOG_DIR="$HOME/logs/briefing"
# 주식 관련은 Sanjuk-Stock-Simulator 별도 리포로 이전됨
# UE 관련은 Sanjuk-Unreal 별도 리포로 이전됨

# ── 사전 검증 ──────────────────────────────────────────────
echo "🔍 사전 검증 중..."

if [ ! -d "$REPO_DIR" ]; then
    echo "❌ 리포 디렉토리 없음: $REPO_DIR"
    exit 1
fi

if [ ! -d "$GAMENEWS_DIR" ]; then
    echo "❌ 디렉토리 없음: $GAMENEWS_DIR"
    exit 1
fi

if [ ! -f "$REPO_DIR/.env" ]; then
    echo "⚠️  .env 파일 없음: $REPO_DIR/.env"
    echo "   API 키가 설정되어 있는지 확인하세요."
    exit 1
fi

# ── 로그 디렉토리 생성 ────────────────────────────────────
mkdir -p "$LOG_DIR"

# ── venv 및 패키지 확인 ───────────────────────────────────
echo "📦 패키지 확인 중..."

# GameNews_bot (공유 venv 사용)
VENV_DIR="$REPO_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "  → 공유 venv 생성..."
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install -q -r "$GAMENEWS_DIR/requirements.txt"

# ── 브리핑 래퍼 스크립트 생성 ─────────────────────────────

REPO_ENV="$REPO_DIR/.env"

# 주식 브리핑/주가 업데이트는 Sanjuk-Stock-Simulator에서 관리
# UE 브리핑은 Sanjuk-Unreal에서 관리

# 게임뉴스 브리핑
cat > "$HOME/run_game_news.sh" << SCRIPT
#!/bin/bash
cd "$GAMENEWS_DIR"
set -a; source "$REPO_ENV"; set +a
export TELEGRAM_BOT_TOKEN="\$GAME_NEWS_BOT_TOKEN"
$VENV_DIR/bin/python game_news.py >> "$LOG_DIR/game_news.log" 2>&1
SCRIPT
chmod +x "$HOME/run_game_news.sh"

echo "✅ 래퍼 스크립트 1개 생성 완료 (주식은 Sanjuk-Stock-Simulator, UE는 Sanjuk-Unreal에서 관리)"

# ── crontab 등록 ──────────────────────────────────────────
echo "⏰ crontab 등록 중..."

# 기존 crontab 보존 (브리핑 관련 항목만 교체)
CURRENT_CRON=$(crontab -l 2>/dev/null || true)
FILTERED_CRON=$(echo "$CURRENT_CRON" | grep -v "run_game_news\|game_news.py" || true)

# 새 cron 항목 추가
NEW_CRON="$FILTERED_CRON

# ━━━ 게임뉴스 브리핑 자동화 ━━━
# GCP 서버는 UTC 기준. KST = UTC + 9시간

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
echo "  🕹️ 게임뉴스        : 매일 09:15 KST"
echo ""
echo "📁 로그: $LOG_DIR/"
echo "📋 확인: crontab -l"
