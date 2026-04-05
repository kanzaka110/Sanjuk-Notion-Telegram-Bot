#!/bin/bash
# ═══════════════════════════════════════════════════════
# 새 PC 초기 셋업 스크립트
# 사용법: git clone 후 bash setup.sh 실행
# ═══════════════════════════════════════════════════════

set -e
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_BASE="$HOME/.claude"

echo "═══════════════════════════════════════════"
echo " 🔧 Sanjuk-Notion-Telegram-Bot 환경 셋업"
echo "═══════════════════════════════════════════"
echo ""

# ─── 1. Claude 메모리 동기화 ─────────────────────────
echo "📝 Claude 메모리 동기화..."

# 프로젝트별 메모리 경로 (Windows/Linux 호환)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    # Windows (Git Bash / MSYS2)
    WIN_REPO=$(cygpath -w "$REPO_DIR" 2>/dev/null || echo "$REPO_DIR")
    # Windows 경로에서 : 과 \ 를 -- 과 - 로 변환
    PROJECT_KEY=$(echo "$WIN_REPO" | sed 's/://g' | sed 's/\\/--/g' | sed 's/^-*//')
    MEMORY_TARGET="$CLAUDE_BASE/projects/$PROJECT_KEY/memory"
else
    # Linux/macOS
    PROJECT_KEY=$(echo "$REPO_DIR" | sed 's/\//-/g' | sed 's/^-//')
    MEMORY_TARGET="$CLAUDE_BASE/projects/$PROJECT_KEY/memory"
fi

mkdir -p "$(dirname "$MEMORY_TARGET")"

if [ -L "$MEMORY_TARGET" ] || [ "$(cmd.exe //c 'dir /AL "%MEMORY_TARGET%" 2>NUL | find "JUNCTION"' 2>/dev/null)" ]; then
    echo "  ✅ 이미 링크 설정됨: $MEMORY_TARGET"
elif [ -d "$MEMORY_TARGET" ]; then
    echo "  ⚠️  기존 메모리 디렉토리가 있습니다. 백업 후 링크 생성..."
    mv "$MEMORY_TARGET" "${MEMORY_TARGET}.bak.$(date +%Y%m%d%H%M%S)"
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        WIN_TARGET=$(cygpath -w "$MEMORY_TARGET" 2>/dev/null || echo "$MEMORY_TARGET")
        WIN_SOURCE=$(cygpath -w "$REPO_DIR/.claude/memory" 2>/dev/null || echo "$REPO_DIR/.claude/memory")
        cmd.exe //c mklink //J "$WIN_TARGET" "$WIN_SOURCE" > /dev/null 2>&1
    else
        ln -s "$REPO_DIR/.claude/memory" "$MEMORY_TARGET"
    fi
    echo "  ✅ 링크 생성 완료 (기존 파일은 .bak으로 백업됨)"
else
    mkdir -p "$(dirname "$MEMORY_TARGET")"
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        WIN_TARGET=$(cygpath -w "$MEMORY_TARGET" 2>/dev/null || echo "$MEMORY_TARGET")
        WIN_SOURCE=$(cygpath -w "$REPO_DIR/.claude/memory" 2>/dev/null || echo "$REPO_DIR/.claude/memory")
        cmd.exe //c mklink //J "$WIN_TARGET" "$WIN_SOURCE" > /dev/null 2>&1
    else
        ln -s "$REPO_DIR/.claude/memory" "$MEMORY_TARGET"
    fi
    echo "  ✅ 링크 생성 완료"
fi

# ─── 2. GCP gcloud CLI 확인 ──────────────────────────
echo ""
echo "☁️  GCP gcloud CLI 확인..."

GCLOUD_PATH="C:/Users/$USER/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd"
if [ -f "$GCLOUD_PATH" ] || command -v gcloud &>/dev/null; then
    echo "  ✅ gcloud CLI 설치됨"
else
    echo "  ❌ gcloud CLI 미설치"
    echo "     설치: winget install Google.CloudSDK"
    echo "     설치 후: gcloud auth login && gcloud config set project sanjuk-talk-bot"
fi

# ─── 3. GCP SSH 래퍼 생성 ────────────────────────────
echo ""
echo "🔗 GCP SSH 래퍼 생성..."

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    cat > "$REPO_DIR/gcp-ssh.cmd" << 'CMDEOF'
@echo off
"C:\Users\%USERNAME%\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" compute ssh sanjuk-project --zone=us-central1-b --command="%~1"
CMDEOF
    echo "  ✅ gcp-ssh.cmd 생성 완료"
    echo "     사용법: cmd.exe //c \"gcp-ssh.cmd\" \"명령어\""
fi

# ─── 4. 완료 ──────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo " ✅ 셋업 완료!"
echo ""
echo " 다음 단계:"
echo "   1. gcloud auth login (미설치시 먼저 설치)"
echo "   2. Claude Code 실행 — 메모리 자동 동기화됨"
echo "   3. git pull로 최신 메모리/코드 동기화"
echo "═══════════════════════════════════════════"
