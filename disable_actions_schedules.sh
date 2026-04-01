#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GitHub Actions 스케줄 비활성화
# GCP cron 이전 후 중복 실행 방지
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 사용법: bash disable_actions_schedules.sh
# ※ 로컬 PC에서 실행 (gh CLI 필요)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

export PATH="/c/Program Files/GitHub CLI:$PATH"

REPO="kanzaka110/Sanjuk-Notion-Telegram-Bot"

echo "🔄 GitHub Actions 스케줄 워크플로우 비활성화 중..."
echo ""

echo "📦 Sanjuk-Notion-Telegram-Bot:"
gh workflow disable ue-animation-briefing.yml --repo "$REPO" && echo "  ✅ UE 브리핑 비활성화" || echo "  ❌ 실패"
gh workflow disable game-news.yml --repo "$REPO" && echo "  ✅ 게임뉴스 비활성화" || echo "  ❌ 실패"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 완료! 수동 실행(workflow_dispatch)은 여전히 가능합니다."
echo "   다시 활성화: gh workflow enable <workflow> --repo $REPO"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
