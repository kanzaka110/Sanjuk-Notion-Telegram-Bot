"""
산적 수다방 - 분위기 감지
━━━━━━━━━━━━━━━━━━━━━━━━━
메시지 패턴에서 유저의 에너지/분위기를 감지한다.
명시적으로 물어보지 않고 언어적 신호로 파악.
"""

from database import Message


def analyze_mood(current_msg: str, recent_msgs: list[Message]) -> dict:
    """유저 메시지의 분위기 신호를 분석한다."""
    user_msgs = [m for m in recent_msgs if m.role == "user"]
    avg_len = (
        sum(len(m.content) for m in user_msgs) / len(user_msgs)
        if user_msgs
        else 50
    )
    current_len = len(current_msg)
    msg_lower = current_msg.lower()

    # ─── 감정 패턴 감지 (우선 처리) ───────────────────
    # 비꼼/빈정거림
    sarcasm_markers = ["그딴", "고맙다", "잘했어", "참 좋다", "그래 뭐", "아 그래", "덕분에"]
    is_sarcastic = any(m in current_msg for m in sarcasm_markers)

    # 한숨/실망
    sigh_markers = ["에휴", "휴", "하아", "아...", "ㅠ", "ㅜ", "에잇", "아놔", "아씨"]
    is_sighing = any(m in current_msg for m in sigh_markers)

    # 짜증/분노
    annoy_markers = ["짜증", "열받", "미치", "ㅡㅡ", "화나", "빡", "개짜증", "아 진짜"]
    is_annoyed = any(m in current_msg for m in annoy_markers)

    # 기대/간절
    hopeful_markers = ["제발", "좋겠", "바란다", "기도", "됐으면", "왔으면", "오길"]
    is_hopeful = any(m in current_msg for m in hopeful_markers)

    # 기쁨/흥분
    happy_markers = ["ㅋㅋㅋ", "대박", "미쳤", "헐", "오오", "좋아", "됐다", "합격"]
    is_happy = any(m in current_msg for m in happy_markers)

    # 초간결 패턴
    ultra_casual_markers = ["ㅇㅇ", "ㄴㄴ", "ㅎ", "ㅋ", "ㄱㄱ", "ㅇㅋ", "ㄹㄹ"]
    is_ultra_casual = any(k in current_msg for k in ultra_casual_markers) and current_len <= 10

    # 감정 강도
    question_intensity = current_msg.count("?")
    exclaim_intensity = current_msg.count("!")
    ellipsis_count = current_msg.count("...")

    # 에너지 레벨
    if is_ultra_casual or current_len <= 5:
        energy = "very_low"
    elif current_len < avg_len * 0.4:
        energy = "low"
    elif current_len > avg_len * 2:
        energy = "high"
    else:
        energy = "normal"

    # ─── 분위기 종합 (감정 우선) ──────────────────────
    mood_hint = ""
    if is_sarcastic:
        mood_hint = "승호가 비꼬고 있어. 네 이전 반응이 마음에 안 든 거야. '미안, 내가 좀 그랬지' 같은 식으로 반응해. 절대 무시하거나 '응' 같은 건조한 반응 하지 마."
    elif is_annoyed:
        mood_hint = "승호가 짜증나거나 화난 상태야. 원인을 물어보거나 같이 공감해줘. 건조하게 반응하면 안 돼."
    elif is_sighing:
        mood_hint = "승호가 한숨 쉬고 있어. 지치거나 실망한 거야. '왜 그래?' 또는 같이 공감해줘. '응.' 같은 한 마디 반응은 절대 금지."
    elif is_hopeful:
        mood_hint = "승호가 뭔가를 간절히 바라고 있어. '좋은 소식 있길 바란다' 같은 진심 어린 응원 해줘."
    elif is_happy:
        mood_hint = "승호가 기뻐하거나 신나 있어. 같이 기뻐해줘!"
    elif energy == "very_low":
        mood_hint = "승호가 매우 짧게 답함. 피곤하거나 바쁜 듯. 짧게 반응하되, 감정이 있으면 무시하지 마."
    elif energy == "low":
        mood_hint = "승호가 평소보다 짧게 말함. 가볍게 반응해."
    elif energy == "high":
        mood_hint = "승호가 길게 얘기함. 관심 있는 주제. 충분히 답해줘."
    elif ellipsis_count >= 2:
        mood_hint = "승호가 망설이거나 생각 중. 재촉하지 마."

    return {
        "energy": energy,
        "is_sarcastic": is_sarcastic,
        "is_sighing": is_sighing,
        "is_annoyed": is_annoyed,
        "is_hopeful": is_hopeful,
        "is_happy": is_happy,
        "is_ultra_casual": is_ultra_casual,
        "mood_hint": mood_hint,
    }
