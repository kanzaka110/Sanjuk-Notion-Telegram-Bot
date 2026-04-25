"""
의도 감지 + 자동 실행 라우터
━━━━━━━━━━━━━━━━━━━━━━━━━━━
대화에서 의도를 파악하여 명령을 자동 실행.
"내일 3시 미팅 잡아줘" → 캘린더 등록
"커피 5500원" → 지출 기록
"""

import asyncio
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared_config import claude_cli

log = logging.getLogger(__name__)

INTENT_PROMPT = """사용자 메시지에서 실행 가능한 의도를 감지해줘.

메시지: "{message}"

가능한 의도:
- schedule: 일정 등록 ("내일 3시 미팅 잡아줘", "다음주 화요일에 치과 예약")
- todo_add: 할일 추가 ("할일 추가해줘 보고서", "리타겟 작업 해야돼 메모해둬")
- todo_done: 할일 완료 ("1번 할일 끝났어", "보고서 다 했어")
- spend: 지출 기록 ("커피 5500원", "점심 12000원 썼어")
- search: 웹 검색 ("UE5.6 뭐 바뀌었어?", "코스피 지금 얼마야?")
- work_start: 작업 시작 ("리타겟 작업 시작", "IK 셋업 들어간다")
- work_stop: 작업 종료 ("작업 끝", "퇴근이다")
- focus_on: 집중 모드 ("집중 모드 켜줘", "90분 집중할게")
- focus_off: 집중 모드 해제 ("집중 모드 꺼", "끝났어 알림 보여줘")
- note: 메모 저장 ("기억해둬: P4 브랜치 규칙은...", "메모해둬")
- exec: GCP 명령 ("운세봇 로그 확인해줘", "서버 메모리 얼마나 써?")
- condition: 컨디션 기록 ("오늘 6시간 잤어 컨디션 7점")
- none: 위에 해당 없음 (일반 대화)

JSON으로만 답해. 다른 텍스트 금지:
{{"intent": "의도명", "params": "실행에 필요한 핵심 텍스트"}}

예시:
- "내일 오후 3시에 팀 미팅" → {{"intent": "schedule", "params": "내일 오후 3시 팀 미팅"}}
- "커피 5500" → {{"intent": "spend", "params": "커피 5500"}}
- "요즘 날씨 어때?" → {{"intent": "none", "params": ""}}
- "리타겟 작업 시작할게" → {{"intent": "work_start", "params": "리타겟 작업"}}"""


def detect_intent(message: str) -> dict:
    """메시지에서 의도를 감지한다."""
    prompt = INTENT_PROMPT.format(message=message[:300])
    result = claude_cli(prompt, model="haiku", timeout=15)

    if not result:
        return {"intent": "none", "params": ""}

    try:
        json_match = re.search(r'\{[^}]+\}', result)
        if json_match:
            return json.loads(json_match.group())
    except (json.JSONDecodeError, KeyError):
        pass

    return {"intent": "none", "params": ""}


async def detect_intent_async(message: str) -> dict:
    return await asyncio.to_thread(detect_intent, message)


async def execute_intent(intent: dict) -> str | None:
    """감지된 의도를 실행하고 결과를 반환한다."""
    action = intent.get("intent", "none")
    params = intent.get("params", "")

    if action == "none" or not params:
        return None

    try:
        if action == "schedule":
            from calendar_writer import parse_and_create_event
            event = await asyncio.to_thread(parse_and_create_event, params)
            if event:
                return f"일정 등록 완료: {event['summary']}"
            return "일정 등록 실패했어. 다시 말해줘."

        elif action == "todo_add":
            from todo_manager import add_todo
            item = add_todo(params)
            return f"할일 추가: #{item['id']} {item['text']}"

        elif action == "todo_done":
            from todo_manager import complete_todo
            # 숫자 추출
            nums = re.findall(r'\d+', params)
            if nums:
                item = complete_todo(int(nums[0]))
                if item:
                    return f"할일 완료: #{item['id']} {item['text']}"
            return None

        elif action == "spend":
            from expense_tracker import parse_expense, add_expense, get_today_expenses
            parsed = parse_expense(params)
            if parsed:
                item = add_expense(parsed["description"], parsed["amount"])
                today = get_today_expenses()
                total = sum(e["amount"] for e in today)
                return f"지출 기록: {item['description']} {item['amount']:,}원 (오늘 총 {total:,}원)"
            return None

        elif action == "search":
            from web_search import search_web_async
            result = await search_web_async(params)
            return result[:2000] if result else None

        elif action == "work_start":
            from work_timer import start_work
            return start_work(params)

        elif action == "work_stop":
            from work_timer import stop_work
            return stop_work()

        elif action == "focus_on":
            from focus_mode import start_focus
            nums = re.findall(r'\d+', params)
            minutes = int(nums[0]) if nums else 90
            return start_focus(minutes)

        elif action == "focus_off":
            from focus_mode import stop_focus
            return stop_focus()

        elif action == "note":
            from rag_memory import store_memory
            store_memory(params, {"source": "manual_note", "category": "onboarding"})
            return f"메모 저장 완료 ({len(params)}자)"

        elif action == "exec":
            from remote_exec import handle_exec
            return await handle_exec(params)

        elif action == "condition":
            from condition_tracker import log_condition
            nums = re.findall(r'[\d.]+', params)
            if len(nums) >= 2:
                entry = log_condition(float(nums[0]), int(float(nums[1])))
                return f"기록: 수면 {entry['sleep']}h, 컨디션 {entry['score']}/10"
            elif len(nums) == 1:
                entry = log_condition(float(nums[0]), 5)
                return f"기록: 수면 {entry['sleep']}h, 컨디션 5/10"
            return None

    except Exception as e:
        log.error("의도 실행 실패 [%s]: %s", action, e)
        return None

    return None
