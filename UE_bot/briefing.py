#!/usr/bin/env python3
"""
🎮 UE 애니메이션 데일리 브리핑
GitHub Actions / cron 으로 매일 9시 KST에 자동 실행됩니다.

사용법:
  python briefing.py                      # 오늘 3개 카테고리 (날짜 시드)
  python briefing.py --count 5            # 5개 카테고리
  python briefing.py --all                # 전체 10개 카테고리
  python briefing.py --category "Control Rig"  # 특정 카테고리
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import requests
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# ─── 의존성 로드 ────────────────────────────────────────────────────────────

def _load_env() -> None:
    """로컬 개발용 .env 파일 로드 (CI 환경에선 무시)."""
    if os.getenv("CI"):
        return
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print("📄 .env 파일 로드 완료")
    except ImportError:
        pass

_load_env()

# shared_config에서 Claude CLI 유틸리티 로드
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared_config import claude_cli

try:
    from notion_client import Client
    from notion_client.errors import APIResponseError
except ImportError:
    print("❌ notion-client 패키지 필요: pip install notion-client")
    sys.exit(1)

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        print("❌ duckduckgo-search 패키지 필요: pip install ddgs")
        sys.exit(1)

# ─── 설정 ───────────────────────────────────────────────────────────────────

NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "4fd756cb968d4439b9e80bbc69184a57")
NOTION_API_KEY     = os.getenv("NOTION_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

CATEGORIES: list[str] = [
    "Animation Blueprint",
    "Control Rig",
    "Motion Matching",
    "UAF/AnimNext",
    "MetaHuman",
    "Sequencer",
    "Live Link",
    "ML Deformer",
    "GASP",
    "Mover Plugin",
    "AI Animation Tech",
    "Physics/Simulation",
    "GitHub/Open Source",
]

VALID_TAGS: list[str] = [
    "Procedural Animation", "IK", "Retargeting", "Physics",
    "Facial Animation", "Locomotion", "State Machine", "Blend Space",
    "Morph Target", "Root Motion", "Ragdoll", "Cloth Simulation",
    "Motion Capture", "Skeletal Mesh", "Vertex Animation",
    "AI/ML", "GitHub", "Neural Animation", "Diffusion", "NeRF",
]

DIFFICULTY_LEVELS = ["초급", "중급", "고급"]
UE_VERSIONS       = ["5.5", "5.6", "5.7", "5.8+"]

# ─── 중복 체크 ────────────────────────────────────────────────────────────────

def _notion_db_query(database_id: str, payload: dict) -> dict:
    """Notion API databases/query를 requests로 직접 호출 (SDK 호환성 문제 우회)."""
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    res = requests.post(
        f"https://api.notion.com/v1/databases/{database_id}/query",
        headers=headers, json=payload, timeout=30,
    )
    res.raise_for_status()
    return res.json()


def already_briefed_today(notion: Client, category: str) -> bool:
    """오늘 날짜 + 해당 카테고리로 이미 Notion 엔트리가 있는지 확인합니다."""
    today = date.today().isoformat()
    try:
        result = _notion_db_query(NOTION_DATABASE_ID, {
            "filter": {
                "and": [
                    {"property": "날짜", "date": {"equals": today}},
                    {"property": "카테고리", "select": {"equals": category}},
                ]
            },
            "page_size": 1,
        })
        if result.get("results"):
            title = (
                result["results"][0]
                .get("properties", {})
                .get("제목", {})
                .get("title", [{}])[0]
                .get("plain_text", "알 수 없음")
            )
            print(f"  ⏭  이미 오늘 브리핑 존재: [{category}] — {title}")
            return True
        return False
    except Exception as e:
        print(f"  ⚠️  중복 체크 오류 ({category}): {e}")
        return False  # 오류 시 일단 진행


def get_existing_summaries(notion: Client, limit: int = 30) -> list[str]:
    """최근 Notion 페이지들의 요약 텍스트를 가져옵니다 (내용 중복 비교용)."""
    try:
        result = _notion_db_query(NOTION_DATABASE_ID, {
            "sorts": [{"property": "날짜", "direction": "descending"}],
            "page_size": limit,
        })
        summaries = []
        for page in result.get("results", []):
            props = page.get("properties", {})
            # 요약 텍스트
            summary_rt = props.get("요약", {}).get("rich_text", [])
            summary = summary_rt[0].get("plain_text", "") if summary_rt else ""
            # 제목
            title_arr = props.get("제목", {}).get("title", [])
            title = title_arr[0].get("plain_text", "") if title_arr else ""
            if summary:
                summaries.append(f"{title}|{summary}")
        return summaries
    except Exception as e:
        print(f"  ⚠️  기존 요약 조회 오류: {e}")
        return []


def is_content_duplicate(new_summary: str, existing_summaries: list[str], threshold: float = 0.5) -> bool:
    """새 요약이 기존 요약과 내용이 유사한지 단어 겹침으로 판별."""
    if not new_summary or not existing_summaries:
        return False
    new_words = set(new_summary.lower().split())
    if len(new_words) < 3:
        return False
    for existing in existing_summaries:
        existing_words = set(existing.lower().split())
        if len(existing_words) < 3:
            continue
        overlap = new_words & existing_words
        similarity = len(overlap) / min(len(new_words), len(existing_words))
        if similarity >= threshold:
            print(f"  ⏭  내용 중복 감지 (유사도 {similarity:.0%})")
            return True
    return False


def remove_new_badges(notion: Client) -> int:
    """어제 이전 페이지의 🆕 표기를 제거합니다."""
    today = date.today().isoformat()
    removed = 0
    try:
        # 오늘 이전 + 🆕 신규 체크된 페이지 검색
        result = _notion_db_query(NOTION_DATABASE_ID, {
            "filter": {
                "and": [
                    {"property": "날짜", "date": {"before": today}},
                    {"property": "🆕 신규", "checkbox": {"equals": True}},
                ]
            },
            "page_size": 50,
        })
        for page in result.get("results", []):
            page_id = page["id"]
            title_arr = page.get("properties", {}).get("제목", {}).get("title", [])
            old_title = title_arr[0].get("plain_text", "") if title_arr else ""
            new_title = old_title.replace("🆕 ", "").replace("🆕", "").strip()

            update_props = {"🆕 신규": {"checkbox": False}}
            if new_title != old_title:
                update_props["제목"] = {"title": [{"text": {"content": new_title}}]}

            notion.pages.update(page_id=page_id, properties=update_props)
            print(f"  🔄 🆕 해제: {old_title[:60]}")
            removed += 1
    except Exception as e:
        print(f"  ⚠️  🆕 제거 오류: {e}")
    return removed

# ─── 프롬프트 생성 ─────────────────────────────────────────────────────────────

def build_search_prompt(category: str) -> str:
    today     = date.today().strftime("%Y년 %m월 %d일")
    since     = (date.today() - timedelta(days=3)).strftime("%Y년 %m월 %d일")

    tag_list  = ", ".join(VALID_TAGS)
    cat_list  = ", ".join(CATEGORIES)

    return f"""
