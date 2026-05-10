"""
지출 기록 모듈 — 로컬 JSON + 월간 요약
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"커피 5500원" 같은 자연어 입력을 파싱하여 기록.
Google Sheets 연동은 추후 확장 가능.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPENSE_PATH = os.path.join(_BASE_DIR, "data", "expenses.json")


def _ensure_dir():
    os.makedirs(os.path.dirname(EXPENSE_PATH), exist_ok=True)


def _load() -> list[dict]:
    if not os.path.exists(EXPENSE_PATH):
        return []
    with open(EXPENSE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(expenses: list[dict]):
    _ensure_dir()
    with open(EXPENSE_PATH, "w", encoding="utf-8") as f:
        json.dump(expenses, f, ensure_ascii=False, indent=2)


def add_expense(description: str, amount: int, category: str = "") -> dict:
    """지출을 기록한다."""
    expenses = _load()
    item = {
        "id": len(expenses) + 1,
        "description": description,
        "amount": amount,
        "category": category,
        "date": datetime.now(KST).strftime("%Y-%m-%d"),
        "time": datetime.now(KST).strftime("%H:%M"),
    }
    expenses.append(item)
    _save(expenses)
    return item


def parse_expense(text: str) -> dict | None:
    """자연어에서 지출 정보를 파싱한다.

    "커피 5500원", "점심 12000", "택시 23000원" 등
    """
    pattern = r"(.+?)\s*(\d[\d,]*)\s*원?"
    match = re.search(pattern, text.strip())
    if not match:
        return None
    desc = match.group(1).strip()
    amount = int(match.group(2).replace(",", ""))
    return {"description": desc, "amount": amount}


def get_today_expenses() -> list[dict]:
    """오늘 지출 목록."""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    return [e for e in _load() if e["date"] == today]


def get_month_expenses() -> list[dict]:
    """이번 달 지출 목록."""
    month = datetime.now(KST).strftime("%Y-%m")
    return [e for e in _load() if e["date"].startswith(month)]


def get_expense_summary(expenses: list[dict]) -> str:
    """지출 목록을 요약 텍스트로 반환한다."""
    if not expenses:
        return "기록된 지출 없음"
    total = sum(e["amount"] for e in expenses)
    lines = [f"- {e['description']}: {e['amount']:,}원" for e in expenses]
    lines.append(f"\n합계: {total:,}원")
    return "\n".join(lines)


def get_expense_context() -> str:
    """봇 프롬프트에 삽입할 지출 컨텍스트."""
    today = get_today_expenses()
    if not today:
        return ""
    return (
        "━━━ 오늘 지출 ━━━\n"
        + get_expense_summary(today)
        + "\n━━━━━━━━━━━━━━━"
    )
