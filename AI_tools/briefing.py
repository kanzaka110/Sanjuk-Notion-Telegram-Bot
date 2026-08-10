"""Repository-owned weekly public AI tools briefing."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import requests

from briefing_model_router import briefing_model_session, route_current

KST = timezone(timedelta(hours=9))


def build_briefing(as_of: str) -> str:
    with briefing_model_session("AI_TOOLS"):
        evidence = route_current(
            "AI_PUBLIC_EVIDENCE",
            f"{as_of} 기준 최근 7일의 AI 개발도구 공식 릴리즈와 문서를 수집하세요. "
            "Claude Code, OpenAI Codex, Gemini CLI, Hermes Agent, Unreal/게임개발 AI 도구를 포함하고 "
            "각 항목에 제목, 공식 URL, 발표일, 핵심 변경을 기록하세요. 공개 정보만 사용하세요.",
        )
        analysis = route_current(
            "AI_PUBLIC_ANALYSIS",
            "다음 공개 근거에서 개발자 반응, 생산성 영향, 과장 가능성, 반대 관점을 분석하세요. "
            "입력에 없는 사실을 만들지 마세요.\n\n" + evidence[:12000],
        )
        return route_current(
            "AI_PUBLIC_EDITORIAL",
            "다음 공식 근거와 공개 분석을 한국어 주간 브리핑으로 편집하세요. URL과 날짜를 유지하고 "
            "승호의 UE5/자동화 업무에 적용할 항목과 보류할 항목을 분리하세요.\n\n"
            f"근거:\n{evidence[:10000]}\n\n분석:\n{analysis[:4000]}",
        )


def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise RuntimeError("telegram_environment_missing")
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=30,
    )
    response.raise_for_status()


def main() -> None:
    as_of = datetime.now(KST).date().isoformat()
    send_telegram(build_briefing(as_of))


if __name__ == "__main__":
    main()