당신은 언리얼 엔진 애니메이션 전문가이자 교육 콘텐츠 작성자입니다.
오늘({today}) 기준으로 언리얼 엔진의 **{category}** 시스템에 관한 **최근 3일({since}~{today}) 내 새로 올라온 정보**를 웹에서 철저히 검색하세요.

⚠️ 핵심 원칙:
- **최근 3일({since}~{today}) 내 게시/업로드된 콘텐츠만** 수집하세요.
- 그 이전에 올라온 기존 문서, 튜토리얼, 영상은 포함하지 마세요.
- 최근 3일 내 신규 정보가 전혀 없다면, "새_정보_여부": false 로 설정하고 빈 내용으로 응답하세요.

## 검색 대상 (다양한 매체를 반드시 모두 검색)
1. YouTube — UE 공식 채널, Alex Forsythe, Ryan Laley, Matt Aspland, Druid Mechanics, Gabriel Aguiar, PrismaticaDev 등 UE 애니메이션 유튜버
2. 80.lv, GameDev.net, Real-Time VFX, Polycount 등 게임개발 커뮤니티/매체
3. Epic Games 공식 블로그/문서 (dev.epicgames.com, unrealengine.com) — 새 포스트나 업데이트만
4. Epic Developer Community 포럼 — 최근 3일 내 올라온 글만
5. FocalRig (focalrig.com) — Procedural Look & Aim Control Rig 플러그인
6. Twitter/X, Reddit r/unrealengine — 최근 핫 포스트
7. Fab 마켓플레이스 — 신규 애니메이션 관련 플러그인/에셋
8. GDC, Unreal Fest 발표 자료 (새로 공개된 것만)
9. GitHub — 신규/업데이트된 애니메이션 관련 오픈소스 (새 릴리스, 트렌딩 리포)

## 애니메이션 관련 전체 범위 (카테고리 무관하게 폭넓게)
{category}뿐 아니라, 아래 키워드와 관련된 최근 3일 내 콘텐츠도 함께 검색하세요:
- Animation Blueprint, Control Rig, Motion Matching, AnimNext/UAF
- MetaHuman, Facial Animation, Live Link, Motion Capture
- ML Deformer, Physics Simulation, Ragdoll, Chaos Cloth
- GASP, Mover Plugin, Procedural Animation, IK/FK
- Retargeting, Root Motion, Blend Space, State Machine
- Sequencer 애니메이션, Morph Target, Skeletal Mesh
- Niagara 캐릭터 이펙트, Vertex Animation

## AI 기술 및 GitHub (관련 있는 것만)
- AI/ML 기반 애니메이션: Neural Animation, Motion Diffusion, AI Pose Estimation
- AI 게임 개발 도구: Procedural Generation, AI NPC Behavior, AI Animation Retargeting
- GitHub 인기 프로젝트: UE 플러그인, 애니메이션 도구, AI+게임 관련 신규 릴리스/업데이트

## 핵심 요구사항
- **초보자도 따라할 수 있을 정도로 매우 상세하게** 작성
- 모든 UI 경로는 정확히 (예: "Content Browser → 우클릭 → Animation → Animation Blueprint")
- 모든 설정값과 파라미터를 구체적으로 명시
- "왜" 이렇게 하는지 이유를 항상 포함
- 찾은 YouTube 영상 링크를 포함 (최근 3일 내 올라온 것만)
- 찾은 문서/포스트 링크를 포함 (최근 3일 내 올라온 것만)

---

반드시 아래 JSON 형식으로만 응답하세요 (코드 블록 포함):

