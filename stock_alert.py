"""
포트폴리오 가격 알림 — 등락률 초과 시 즉시 알림
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_PATH = os.path.join(_BASE_DIR, "data", "stock_watchlist.json")

_alerted_today: set[str] = set()


def _load_watchlist() -> list[dict]:
    if not os.path.exists(WATCHLIST_PATH):
        return []
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_watchlist(items: list[dict]):
    os.makedirs(os.path.dirname(WATCHLIST_PATH), exist_ok=True)
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def add_watch(ticker: str, threshold_pct: float = 3.0) -> dict:
    """종목 감시 추가."""
    items = _load_watchlist()
    item = {"ticker": ticker.upper(), "threshold": threshold_pct}
    items = [i for i in items if i["ticker"] != item["ticker"]]
    items.append(item)
    _save_watchlist(items)
    return item


def remove_watch(ticker: str) -> bool:
    items = _load_watchlist()
    new = [i for i in items if i["ticker"] != ticker.upper()]
    if len(new) == len(items):
        return False
    _save_watchlist(new)
    return True


def get_watchlist() -> list[dict]:
    return _load_watchlist()


def check_prices() -> list[dict]:
    """감시 종목 가격 체크 → 알림 대상 반환."""
    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance 미설치")
        return []

    items = _load_watchlist()
    if not items:
        return []

    alerts = []
    tickers = [i["ticker"] for i in items]

    try:
        data = yf.download(tickers, period="1d", progress=False)
        if data.empty:
            return []

        for item in items:
            ticker = item["ticker"]
            if ticker in _alerted_today:
                continue
            try:
                if len(tickers) == 1:
                    close = data["Close"].iloc[-1]
                    prev = data["Open"].iloc[0]
                else:
                    close = data["Close"][ticker].iloc[-1]
                    prev = data["Open"][ticker].iloc[0]
                change_pct = ((close - prev) / prev) * 100
                if abs(change_pct) >= item["threshold"]:
                    alerts.append({
                        "ticker": ticker,
                        "change": round(change_pct, 2),
                        "price": round(close, 0),
                    })
                    _alerted_today.add(ticker)
            except Exception:
                continue
    except Exception as e:
        log.error("주가 조회 실패: %s", e)

    return alerts


def format_alerts(alerts: list[dict]) -> str:
    if not alerts:
        return ""
    lines = ["[주가 알림]"]
    for a in alerts:
        direction = "상승" if a["change"] > 0 else "하락"
        lines.append(f"- {a['ticker']}: {a['change']:+.1f}% {direction} (현재 {a['price']:,.0f})")
    return "\n".join(lines)
