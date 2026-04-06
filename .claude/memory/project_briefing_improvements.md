---
name: Briefing System Improvements 2026-04-06
description: UE/게임뉴스 브리핑 검색 범위 확장, AI/GitHub 추가, URL 검증 시스템
type: project
---

2026-04-06 브리핑 시스템 대폭 개선.

**UE_bot 브리핑 변경사항:**
- 검색 기간: "오늘만" → "최근 3일" (주말에도 콘텐츠 확보)
- 카테고리 10개 → 13개: +AI Animation Tech, +Physics/Simulation, +GitHub/Open Source
- 태그 추가: AI/ML, GitHub, Neural Animation, Diffusion, NeRF
- 기본 브리핑 수: 1개/일 → 3개/일
- Gemini 검색 쿼리: 2개 → 6개 (YouTube, 80.lv, Reddit, GitHub 포함)
- Gemini max_output_tokens: 2000 → 4000
- AI 전용 쿼리: neural animation, ML Deformer, AI motion synthesis, diffusion model
- GitHub 전용 쿼리: site:github.com unreal engine animation plugin
- 신규 정보 없을 때도 텔레그램 "새로운 업데이트 없음" 전송
- URL 검증: Gemini grounding_metadata에서 검증된 URL 추출 → Claude에 전달
- 모든 프롬프트에 "검증된 URL만 사용, 임의 URL 생성 금지" 규칙 추가

**GameNews_bot 브리핑 변경사항:**
- 시프트업(SHIFT UP) 전용 섹션 최상단 배치 (검색어 8-9번)
- Gemini grounding URL 검증 시스템은 이미 적용되어 있었음

**Why:** 일요일 등 콘텐츠가 적은 날 빈 브리핑 방지, AI/GitHub 트렌드 파악 요청, URL hallucination 문제 해결
**How to apply:** UE_bot 브리핑 수정 시 CATEGORIES, 검색 쿼리, 프롬프트 3곳(build_search_prompt, _build_meta_prompt, _build_body_prompt) 모두 동기화 필요