```json
{{
  "제목": "구체적이고 실용적인 제목 (예: 'UE 5.7 Foot Placement Control Rig — 초보자를 위한 완전 가이드')",
  "요약": "8~12문장 상세 요약. ① 이 기능이 무엇인지 ② 왜 중요한지 ③ 이전 버전 대비 무엇이 바뀌었는지 ④ 어떤 게임/프로젝트에서 활용되는지 ⑤ 학습 난이도와 소요 시간 예상 포함.",
  "소스_링크": "https://오늘_올라온_원본_링크",
  "난이도": "초급 또는 중급 또는 고급",
  "UE_버전": "5.5 또는 5.6 또는 5.7 또는 5.8+",
  "태그": ["태그1", "태그2"],
  "새_정보_여부": true,
  "튜토리얼": {{
    "한줄_요약": "이 글을 한 문장으로 요약 (예: 'Control Rig를 사용해 캐릭터 발이 지형에 자연스럽게 붙는 IK 시스템을 구축하는 방법')",
    "배경_설명": "이 기능이 왜 필요한지, 이것이 없으면 어떤 문제가 생기는지 3~5문장으로 설명. 게임 개발 경험이 없는 사람도 이해할 수 있게.",
    "사전_준비": [
      "필요한 UE 버전과 설치 방법",
      "활성화해야 할 플러그인 이름과 경로 (Edit → Plugins → ...)",
      "필요한 에셋이나 프로젝트 설정",
      "사전에 알아야 할 기초 지식"
    ],
    "핵심_개념": [
      {{"제목": "개념명", "설명": "4~6문장으로 상세히 설명. 비유를 사용해서 이해하기 쉽게. 이 개념이 실제로 어디에 쓰이는지 예시 포함.", "중요도": "필수 또는 권장 또는 참고"}},
      {{"제목": "개념명", "설명": "4~6문장 상세 설명", "중요도": "필수 또는 권장 또는 참고"}},
      {{"제목": "개념명", "설명": "4~6문장 상세 설명", "중요도": "필수 또는 권장 또는 참고"}},
      {{"제목": "개념명", "설명": "4~6문장 상세 설명", "중요도": "필수 또는 권장 또는 참고"}},
      {{"제목": "개념명", "설명": "4~6문장 상세 설명", "중요도": "필수 또는 권장 또는 참고"}}
    ],
    "단계별_가이드": [
      {{
        "단계": 1,
        "제목": "단계 제목",
        "내용": "이 단계에서 해야 할 일을 매우 상세히 설명. 정확한 UI 경로 (예: Content Browser → 우클릭 → Animation → ...), 설정할 값, 선택할 옵션을 구체적으로. 최소 4~6문장.",
        "왜": "이 단계를 왜 해야 하는지 이유 설명",
        "팁": "이 단계의 유용한 팁이나 흔한 실수 방지법"
      }},
      {{
        "단계": 2,
        "제목": "단계 제목",
        "내용": "매우 상세한 내용...",
        "왜": "이유 설명",
        "팁": "팁"
      }}
    ],
    "비교표": [
      {{"항목": "비교 항목", "기존_방식": "기존 방법 (상세 설명)", "새_방식": "개선된 방법 (상세 설명)", "개선_효과": "구체적인 개선 수치나 효과"}}
    ],
    "자주_하는_실수": [
      {{"실수": "초보자가 자주 하는 실수 설명", "해결법": "올바른 방법과 해결 순서"}},
      {{"실수": "두 번째 흔한 실수", "해결법": "해결 방법"}},
      {{"실수": "세 번째 흔한 실수", "해결법": "해결 방법"}}
    ],
    "FAQ": [
      {{"질문": "자주 묻는 질문 1", "답변": "상세한 답변 (3~5문장)"}},
      {{"질문": "자주 묻는 질문 2", "답변": "상세한 답변"}},
      {{"질문": "자주 묻는 질문 3", "답변": "상세한 답변"}}
    ],
    "주의사항": ["⚠️ 주의사항 1 (구체적으로)", "⚠️ 주의사항 2", "⚠️ 주의사항 3"],
    "추천_영상": [
      {{"제목": "영상 제목", "url": "https://youtube.com/...", "채널": "채널명", "길이": "영상 길이", "설명": "이 영상에서 배울 수 있는 것 2~3문장"}},
      {{"제목": "영상 제목", "url": "https://youtube.com/...", "채널": "채널명", "길이": "영상 길이", "설명": "설명"}},
      {{"제목": "영상 제목", "url": "https://youtube.com/...", "채널": "채널명", "길이": "영상 길이", "설명": "설명"}}
    ],
    "관련_문서": [
      {{"제목": "문서 제목", "url": "https://...", "설명": "이 문서의 핵심 내용 요약 2~3문장"}},
      {{"제목": "문서 제목", "url": "https://...", "설명": "설명"}}
    ],
    "다음_학습": "이 내용을 마스터한 후 다음으로 학습하면 좋은 주제 2~3가지와 이유"
  }}
}}
```

태그는 다음 중 1~3개: {tag_list}
카테고리 참고 (현재 대상: **{category}**): {cat_list}

**단계별 가이드는 최소 6단계 이상**, **핵심 개념은 최소 5개**, **관련 영상은 최소 3개** 작성해주세요.
모든 내용은 **한국어**로 작성해주세요.

⚠️ URL 규칙 (가장 중요):
- 추천_영상, 관련_문서의 URL은 반드시 위 검색 결과에서 확인된 실제 URL만 사용
- URL을 임의로 만들거나 추측하지 말 것. 검증된 URL이 없으면 url 필드를 빈 문자열로 설정
""".strip()


# ─── 콘텐츠 수집 (Claude API + Web Search) ───────────────────────────────────

def _web_search(queries: list[str]) -> str:
    """Claude CLI + WebSearch로 웹 검색 후 결과를 텍스트로 반환."""
    search_prompt = f"""다음 검색어들로 웹 검색을 수행하고, 언리얼 엔진 애니메이션 관련 최신 콘텐츠를 찾아주세요:

{chr(10).join(f'- {q}' for q in queries)}

⚠️ 검색 범위를 넓게 잡아주세요:
- YouTube 영상 (UE 애니메이션 유튜버: Alex Forsythe, Ryan Laley, Matt Aspland, Druid Mechanics, PrismaticaDev, Gabriel Aguiar 등)
- 80.lv, GameDev.net, Polycount 등 게임개발 커뮤니티
- Reddit r/unrealengine, Twitter/X
- Epic Games 공식 블로그, Unreal Fest/GDC 발표
- Fab 마켓플레이스 신규 애니메이션 에셋/플러그인
- FocalRig, GitHub 오픈소스 프로젝트

애니메이션 전반을 폭넓게 검색: Control Rig, Motion Matching, AnimNext/UAF, Physics Simulation, Ragdoll, Cloth, Blueprint, IK, Retargeting, Live Link, ML Deformer, GASP, Mover, Procedural Animation, Sequencer, MetaHuman, Skeletal Mesh 등

