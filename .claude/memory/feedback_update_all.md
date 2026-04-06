---
name: Update All Three Places
description: "최신업데이트" 요청 시 메모리+GitHub+GCP 세 곳 모두 동기화
type: feedback
---

"최신업데이트"라고 하면 세 곳 모두 최신화할 것:
1. 메모리 (MEMORY.md + 관련 .md 파일)
2. GitHub (CLAUDE.md 등 커밋 + push)
3. GCP (git pull로 반영)

**Why:** 매번 세 곳을 따로 요청하는 것이 번거로움. 한 마디로 전부 처리되길 원함.
**How to apply:** 코드/설정 변경 후 사용자가 "최신업데이트" 또는 유사 표현 사용 시, 묻지 않고 세 곳 모두 순서대로 업데이트.
