#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# UE 애니메이션 데일리 브리핑 – 매일 오전 9시 cron 설정 스크립트
# 사용법: bash setup_cron.sh
# ─────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIEFING_SCRIPT="$SCRIPT_DIR/briefing/briefing.py"
LOG_FILE="$SCRIPT_DIR/briefing/briefing.log"
ENV_FILE="$SCRIPT_DIR/briefing/.env"
PYTHON_BIN="$(which python3)"

# .env 파일 확인
if [[ ! -f "$ENV_FILE" ]]; then
    echo "⚠️  .env 파일이 없습니다."
    echo "   cp $SCRIPT_DIR/briefing/.env.example $ENV_FILE"
    echo "   위 명령어로 생성 후 API 키를 입력해주세요."
    exit 1
fi

# requirements 설치 여부 확인
if ! $PYTHON_BIN -c "import anthropic, notion_client" &>/dev/null; then
    echo "📦 패키지 설치 중..."
    $PYTHON_BIN -m pip install -r "$SCRIPT_DIR/briefing/requirements.txt" -q
fi

# 기존 cron 항목 제거 후 새로 추가
CRON_JOB="0 9 * * * cd $SCRIPT_DIR && $PYTHON_BIN $BRIEFING_SCRIPT >> $LOG_FILE 2>&1"

# 현재 crontab 가져오기 (비어있어도 오류 없이 처리)
CURRENT_CRON=$(crontab -l 2>/dev/null || true)

# 기존 briefing.py 항목 제거
FILTERED_CRON=$(echo "$CURRENT_CRON" | grep -v "briefing.py" || true)

# 새 cron 항목 추가
NEW_CRON="$FILTERED_CRON
$CRON_JOB"

echo "$NEW_CRON" | crontab -

echo ""
echo "✅ Cron 설정 완료!"
echo "   ⏰ 매일 오전 09:00 자동 실행"
echo "   📁 로그: $LOG_FILE"
echo "   📋 확인: crontab -l"
echo ""
echo "   수동 실행: $PYTHON_BIN $BRIEFING_SCRIPT"
echo "   전체 실행: $PYTHON_BIN $BRIEFING_SCRIPT --all"
echo ""
