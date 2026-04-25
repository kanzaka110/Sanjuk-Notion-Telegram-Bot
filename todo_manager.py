"""
할일/체크리스트 관리 모듈
━━━━━━━━━━━━━━━━━━━━━━━━
로컬 JSON 기반 할일 목록. 자연어로 추가/완료/삭제.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TODO_PATH = os.path.join(_BASE_DIR, "data", "todos.json")


def _ensure_dir():
    os.makedirs(os.path.dirname(TODO_PATH), exist_ok=True)


def _load() -> list[dict]:
    if not os.path.exists(TODO_PATH):
        return []
    with open(TODO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(todos: list[dict]):
    _ensure_dir()
    with open(TODO_PATH, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)


def add_todo(text: str, due: str = "") -> dict:
    """할일을 추가한다."""
    todos = _load()
    item = {
        "id": len(todos) + 1,
        "text": text,
        "done": False,
        "due": due,
        "created": datetime.now(KST).isoformat(),
    }
    todos.append(item)
    _save(todos)
    return item


def complete_todo(todo_id: int) -> dict | None:
    """할일을 완료 처리한다."""
    todos = _load()
    for t in todos:
        if t["id"] == todo_id:
            t["done"] = True
            t["completed_at"] = datetime.now(KST).isoformat()
            _save(todos)
            return t
    return None


def delete_todo(todo_id: int) -> bool:
    """할일을 삭제한다."""
    todos = _load()
    new_todos = [t for t in todos if t["id"] != todo_id]
    if len(new_todos) == len(todos):
        return False
    _save(new_todos)
    return True


def get_pending_todos() -> list[dict]:
    """미완료 할일 목록을 반환한다."""
    return [t for t in _load() if not t["done"]]


def get_all_todos() -> list[dict]:
    """전체 할일 목록을 반환한다."""
    return _load()


def get_today_todos() -> list[dict]:
    """오늘 마감인 할일을 반환한다."""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    return [t for t in _load() if not t["done"] and t.get("due", "").startswith(today)]


def format_todo_list(todos: list[dict]) -> str:
    """할일 목록을 텍스트로 포맷한다."""
    if not todos:
        return "할일 없음"
    lines = []
    for t in todos:
        check = "v" if t["done"] else " "
        due = f" (마감: {t['due']})" if t.get("due") else ""
        lines.append(f"[{check}] #{t['id']} {t['text']}{due}")
    return "\n".join(lines)


def get_todo_context() -> str:
    """봇 프롬프트에 삽입할 할일 컨텍스트를 반환한다."""
    pending = get_pending_todos()
    if not pending:
        return ""
    return (
        "━━━ 할일 목록 ━━━\n"
        + format_todo_list(pending)
        + "\n━━━━━━━━━━━━━━━"
    )