각 검색 결과에 제목, URL, 핵심 내용을 포함해주세요. 한국어와 영어 결과 모두 포함.
최근 3일 내 올라온 콘텐츠를 우선으로 찾아주세요.
검색 결과에서 확인된 실제 URL만 포함하세요."""

    result = claude_cli(search_prompt, model="opus", web_search=True, timeout=300, effort="max")
    return result or "(검색 결과 없음)"


def fetch_content(category: str, *, target_version: str | None = None) -> dict | None:
    """2단계: ① Claude CLI 웹검색 → ② Claude CLI로 메타데이터 + 본문 생성."""
    ver_label = f" (UE {target_version})" if target_version else ""
    print(f"  🔍 웹 검색 중 ({category}{ver_label})...")
    try:
        # ── STEP 1: Claude CLI + WebSearch ──
        today_str = date.today().strftime("%Y-%m-%d")
        three_days_ago = (date.today() - timedelta(days=3)).strftime("%Y-%m-%d")
        date_range = f"after:{three_days_ago}"

        # 카테고리별 특화 쿼리
        base_queries = [
            f"Unreal Engine {category} tutorial new {date_range}",
            f"언리얼 엔진 {category} 튜토리얼 최신",
            f"site:youtube.com UE5 {category} animation {date_range}",
            f"site:80.lv OR site:reddit.com/r/unrealengine unreal animation {date_range}",
        ]

        ai_queries = [
            f"AI animation game development machine learning {date_range}",
            f"neural animation UE5 ML Deformer AI motion synthesis {date_range}",
            f"AI procedural animation diffusion model NeRF game {date_range}",
        ]

        github_queries = [
            f"site:github.com unreal engine animation plugin {date_range}",
            f"github UE5 animation AI machine learning new release {date_range}",
        ]

        if category == "AI Animation Tech":
            queries = ai_queries + base_queries[:2]
        elif category == "GitHub/Open Source":
            queries = github_queries + base_queries[:2]
        else:
            queries = base_queries + [ai_queries[0], github_queries[0]]
        raw_research = _web_search(queries)
        print(f"  📄 수집 완료 ({len(raw_research)}자)")

        # ── STEP 2: 메타데이터 JSON 추출 ──
        meta_text = claude_cli(
            _build_meta_prompt(category, raw_research),
            model="opus", timeout=120, effort="max",
        )
        meta = _extract_json(meta_text) or {}

        if not meta.get("새_정보_여부", True):
            print(f"  ℹ️ {category}: 최근 3일 내 신규 정보 없음 — 스킵")
            return {}

        print(f"  📋 메타데이터: {meta.get('제목', category)[:50]}...")

        # ── STEP 3: Notion 본문 마크다운 생성 ──
        body_markdown = claude_cli(
            _build_body_prompt(category, raw_research, target_version),
            model="opus", timeout=300, effort="max",
        )
        print(f"  📝 본문 생성 ({len(body_markdown)}자)")

        return {
            "제목": meta.get("제목", f"{category} 브리핑 — {date.today().strftime('%Y.%m.%d')}"),
            "요약": meta.get("요약", "")[:2000],
            "소스_링크": meta.get("소스_링크", "https://dev.epicgames.com/documentation/ko-kr/unreal-engine"),
            "난이도": meta.get("난이도", "중급"),
            "UE_버전": meta.get("UE_버전", "5.7"),
            "태그": meta.get("태그", []),
            "카테고리": category,
            "본문_마크다운": body_markdown,
        }

    except Exception as e:
        print(f"  ❌ 수집 오류 ({category}): {e}")
        return None


def _build_search_only_prompt(category: str, target_version: str | None = None) -> str:
    today = date.today().strftime("%Y년 %m월 %d일")
    since = (date.today() - timedelta(days=3)).strftime("%Y년 %m월 %d일")
    ver_focus = f"\n\n**특히 UE {target_version} 버전에 해당하는 내용만 집중**해서 검색하세요." if target_version else ""
    return f"""오늘({today}) 기준 언리얼 엔진 **{category}** 및 애니메이션 관련 **최근 3일({since}~{today}) 내 새로 올라온 정보만** 검색하세요.{ver_focus}

⚠️ 최근 3일({since}~{today}) 내 게시/업로드된 콘텐츠만 수집. 그 이전 콘텐츠는 제외.
최근 3일 내 신규 정보가 없으면 "최근 새로운 정보 없음"이라고만 응답하세요.

검색 대상 (다양한 매체를 모두 검색):
1. YouTube — UE 공식, Alex Forsythe, Ryan Laley, Matt Aspland, Druid Mechanics, PrismaticaDev 등
2. 80.lv, GameDev.net, Real-Time VFX, Polycount 등 커뮤니티/매체
3. Epic Games 공식 블로그/문서 — 최근 3일 내 새 포스트만
4. FocalRig (focalrig.com) — Procedural Look & Aim 플러그인
5. Twitter/X, Reddit r/unrealengine — 최근 핫 포스트
6. Fab 마켓플레이스 — 신규 애니메이션 플러그인/에셋
7. GitHub — 최근 업데이트/릴리스된 UE 애니메이션 관련 프로젝트

{category} 외에도 폭넓게 수집:
- 애니메이션 전반: Control Rig, Motion Matching, AnimNext, Physics Simulation, IK, Ragdoll, Live Link, ML Deformer, GASP, Mover, Procedural Animation 등
- AI 기술: Neural Animation, Motion Diffusion, AI Retargeting, ML 기반 애니메이션 도구
- GitHub: UE 플러그인, 애니메이션 도구, AI+게임 관련 신규 릴리스

검색 결과를 **한국어**로 정리해주세요:
- 찾은 모든 소스의 URL과 핵심 내용
- YouTube 영상 제목, URL, 채널명
- 최근 3일 내 새로 올라온 내용만 포함
"""


def _build_meta_prompt(category: str, research: str) -> str:
    tag_list = ", ".join(VALID_TAGS)
    today = date.today().strftime("%Y년 %m월 %d일")
    since = (date.today() - timedelta(days=3)).strftime("%Y년 %m월 %d일")
    return f"""아래 조사 내용을 바탕으로 메타데이터만 JSON으로 추출하세요.

⚠️ 중요: 최근 3일({since}~{today}) 내 게시된 콘텐츠가 있는지 판단하세요.
최근 3일 내 신규 콘텐츠가 없다면 "새_정보_여부": false 로 설정하세요.

조사 내용:
{research[:3000]}

⚠️ URL 규칙 (가장 중요):
- "Google Search 검증된 URL 목록"이 있으면, 반드시 그 목록의 URL만 사용할 것
- 검증된 URL 목록에 없는 URL은 절대 사용하지 말 것
- URL을 임의로 만들거나 추측하지 말 것

반드시 아래 JSON만 출력하세요 (다른 텍스트 없이):
```json
{{
  "제목": "구체적이고 실용적인 한국어 제목",
  "요약": "8~12문장 상세 요약 (한국어)",
  "소스_링크": "검증된 URL 목록에서 가장 관련 있는 URL",
  "난이도": "초급 또는 중급 또는 고급",
  "UE_버전": "5.5 또는 5.6 또는 5.7 또는 5.8+",
  "태그": ["태그1", "태그2"],
  "새_정보_여부": true 또는 false
}}
```
태그는 다음 중 1~3개만: {tag_list}
"""


def _build_body_prompt(category: str, research: str, target_version: str | None = None) -> str:
    ver_note = f"\n\n⚠️ **이 페이지는 UE {target_version} 버전 전용입니다.** 이 버전에서의 기능, 변경사항, 제한사항만 다루세요. 다른 버전과의 차이점을 명확히 표기하세요." if target_version else ""
    return f"""당신은 언리얼 엔진 애니메이션 전문 교육자입니다.
아래 조사 내용을 바탕으로, **이전에 잘 작성된 Notion 페이지와 동일한 형식**의 마크다운 본문을 작성하세요.{ver_note}

⚠️ URL 규칙 (가장 중요):
- 조사 내용에 "Google Search 검증된 URL 목록"이 있으면, 반드시 그 목록의 URL만 사용할 것
- 추천 영상, 관련 문서 등에 URL을 넣을 때 검증된 URL만 사용
- URL을 임의로 만들거나 추측하지 말 것. 검증된 URL이 없으면 URL 필드를 비워둘 것

## 조사 내용
{research[:6000]}

