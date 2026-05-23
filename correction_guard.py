"""사용자 정정/반복 금지/오래된 할일 가드.

수다봇이 오래된 할일이나 사용자가 이미 정정한 주제를 반복하지 않도록
todo와 suppression memory를 함께 관리한다.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import todo_manager

KST = timezone(timedelta(hours=9))
SUPPRESSION_PATH = Path(__file__).resolve().parent / "Chat_bot" / "data" / "suppression_memory.json"

CORRECTION_WORDS = (
    "이미", "끝났", "끝낫", "완료", "했어", "했다", "그만", "다시 말하지", "말하지 마", "몇번", "몇 번",
    "아니야", "없애", "지워", "삭제", "반복", "왜계속", "왜 계속",
)
DOG_KEYWORDS = ("강아지", "강지", "봄이", "보미", "개", "반려견")
VAGUE_WORDS = ("나중", "할 일", "해야 할 일", "처리", "확인")


def _load_suppression() -> list[dict]:
    if not SUPPRESSION_PATH.exists():
        return []
    try:
        return json.loads(SUPPRESSION_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_suppression(items: list[dict]) -> None:
    SUPPRESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUPPRESSION_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(k in text for k in keywords)


def _is_correction(text: str) -> bool:
    normalized = re.sub(r"\s+", "", text.lower())
    return _contains_any(normalized, [w.replace(" ", "") for w in CORRECTION_WORDS])


def _dog_topic(text: str) -> bool:
    return _contains_any(text, DOG_KEYWORDS)


def _todo_matches_topic(todo_text: str, user_text: str, keywords: Iterable[str]) -> bool:
    hay = f"{todo_text} {user_text}"
    return _contains_any(hay, keywords)


def _add_suppression(topic: str, keywords: list[str], rule: str) -> None:
    items = _load_suppression()
    now = datetime.now(KST).isoformat()
    for item in items:
        if item.get("topic") == topic:
            item.update({"keywords": keywords, "rule": rule, "updated_at": now})
            _save_suppression(items)
            return
    items.append({
        "topic": topic,
        "keywords": keywords,
        "rule": rule,
        "created_at": now,
        "updated_at": now,
    })
    _save_suppression(items)


def apply_user_correction(user_text: str) -> str | None:
    """사용자 정정 발화가 들어오면 관련 todo를 완료하고 반복 금지를 저장한다.

    반환값이 있으면 봇은 일반 LLM 응답 대신 그 메시지를 전송한다.
    """
    if not _is_correction(user_text):
        return None

    completed: list[str] = []
    if _dog_topic(user_text):
        for item in todo_manager.get_pending_todos():
            if _todo_matches_topic(item.get("text", ""), user_text, DOG_KEYWORDS):
                done = todo_manager.complete_todo(int(item["id"]))
                if done:
                    completed.append(f"#{done['id']} {done['text']}")
        _add_suppression(
            "봄이/강아지 만나기",
            ["강아지", "강지", "봄이", "보미"],
            "이미 완료된 만남/데려오기 맥락. 사용자가 먼저 묻기 전까지 반복 언급 금지.",
        )

    if completed:
        return "정리했어. 관련 미완료 할일을 완료 처리했고, 앞으로 이 주제는 먼저 꺼내지 않을게."

    if _dog_topic(user_text):
        return "알겠어. 봄이/강아지 만남 얘기는 반복 금지로 저장했어. 관련 할일은 더 남아있지 않아."

    return None


def get_suppression_context() -> str:
    items = _load_suppression()
    if not items:
        return ""
    lines = ["━━━ 반복 금지/사용자 정정 사항 ━━━"]
    for item in items[-10:]:
        lines.append(f"- {item.get('topic')}: {item.get('rule')}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def _is_suppressed_text(text: str) -> bool:
    for item in _load_suppression():
        if _contains_any(text, item.get("keywords", [])):
            return True
    return False


def _is_old_vague_todo(item: dict) -> bool:
    created = item.get("created", "")
    if not created:
        return False
    try:
        dt = datetime.fromisoformat(created)
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    age = datetime.now(KST) - dt.astimezone(KST)
    text = item.get("text", "")
    return age.days >= 14 and _contains_any(text, VAGUE_WORDS)


def get_filtered_todo_context() -> str:
    """브리핑/프롬프트용 할일 컨텍스트. 반복 금지·오래된 애매한 todo는 숨긴다."""
    visible = []
    for item in todo_manager.get_pending_todos():
        text = item.get("text", "")
        if _is_suppressed_text(text):
            continue
        if _is_old_vague_todo(item):
            continue
        visible.append(item)
    if not visible:
        return ""
    return "━━━ 할일 목록 ━━━\n" + todo_manager.format_todo_list(visible) + "\n━━━━━━━━━━━━━━━"
