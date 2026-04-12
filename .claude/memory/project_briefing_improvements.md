---
name: Briefing System Improvements 2026-04-06
description: 게임뉴스 브리핑 개선사항 — 시프트업 전용 섹션, URL 검증 (UE 브리핑은 Sanjuk-Unreal로 이전)
type: project
originSessionId: 5b51174a-9d89-468b-969a-23fab840d5b3
---
2026-04-06 브리핑 시스템 개선. 2026-04-12 UE_bot이 Sanjuk-Unreal 리포로 분리됨.

**GameNews_bot 브리핑 (현재 이 리포에서 관리):**
- 시프트업(SHIFT UP) 전용 섹션 최상단 배치 (검색어 8-9번)
- URL 검증: Claude CLI WebSearch로 검증된 URL만 사용
- 당일 게시된 기사만 수집 (어제 이전 기사 제외)

**UE_bot 브리핑 (Sanjuk-Unreal 리포로 이전됨 — 아카이브):**
- 검색 기간: 최근 3일, 카테고리 13개, AI/GitHub 포함
- 기본 3개/일 브리핑

**Why:** URL hallucination 방지, 시프트업 관심 반영
**How to apply:** GameNews_bot 브리핑 수정만 이 리포에서 작업. UE 브리핑은 Sanjuk-Unreal에서.