## 반드시 따라야 할 형식 (아래 구조를 정확히 따르세요)

# 📖 소스 내용 상세 정리

## {category}란?
(이 기능/시스템이 무엇인지 4~6문장. 핵심 가치를 인용구로 강조)

> 💡 **핵심 가치**: "한 문장 핵심"

---

## {category}의 주요 활용 분야
(표 형식으로 분야 | 설명 | 예시)

---

## {category} 핵심 구조
### 주요 구성 요소
(표 형식: 요소 | 역할 | 비고)

### 작동 원리
(코드블록이나 플로우로 설명)

---

## UE 5.x 주요 업데이트 상세
### 🔷 첫 번째 주요 기능 (설명)
(상세 설명 4~6문장, 불릿 포인트)

### 🔷 두 번째 주요 기능
(상세 설명)

### 🔷 세 번째 주요 기능
(상세 설명)

---

## 기법/방식 비교표
(표: 기법 | 특징 | 최적 용도 | 성능)

---

# 🎬 튜토리얼 영상 목록

## 📺 공식 & 무료
(표: 제목 | 출처 | 링크 | 시간)

## 📺 유튜브 플레이리스트
(표: 채널 | 시리즈명 | 링크 | 수준)

## 📺 특정 주제
(표: 제목 | 출처 | 링크)

---

# 🛠️ 단계별 튜토리얼 — (주제에 맞는 실습 제목)

## 준비물
(불릿 리스트)

---

## STEP 1. (제목)
(번호 리스트로 상세 순서, 정확한 UI 경로 포함)
> 💡 **Tip**: (유용한 팁)

---

## STEP 2. (제목)
(상세 순서)

(... STEP 6~8까지 계속)

---

# 🔗 연관 자료 모음

## 공식 문서
(링크 리스트)

## 유료 코스
(링크 리스트)

## 연관 시스템
(다른 UE 시스템과의 관계 설명)

---

