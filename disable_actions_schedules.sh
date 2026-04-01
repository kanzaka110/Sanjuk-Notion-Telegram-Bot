#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GitHub Actions 스케줄 비활성화
# GCP cron 이전 후 중복 실행 방지
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 사용법: bash disable_actions_schedules.sh
# ※ 로컬 PC에서 실행 (gh CLI 필요)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

export PATH="/c/Program Files/GitHub CLI:$PATH"

echo "🔄 GitHub Actions 스케줄 워크플로우 비활성화 중..."
echo ""

# notion-stock-update
echo "📊 notion-stock-update:"
gh workflow disable briefing.yml --repo kanzaka110/notion-stock-update && echo "  ✅ 투자 브리핑 비활성화" || echo "  ❌ 실패"
gh workflow disable main.yml --repo kanzaka110/notion-stock-update && echo "  ✅ 주가 업데이트 비활성화" || echo "  ❌ 실패"
echo ""

# desktop-tutorial
echo "🎮 desktop-tutorial:"
gh workflow disable ue-animation-briefing.yml --repo kanzaka110/desktop-tutorial && echo "  ✅ UE 브리핑 비활성화" || echo "  ❌ 실패"
gh workflow disable game-news.yml --repo kanzaka110/desktop-tutorial && echo "  ✅ 게임뉴스 비활성화" || echo "  ❌ 실패"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 완료! 수동 실행(workflow_dispatch)은 여전히 가능합니다."
echo "   다시 활성화: gh workflow enable <workflow> --repo <repo>"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
