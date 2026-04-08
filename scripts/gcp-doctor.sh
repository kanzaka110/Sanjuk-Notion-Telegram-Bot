#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GCP Health Check — 봇 4개 + 시스템 상태 점검
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 사용법:
#   로컬: gcloud compute ssh sanjuk-project --zone=us-central1-b < scripts/gcp-doctor.sh
#   GCP:  bash ~/Sanjuk-Notion-Telegram-Bot/scripts/gcp-doctor.sh

SERVICES=("chatbot" "ue-bot" "game-news-bot" "luck-bot")
REPO_DIR="$HOME/Sanjuk-Notion-Telegram-Bot"
PASS="[OK]"
FAIL="[FAIL]"
WARN="[WARN]"
SKIP="[SKIP]"

passed=0
failed=0
warned=0

# ─── 헬퍼 함수 ─────────────────────────────────────────
mark_pass() { echo "  $PASS $1"; ((passed++)); }
mark_fail() { echo "  $FAIL $1"; ((failed++)); }
mark_warn() { echo "  $WARN $1"; ((warned++)); }

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  GCP Doctor — $(date '+%Y-%m-%d %H:%M:%S KST')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ─── 1. systemd 서비스 상태 ──────────────────────────────
echo "[1/5] systemd 서비스 상태"
for svc in "${SERVICES[@]}"; do
    status=$(systemctl is-active "$svc" 2>/dev/null)
    if [ "$status" = "active" ]; then
        uptime=$(systemctl show "$svc" --property=ActiveEnterTimestamp --value 2>/dev/null)
        mark_pass "$svc: active (since $uptime)"
    elif [ "$status" = "inactive" ]; then
        mark_warn "$svc: inactive"
    else
        mark_fail "$svc: $status"
    fi
done
echo ""

# ─── 2. 최근 에러 로그 ──────────────────────────────────
echo "[2/5] 최근 에러 로그 (1시간 이내)"
for svc in "${SERVICES[@]}"; do
    errors=$(journalctl -u "$svc" --since "1 hour ago" -p err --no-pager -q 2>/dev/null | wc -l)
    if [ "$errors" -eq 0 ]; then
        mark_pass "$svc: 에러 없음"
    elif [ "$errors" -lt 5 ]; then
        mark_warn "$svc: 에러 ${errors}건"
    else
        mark_fail "$svc: 에러 ${errors}건"
        journalctl -u "$svc" --since "1 hour ago" -p err --no-pager -q 2>/dev/null | tail -3 | sed 's/^/        /'
    fi
done
echo ""

# ─── 3. .env 파일 존재 확인 ──────────────────────────────
echo "[3/5] .env 파일 확인"
declare -A ENV_PATHS=(
    ["chatbot"]="$REPO_DIR/Chat_bot/.env"
    ["luck-bot"]="$REPO_DIR/Luck_bot/.env"
    ["ue-bot"]="$REPO_DIR/.env"
    ["game-news-bot"]="$REPO_DIR/.env"
)

for svc in "${SERVICES[@]}"; do
    env_path="${ENV_PATHS[$svc]}"
    if [ -f "$env_path" ]; then
        # 필수 키 존재 확인 (값은 검사하지 않음)
        missing=""
        for key in TELEGRAM_BOT_TOKEN GEMINI_API_KEY; do
            if ! grep -q "^${key}=" "$env_path" 2>/dev/null; then
                missing="$missing $key"
            fi
        done
        if [ -z "$missing" ]; then
            mark_pass "$svc: $env_path (필수 키 확인)"
        else
            mark_warn "$svc: 누락 키:$missing"
        fi
    else
        mark_fail "$svc: $env_path 없음"
    fi
done
echo ""

# ─── 4. 시스템 리소스 ───────────────────────────────────
echo "[4/5] 시스템 리소스"

# 디스크
disk_usage=$(df -h / 2>/dev/null | awk 'NR==2 {print $5}' | tr -d '%')
disk_total=$(df -h / 2>/dev/null | awk 'NR==2 {print $2}')
disk_avail=$(df -h / 2>/dev/null | awk 'NR==2 {print $4}')
if [ -n "$disk_usage" ]; then
    if [ "$disk_usage" -lt 70 ]; then
        mark_pass "디스크: ${disk_usage}% 사용 (${disk_avail}/${disk_total} 여유)"
    elif [ "$disk_usage" -lt 85 ]; then
        mark_warn "디스크: ${disk_usage}% 사용 — 정리 권장"
    else
        mark_fail "디스크: ${disk_usage}% 사용 — 즉시 정리 필요"
        echo "        sudo apt-get clean && sudo journalctl --vacuum-time=3d"
    fi
fi

# 메모리 (RAM + Swap)
mem_info=$(free -m 2>/dev/null | awk 'NR==2 {printf "%d/%dMB (%.0f%%)", $3, $2, $3/$2*100}')
mem_pct=$(free -m 2>/dev/null | awk 'NR==2 {printf "%.0f", $3/$2*100}')
swap_info=$(free -m 2>/dev/null | awk 'NR==3 {printf "%d/%dMB", $3, $2}')
if [ -n "$mem_pct" ]; then
    if [ "$mem_pct" -lt 80 ]; then
        mark_pass "메모리: $mem_info, Swap: $swap_info"
    elif [ "$mem_pct" -lt 95 ]; then
        mark_warn "메모리: $mem_info, Swap: $swap_info"
    else
        mark_fail "메모리: $mem_info — 과부하"
    fi
fi

# 로드 평균
load=$(uptime 2>/dev/null | awk -F'load average:' '{print $2}' | xargs)
if [ -n "$load" ]; then
    mark_pass "로드 평균: $load"
fi
echo ""

# ─── 5. Git 동기화 상태 ─────────────────────────────────
echo "[5/5] Git 동기화 상태"
if [ -d "$REPO_DIR/.git" ]; then
    cd "$REPO_DIR"
    git fetch origin --quiet 2>/dev/null
    local_hash=$(git rev-parse --short HEAD 2>/dev/null)
    remote_hash=$(git rev-parse --short origin/master 2>/dev/null || git rev-parse --short origin/main 2>/dev/null)

    if [ "$local_hash" = "$remote_hash" ]; then
        mark_pass "최신 상태 ($local_hash)"
    else
        mark_warn "동기화 필요: 로컬=$local_hash, 리모트=$remote_hash"
    fi

    # auto_update cron 확인
    if crontab -l 2>/dev/null | grep -q "auto_update"; then
        mark_pass "auto_update cron 활성"
    else
        mark_warn "auto_update cron 미설정"
    fi
else
    mark_fail "리포 디렉토리 없음: $REPO_DIR"
fi
echo ""

# ─── 요약 ───────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  결과: $PASS $passed  $WARN $warned  $FAIL $failed"
if [ "$failed" -gt 0 ]; then
    echo "  상태: 문제 발견 — 위의 FAIL 항목을 확인하세요"
elif [ "$warned" -gt 0 ]; then
    echo "  상태: 경고 있음 — 권장 조치를 확인하세요"
else
    echo "  상태: 모두 정상"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