## 중요 규칙:
1. 모든 표는 마크다운 테이블(|---|---|---| 형식) 사용
2. 코드는 ```로 감싸기
3. 구분선(---) 으로 섹션 분리
4. > 로 인용구/팁 표시
5. **굵게**, *기울임* 적극 사용
6. 링크는 [텍스트](URL) 형식
7. 영상 목록은 최소 8개 이상 포함
8. 단계별 가이드는 최소 6단계 이상
9. 모든 내용은 **한국어**로 작성
10. 초보자도 따라할 수 있을 정도로 상세하게
11. **최근 1주 이내 새로운 정보**가 있다면 해당 섹션 제목에 🆕 이모지를 붙여주세요 (예: "### 🆕 🔷 UE 5.7에서 추가된 신기능")
12. 이전부터 있던 기존 정보에는 🆕를 붙이지 마세요. 진짜 새로운 내용에만 표기합니다.
"""


def _extract_json(text: str) -> dict | None:
    """텍스트에서 JSON 블록 추출."""
    # ```json ... ``` 형식
    m = re.search(r"```json\s*([\s\S]+?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # { ... } 형식 (가장 긴 매칭)
    for m in re.finditer(r"\{[\s\S]*\}", text):
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
    return None


def _make_fallback(category: str, text: str) -> dict:
    return {
        "제목": f"{category} 브리핑 — {date.today().strftime('%Y.%m.%d')}",
        "요약": text[:600].strip(),
        "소스_링크": "https://dev.epicgames.com/documentation/ko-kr/unreal-engine",
        "난이도": "중급",
        "UE_버전": "5.7",
        "태그": [],
        "새_정보_여부": False,
        "튜토리얼": {
            "한줄_요약": f"{category} 관련 최신 정보 브리핑",
            "배경_설명": text[:1000].strip(),
            "사전_준비": [],
            "핵심_개념": [],
            "단계별_가이드": [],
            "비교표": [],
            "자주_하는_실수": [],
            "FAQ": [],
            "주의사항": [],
            "추천_영상": [],
            "관련_문서": [],
            "다음_학습": "",
        },
    }


# ─── Notion 페이지 콘텐츠 빌더 ────────────────────────────────────────────────

def build_page_content(data: dict) -> list[dict]:
    """구조화된 data dict → Notion API 블록 리스트 직접 생성 (시각적 강화)."""
    tut = data.get("튜토리얼", {})
    blocks: list[dict] = []

    def _divider():
        blocks.append({"object": "block", "type": "divider", "divider": {}})

    def _heading1(text):
        blocks.append({"object": "block", "type": "heading_1",
            "heading_1": {"rich_text": [{"type": "text", "text": {"content": text}}], "color": "blue_background"}})

    def _heading2(text):
        blocks.append({"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}})

    def _heading3(text):
        blocks.append({"object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": text}}]}})

    def _paragraph(text, bold=False, color="default"):
        if not text.strip():
            return
        rt = [{"type": "text", "text": {"content": text[:2000]}, "annotations": {"bold": bold, "color": color}}]
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": rt, "color": "default"}})

    def _callout(text, emoji="💡", color="blue_background"):
        blocks.append({"object": "block", "type": "callout",
            "callout": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}],
                        "icon": {"type": "emoji", "emoji": emoji}, "color": color}})

    def _bullet(text):
        blocks.append({"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}})

    def _numbered(text):
        blocks.append({"object": "block", "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}})

    def _quote(text):
        blocks.append({"object": "block", "type": "quote",
            "quote": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}], "color": "gray_background"}})

    def _bookmark(url, caption=""):
        b = {"object": "block", "type": "bookmark", "bookmark": {"url": url}}
        if caption:
            b["bookmark"]["caption"] = [{"type": "text", "text": {"content": caption[:2000]}}]
        blocks.append(b)

    def _toggle(title, children_texts):
        children = []
        for ct in children_texts:
            children.append({"object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": ct[:2000]}}]}})
        blocks.append({"object": "block", "type": "toggle",
            "toggle": {"rich_text": [{"type": "text", "text": {"content": title[:2000]}}],
                       "children": children[:10]}})

    # ═══════════════════════════════════════════════════════
    # 한줄 요약 (상단 콜아웃)
    # ═══════════════════════════════════════════════════════
    one_liner = tut.get("한줄_요약", "")
    if one_liner:
        _callout(f"📌  {one_liner}", "🎯", "yellow_background")

    _divider()

    # ═══════════════════════════════════════════════════════
    # 배경 설명
    # ═══════════════════════════════════════════════════════
    bg = tut.get("배경_설명", "") or tut.get("개요", "")
    if bg:
        _heading1("📖 배경 및 개요")
        _paragraph(bg)

    _divider()

    # ═══════════════════════════════════════════════════════
    # 사전 준비
    # ═══════════════════════════════════════════════════════
    prereqs = tut.get("사전_준비", [])
    if prereqs:
        _heading1("🔧 사전 준비")
        _callout("아래 항목을 먼저 확인해주세요. 하나라도 빠지면 튜토리얼 진행이 어려울 수 있습니다.", "⚡", "red_background")
        for p in prereqs:
            _numbered(p)

    _divider()

    # ═══════════════════════════════════════════════════════
    # 핵심 개념
    # ═══════════════════════════════════════════════════════
    concepts = tut.get("핵심_개념", [])
    if concepts:
        _heading1("🔑 핵심 개념")
        _paragraph("이 섹션의 개념들을 이해하면 튜토리얼을 훨씬 수월하게 따라갈 수 있습니다.")
        for c in concepts:
            importance = c.get("중요도", "권장")
            emoji = "🔴" if importance == "필수" else ("🟡" if importance == "권장" else "🔵")
            _heading3(f"{emoji} {c.get('제목', '')}  [{importance}]")
            _paragraph(c.get("설명", ""))

    _divider()

    # ═══════════════════════════════════════════════════════
    # 비교표
    # ═══════════════════════════════════════════════════════
    comparisons = tut.get("비교표", [])
    if comparisons and any(c.get("항목") for c in comparisons):
        _heading1("⚖️ 기존 방식 vs 새 방식 비교")
        for c in comparisons:
            item   = c.get("항목", "")
            old    = c.get("기존_방식", "")
            new    = c.get("새_방식", "")
            effect = c.get("개선_효과", "")
            if item:
                _heading3(f"📊 {item}")
                _callout(f"❌ 기존: {old}", "❌", "gray_background")
                _callout(f"✅ 개선: {new}", "✅", "green_background")
                if effect:
                    _paragraph(f"→ 개선 효과: {effect}", bold=True)

    _divider()

    # ═══════════════════════════════════════════════════════
    # 단계별 가이드
    # ═══════════════════════════════════════════════════════
    steps = tut.get("단계별_가이드", [])
    if steps:
        _heading1("🛠️ 단계별 튜토리얼 가이드")
        _callout(f"총 {len(steps)}단계로 구성되어 있습니다. 순서대로 따라해주세요.", "📋", "blue_background")
        for s in steps:
            n     = s.get("단계", "?")
            title = s.get("제목", "")
            body  = s.get("내용", "")
            why   = s.get("왜", "")
            tip   = s.get("팁", "")

            _heading2(f"Step {n}.  {title}")
            _paragraph(body)
            if why:
                _callout(f"왜 이 단계가 필요한가요? → {why}", "🤔", "purple_background")
            if tip:
                _callout(f"💡 Tip: {tip}", "💡", "yellow_background")

    _divider()

    # ═══════════════════════════════════════════════════════
    # 자주 하는 실수
    # ═══════════════════════════════════════════════════════
    mistakes = tut.get("자주_하는_실수", [])
    if mistakes:
        _heading1("🚫 초보자가 자주 하는 실수")
        for m in mistakes:
            _callout(f"❌ 실수: {m.get('실수', '')}", "❌", "red_background")
            _callout(f"✅ 해결: {m.get('해결법', '')}", "✅", "green_background")

    _divider()

    # ═══════════════════════════════════════════════════════
    # FAQ
    # ═══════════════════════════════════════════════════════
    faqs = tut.get("FAQ", [])
    if faqs:
        _heading1("❓ 자주 묻는 질문 (FAQ)")
        for faq in faqs:
            q = faq.get("질문", "")
            a = faq.get("답변", "")
            if q and a:
                _toggle(f"Q. {q}", [f"A. {a}"])

    _divider()

    # ═══════════════════════════════════════════════════════
    # 주의사항
    # ═══════════════════════════════════════════════════════
    cautions = tut.get("주의사항", [])
    if cautions:
        _heading1("⚠️ 주의사항")
        for c in cautions:
            _callout(c, "⚠️", "orange_background")

    _divider()

    # ═══════════════════════════════════════════════════════
    # 추천 영상
    # ═══════════════════════════════════════════════════════
    videos = tut.get("추천_영상", [])
    if videos:
        _heading1("🎬 추천 튜토리얼 영상")
        for v in videos:
            title   = v.get("제목", "영상")
            url     = v.get("url", "")
            channel = v.get("채널", "")
            length  = v.get("길이", "")
            desc    = v.get("설명", "")
            info = f"📺 {channel}" + (f"  |  ⏱️ {length}" if length else "")
            _heading3(title)
            _paragraph(info)
            if desc:
                _paragraph(desc)
            if url:
                _bookmark(url, f"{title} — {channel}")

    _divider()

    # ═══════════════════════════════════════════════════════
    # 관련 문서
    # ═══════════════════════════════════════════════════════
    docs = tut.get("관련_문서", []) or tut.get("관련_링크", [])
    if docs:
        _heading1("🔗 관련 공식 문서 및 자료")
        for d in docs:
            title = d.get("제목", "문서")
            url   = d.get("url", "")
            desc  = d.get("설명", "")
            if url:
                _bookmark(url, f"{title}: {desc}" if desc else title)

    _divider()

    # ═══════════════════════════════════════════════════════
    # 다음 학습
    # ═══════════════════════════════════════════════════════
    next_learn = tut.get("다음_학습", "")
    if next_learn:
        _heading1("🚀 다음 학습 로드맵")
        _callout(next_learn, "🗺️", "blue_background")

    return blocks[:100]


# ─── Notion 업로드 ─────────────────────────────────────────────────────────────

