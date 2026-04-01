"""
기존 Notion 브리핑 페이지의 '브리핑구분'을 날짜/시간 기반으로 올바르게 수정하는 스크립트.

사용법:
  # 환경변수 설정 후 실행
  NOTION_API_KEY=... NOTION_DB_ID=... python scripts/fix_briefing_labels.py

  # 또는 --dry-run으로 변경 내용만 미리 확인
  python scripts/fix_briefing_labels.py --dry-run
"""

import os
import sys
import requests
from datetime import datetime, timezone, timedelta

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID", "")
KST = timezone(timedelta(hours=9))

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# KST 시간대 기준으로 브리핑 구분 판별
# cron 스케줄 (KST 기준):
#   KR_BEFORE: 08:30 KST → UTC 23:30 → KST hour ~8
#   KR_AFTER:  15:30 KST → UTC 06:30 → KST hour ~15
#   US_BEFORE: 22:30 KST → UTC 13:30 (EST) → KST hour ~22
#   US_AFTER:  06:30 KST → UTC 21:30 (EST) → KST hour ~6
LABEL_MAP = {
    "KR_BEFORE": "🇰🇷 국내장 시작 전",
    "KR_AFTER": "🇰🇷 국내장 마감 후",
    "US_BEFORE": "🇺🇸 미국장 시작 전",
    "US_AFTER": "🇺🇸 미국장 마감 후",
    "MANUAL": "📊 수시 브리핑",
}


def determine_briefing_type(kst_dt):
    """KST datetime으로 브리핑 타입 판별."""
    hour = kst_dt.hour

    if 7 <= hour <= 9:
        return "KR_BEFORE"
    elif 14 <= hour <= 16:
        return "KR_AFTER"
    elif 21 <= hour <= 23:
        return "US_BEFORE"
    elif 5 <= hour <= 7:
        return "US_AFTER"
    else:
        return "MANUAL"


def get_all_pages():
    """DB의 모든 페이지를 가져옴 (페이지네이션 처리)."""
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    pages = []
    has_more = True
    start_cursor = None

    while has_more:
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor

        resp = requests.post(url, headers=HEADERS, json=body, timeout=30)
        if resp.status_code != 200:
            print(f"  ❌ DB 조회 실패: {resp.status_code} {resp.text[:200]}")
            return []

        data = resp.json()
        pages.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return pages


def extract_page_info(page):
    """페이지에서 제목, 날짜, 현재 브리핑구분 추출."""
    props = page.get("properties", {})

    # 제목
    title_prop = props.get("브리핑 제목", {})
    title_arr = title_prop.get("title", [])
    title = title_arr[0].get("plain_text", "") if title_arr else "(제목 없음)"

    # 날짜
    date_prop = props.get("날짜", {})
    date_data = date_prop.get("date")
    date_str = date_data.get("start", "") if date_data else ""

    # 현재 브리핑구분
    label_prop = props.get("브리핑구분", {})
    label_select = label_prop.get("select")
    current_label = label_select.get("name", "") if label_select else ""

    return {
        "id": page["id"],
        "title": title,
        "date_str": date_str,
        "current_label": current_label,
    }


def update_page_label(page_id, new_label):
    """페이지의 브리핑구분을 업데이트."""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "브리핑구분": {"select": {"name": new_label}},
        }
    }
    resp = requests.patch(url, headers=HEADERS, json=payload, timeout=30)
    return resp.status_code == 200


def main():
    dry_run = "--dry-run" in sys.argv

    if not NOTION_API_KEY or not NOTION_DB_ID:
        print("❌ NOTION_API_KEY와 NOTION_DB_ID 환경변수를 설정해주세요.")
        sys.exit(1)

    print(f"{'🔍 [DRY RUN] ' if dry_run else ''}기존 브리핑 페이지 브리핑구분 수정 시작\n")

    pages = get_all_pages()
    print(f"총 {len(pages)}개 페이지 발견\n")

    updated = 0
    skipped = 0
    errors = 0

    for page in pages:
        info = extract_page_info(page)

        if not info["date_str"]:
            print(f"  ⏭️  날짜 없음 — {info['title']}")
            skipped += 1
            continue

        # ISO datetime 파싱
        try:
            dt = datetime.fromisoformat(info["date_str"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=KST)
            kst_dt = dt.astimezone(KST)
        except ValueError:
            print(f"  ⏭️  날짜 파싱 실패 ({info['date_str']}) — {info['title']}")
            skipped += 1
            continue

        correct_type = determine_briefing_type(kst_dt)
        correct_label = LABEL_MAP[correct_type]

        if info["current_label"] == correct_label:
            skipped += 1
            continue

        print(
            f"  {'🔄' if not dry_run else '📋'} "
            f"{info['title'][:40]}"
            f"  |  {kst_dt.strftime('%H:%M KST')}"
            f"  |  [{info['current_label']}] → [{correct_label}]"
        )

        if not dry_run:
            if update_page_label(info["id"], correct_label):
                updated += 1
            else:
                print(f"    ❌ 업데이트 실패: {info['id']}")
                errors += 1
        else:
            updated += 1

    print(f"\n{'═' * 40}")
    print(f"  {'[DRY RUN] ' if dry_run else ''}결과:")
    print(f"  수정: {updated}개  |  스킵: {skipped}개  |  오류: {errors}개")
    print(f"{'═' * 40}")

    if dry_run and updated > 0:
        print("\n💡 실제 수정하려면 --dry-run 없이 다시 실행하세요.")


if __name__ == "__main__":
    main()