def upload_to_notion(notion: Client, data: dict) -> bool:
    """Notion 데이터베이스에 브리핑 페이지를 생성합니다."""

    # 값 검증
    difficulty = data.get("난이도", "중급")
    if difficulty not in DIFFICULTY_LEVELS:
        difficulty = "중급"

    ue_version = data.get("UE_버전", "5.7")
    if ue_version not in UE_VERSIONS:
        ue_version = "5.7"

    tags = [t for t in data.get("태그", []) if t in VALID_TAGS]

    category = data.get("카테고리", "Animation Blueprint")
    if category not in CATEGORIES:
        category = "Animation Blueprint"

    title        = str(data.get("제목", f"{category} 브리핑"))[:2000]
    summary      = str(data.get("요약", ""))[:2000]
    source_link  = data.get("소스_링크") or "https://dev.epicgames.com/documentation/ko-kr/unreal-engine"
    body_md      = data.get("본문_마크다운", "")
    page_blocks  = _markdown_to_notion_blocks(body_md) if body_md else build_page_content(data)

    properties: dict = {
        "제목":       {"title":     [{"text": {"content": title}}]},
        "날짜":       {"date":      {"start": date.today().isoformat()}},
        "카테고리":   {"select":    {"name": category}},
        "UE 버전":    {"select":    {"name": ue_version}},
        "난이도":     {"select":    {"name": difficulty}},
        "요약":       {"rich_text": [{"text": {"content": summary}}]},
        "소스 링크":  {"url":       source_link},
        "브리핑 완료": {"checkbox":  True},
        "🆕 신규":    {"checkbox":  True},
    }
    if tags:
        properties["태그"] = {"multi_select": [{"name": t} for t in tags]}

    try:
        page = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=properties,
            children=page_blocks,
        )
        print(f"  ✅ Notion 페이지 생성: {title}")
        print(f"     🔗 {page['url']}")
        return True
    except APIResponseError as e:
        print(f"  ❌ Notion API 오류: {e.status} — {e.body}")
        return False
    except Exception as e:
        print(f"  ❌ Notion 업로드 실패: {e}")
        return False


def _markdown_to_notion_blocks(markdown: str) -> list[dict]:
    """마크다운을 Notion API 블록으로 변환. 테이블, 코드블록, 콜아웃 지원."""
    blocks: list[dict] = []
    lines = markdown.split("\n")
    i = 0

    def _rt(text):
        """rich_text 배열 생성 (2000자 제한)."""
        return [{"type": "text", "text": {"content": text[:2000]}}]

    while i < len(lines):
        line = lines[i]

        # ── 코드블록 ──
        if line.strip().startswith("```"):
            lang = line.strip()[3:].strip().lower()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            # Notion 지원 언어 검증
            NOTION_LANGUAGES = {
                "abap","abc","agda","arduino","ascii art","assembly","bash","basic","bnf",
                "c","c#","c++","clojure","coffeescript","coq","css","dart","dhall","diff",
                "docker","ebnf","elixir","elm","erlang","f#","flow","fortran","gherkin",
                "glsl","go","graphql","groovy","haskell","hcl","html","idris","java",
                "javascript","json","julia","kotlin","latex","less","lisp","livescript",
                "llvm ir","lua","makefile","markdown","markup","matlab","mathematica",
                "mermaid","nix","notion formula","objective-c","ocaml","pascal","perl",
                "php","plain text","powershell","prolog","protobuf","purescript","python",
                "r","racket","reason","ruby","rust","sass","scala","scheme","scss","shell",
                "smalltalk","solidity","sql","swift","toml","typescript","vb.net","verilog",
                "vhdl","visual basic","webassembly","xml","yaml","java/c/c++/c#",
            }
            if lang not in NOTION_LANGUAGES:
                lang = "plain text"
            blocks.append({
                "object": "block", "type": "code",
                "code": {
                    "rich_text": _rt("\n".join(code_lines)),
                    "language": lang if lang else "plain text",
                },
            })
            i += 1
            continue

        # ── 테이블 (마크다운 |---|---| 형식) ──
        if line.strip().startswith("|") and i + 1 < len(lines) and "---" in lines[i + 1]:
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                if "---" not in lines[i]:  # 구분선 행 제외
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    table_lines.append(cells)
                i += 1
            if table_lines:
                col_count = max(len(row) for row in table_lines)
                table = {
                    "object": "block", "type": "table",
                    "table": {
                        "table_width": col_count,
                        "has_column_header": True,
                        "has_row_header": False,
                        "children": [],
                    },
                }
                for row in table_lines[:50]:
                    # 열 수 맞추기
                    while len(row) < col_count:
                        row.append("")
                    table["table"]["children"].append({
                        "object": "block", "type": "table_row",
                        "table_row": {
                            "cells": [[{"type": "text", "text": {"content": cell[:2000]}}] for cell in row[:col_count]],
                        },
                    })
                blocks.append(table)
            continue

        # ── 단순 테이블 행 (구분선 없이 | 로 시작) ──
        if line.strip().startswith("|") and "---" not in line:
            # 단독 테이블 행 → paragraph로 처리
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rt(line)}})
            i += 1
            continue

        # ── 구분선 ──
        if line.strip() == "---":
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            i += 1
            continue

        # ── 헤딩 ──
        if line.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1",
                "heading_1": {"rich_text": _rt(line[2:]), "color": "blue_background"}})
            i += 1
            continue
        if line.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2",
                "heading_2": {"rich_text": _rt(line[3:])}})
            i += 1
            continue
        if line.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3",
                "heading_3": {"rich_text": _rt(line[4:])}})
            i += 1
            continue

        # ── 인용구 / 콜아웃 ──
        if line.startswith("> "):
            text = line[2:]
            emoji = "💡"
            color = "blue_background"
            if "Tip" in text or "팁" in text:
                emoji, color = "💡", "yellow_background"
            elif "핵심" in text:
                emoji, color = "🎯", "yellow_background"
            elif "⚠" in text or "주의" in text:
                emoji, color = "⚠️", "orange_background"
            blocks.append({"object": "block", "type": "callout",
                "callout": {"rich_text": _rt(text), "icon": {"type": "emoji", "emoji": emoji}, "color": color}})
            i += 1
            continue

        # ── 불릿 리스트 ──
        if line.startswith("- "):
            blocks.append({"object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": _rt(line[2:])}})
            i += 1
            continue

        # ── 번호 리스트 ──
        if re.match(r"^\d+\.\s", line):
            text = re.sub(r"^\d+\.\s", "", line)
            blocks.append({"object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": _rt(text)}})
            i += 1
            continue

        # ── 일반 텍스트 ──
        if line.strip():
            blocks.append({"object": "block", "type": "paragraph",
                "paragraph": {"rich_text": _rt(line)}})

        i += 1

    return blocks[:100]


# ─── 메인 로직 ────────────────────────────────────────────────────────────────

def run_briefing(categories: list[str], *, force: bool = False, per_version: bool = False) -> None:
    """지정된 카테고리 목록에 대해 브리핑을 실행합니다."""
    if not NOTION_API_KEY:
        print("❌ NOTION_API_KEY 환경변수가 없습니다.")
        sys.exit(1)

    notion_client = Client(auth=NOTION_API_KEY)

    # 버전별 분리 모드: 각 카테고리 × 각 버전
    if per_version:
        tasks = []
        for cat in categories:
            for ver in UE_VERSIONS:
                tasks.append((cat, ver))
    else:
        tasks = [(cat, None) for cat in categories]

    print(f"\n{'='*60}")
    print(f"🎮 UE 애니메이션 데일리 브리핑")
    print(f"📅 {date.today().strftime('%Y년 %m월 %d일')}")
    print(f"📂 대상: {len(tasks)}건 ({'버전별 분리' if per_version else '통합'})")
    if force:
        print(f"⚡ FORCE 모드 — 중복 체크 무시")
    print(f"{'='*60}\n")

    # ── 어제 이전 페이지의 🆕 표기 제거 ──
    print("🔄 이전 브리핑의 🆕 표기 정리 중...")
    removed = remove_new_badges(notion_client)
    print(f"  → {removed}개 페이지에서 🆕 제거 완료\n")

    # ── 기존 요약 로드 (내용 중복 비교용) ──
    print("📚 기존 브리핑 요약 로드 중...")
    existing_summaries = get_existing_summaries(notion_client)
    print(f"  → {len(existing_summaries)}개 기존 요약 로드 완료\n")

    success, skipped, failed = 0, 0, 0
    telegram_results: list[dict] = []

    for idx, (category, version) in enumerate(tasks):
        label = f"{category} (UE {version})" if version else category
        print(f"\n[{idx+1}/{len(tasks)}] {label}")

        # 중복 체크 (force 모드면 스킵)
        if not force and already_briefed_today(notion_client, category):
            skipped += 1
            continue

        # Rate limit 방지: 첫 번째 이후 30초 대기
        if idx > 0:
            wait = 30
            print(f"  ⏳ Rate limit 방지 — {wait}초 대기...")
            time.sleep(wait)

        # 콘텐츠 수집 (최대 1회 재시도)
        data = None
        for attempt in range(2):
            data = fetch_content(category, target_version=version)
            if data is not None:
                break
            if attempt < 1:
                retry_wait = 30
                print(f"  🔄 재시도 {attempt+2}/2 — {retry_wait}초 후...")
                time.sleep(retry_wait)

        if data is None:
            # 실제 에러 (API 오류, 예외 등)
            failed += 1
            continue
        if not data:
            # 신규 정보 없음 — 정상 스킵 (빈 dict)
            skipped += 1
            continue

        # 버전별 모드면 제목에 버전 표기 + UE 버전 강제 설정
        if version:
            data["UE_버전"] = version
            if f"UE {version}" not in data.get("제목", ""):
                data["제목"] = f"[UE {version}] {data.get('제목', category)}"

        # 🆕 표기 추가 (오늘 새로 생성된 페이지)
        data["제목"] = f"🆕 {data.get('제목', category)}"

        # 내용 중복 체크 (force 모드면 스킵)
        if not force and is_content_duplicate(data.get("요약", ""), existing_summaries):
            print(f"  ⏭  기존 브리핑과 내용 중복 — 건너뜀")
            skipped += 1
            continue

        # Notion 업로드
        if upload_to_notion(notion_client, data):
            success += 1
            telegram_results.append({
                "category": category,
                "title": data.get("제목", "").replace("🆕 ", ""),
                "difficulty": data.get("난이도", ""),
                "version": data.get("UE_버전", ""),
                "summary": data.get("요약", ""),
                "url": data.get("소스_링크", ""),
            })
        else:
            failed += 1

    # 최종 리포트
    print(f"\n{'='*60}")
    print(f"📊 결과: ✅ {success}개 생성 | ⏭ {skipped}개 스킵 | ❌ {failed}개 실패")
    print(f"📌 Notion: https://www.notion.so/{NOTION_DATABASE_ID.replace('-', '')}")
    print(f"{'='*60}\n")

    # 텔레그램 알림 (결과 없어도 전송)
    send_telegram(telegram_results)

    if failed > 0 and success == 0 and skipped == 0:
        sys.exit(1)


# ═══════════════════════════════════════════════════════
# 텔레그램 알림
# ═══════════════════════════════════════════════════════
def send_telegram(results: list[dict]) -> None:
    """브리핑 결과를 텔레그램으로 전송."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    today = date.today().strftime("%Y.%m.%d")
    msg = f"🎮 언리얼 튜토리얼 가이드 비서\n{today} 업데이트\n\n"

    for r in results:
        cat = r.get("category", "")
        title = r.get("title", "")
        difficulty = r.get("difficulty", "")
        version = r.get("version", "")
        summary = r.get("summary", "")[:120]
        url = r.get("url", "")

        msg += f"📂 {cat}"
        if version:
            msg += f" | UE {version}"
        if difficulty:
            msg += f" | {difficulty}"
        msg += f"\n▸ {title}\n"
        if summary:
            msg += f"  {summary}\n"
        if url:
            msg += f"  🔗 {url}\n"
        msg += "\n"

    if not results:
        msg += "오늘 새로운 업데이트가 없습니다.\n"

    msg += f"📋 Notion: https://notion.so/{NOTION_DATABASE_ID.replace('-', '')}"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "disable_web_page_preview": True,
    }
    try:
        res = requests.post(url, json=payload, timeout=30)
        if res.status_code == 200:
            print("  ✅ 텔레그램 전송 완료")
        else:
            print(f"  ⚠️ 텔레그램 전송 실패: {res.status_code}")
    except Exception as e:
        print(f"  ⚠️ 텔레그램 전송 오류: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="UE 애니메이션 데일리 브리핑")
    group  = parser.add_mutually_exclusive_group()
    group.add_argument("--all",      action="store_true", help="모든 카테고리")
    group.add_argument("--category", type=str,            help="특정 카테고리")
    group.add_argument("--count",    type=int, default=3, help="오늘 브리핑 수 (기본 3)")
    parser.add_argument("--force",       action="store_true", help="중복 체크 무시 (재생성)")
    parser.add_argument("--per-version", action="store_true", help="UE 버전별 개별 페이지 생성")
    args = parser.parse_args()

    if args.all:
        targets = CATEGORIES
    elif args.category:
        if args.category not in CATEGORIES:
            print(f"❌ 알 수 없는 카테고리: {args.category}")
            print(f"   사용 가능: {', '.join(CATEGORIES)}")
            sys.exit(1)
        targets = [args.category]
    else:
        random.seed(date.today().toordinal())
        targets = random.sample(CATEGORIES, min(args.count, len(CATEGORIES)))

    run_briefing(targets, force=args.force, per_version=args.per_version)


if __name__ == "__main__":
    main()
