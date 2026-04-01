"""
사주 역학 계산 모듈 v3
━━━━━━━━━━━━━━━━━━━━━━
일진(日辰) 계산, 지장간, 12운성, 신살, 십성,
공망, 형·파·해, 시진, 납음오행, 절기,
용신/기신, 천간합충, 오행강약.
壬水 일간 기준으로 최적화.
"""

from datetime import datetime, timezone, timedelta, date

KST = timezone(timedelta(hours=9))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  기본 데이터
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CHEONGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
JIJI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

CHEONGAN_KR = {
    "甲": "갑목", "乙": "을목", "丙": "병화", "丁": "정화", "戊": "무토",
    "己": "기토", "庚": "경금", "辛": "신금", "壬": "임수", "癸": "계수",
}
JIJI_KR = {
    "子": "자수", "丑": "축토", "寅": "인목", "卯": "묘목", "辰": "진토", "巳": "사화",
    "午": "오화", "未": "미토", "申": "신금", "酉": "유금", "戌": "술토", "亥": "해수",
}

CHEONGAN_OHAENG = {
    "甲": "목", "乙": "목", "丙": "화", "丁": "화", "戊": "토",
    "己": "토", "庚": "금", "辛": "금", "壬": "수", "癸": "수",
}
JIJI_OHAENG = {
    "子": "수", "丑": "토", "寅": "목", "卯": "목", "辰": "토", "巳": "화",
    "午": "화", "未": "토", "申": "금", "酉": "금", "戌": "토", "亥": "수",
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  壬水 기준 십성(十星)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SIPSUNG_CHEONGAN = {
    "甲": "식신", "乙": "상관", "丙": "편재", "丁": "정재", "戊": "편관",
    "己": "정관", "庚": "편인", "辛": "정인", "壬": "비견", "癸": "겁재",
}
SIPSUNG_JIJI = {
    "子": "겁재", "丑": "정관", "寅": "식신", "卯": "상관", "辰": "편관", "巳": "정재",
    "午": "정재", "未": "정관", "申": "편인", "酉": "정인", "戌": "편관", "亥": "비견",
}

# 십성 의미 (운세 해석용)
SIPSUNG_MEANING = {
    "비견": "동료·경쟁·자존심. 독립심 강해지나 경쟁 주의",
    "겁재": "경쟁·손재·분리. 재물 유출 주의, 공동 투자 자제",
    "식신": "창작·표현·여유. 기술력 발휘, 먹거리 복, 자녀운",
    "상관": "재능·반항·언변. 아이디어 돋보이나 말실수 주의",
    "편재": "투기·사업·부친. 큰 돈의 움직임, 과감한 투자욕",
    "정재": "급여·안정·배우자. 고정 수입, 알뜰한 재물관리",
    "편관": "압박·권위·변동. 직장 스트레스 있으나 성과 가능",
    "정관": "직장·안정·명예. 승진/합격에 유리, 규율 준수",
    "편인": "학문·비주류·모친. 새로운 기술 습득, 독창적 해결",
    "정인": "학업·자격·도움. 시험/자격증에 유리, 귀인의 도움",
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  용신(用神) / 기신(忌神) — 사주 분석의 핵심 기준
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 채승호 사주 원국 분석:
# 일간 壬水, 巳月(화왕절) 출생 → 水가 약한 시기에 태어남
# 그러나 시지 申(장생), 년지 子(제왕)로 수기 보충 + 巳申합(금국)
# → 신강(身强)에 가까운 중화 사주
#
# 용신 결정:
# - 식상(食傷/목): 강한 수를 설기(泄氣)시켜 균형 → 용신
# - 재성(財星/화): 식상이 생하는 재물 → 희신
# - 인성(印星/금): 이미 충분, 과하면 수가 더 강해짐 → 한신(閒神)
# - 관성(官星/토): 적당한 제어 → 한신~소길
# - 비겁(比劫/수): 이미 강한 수를 더 강하게 → 기신

YONGSIN = {
    "용신(用神)": {"오행": "목", "설명": "식상(食傷) — 壬水의 강한 기운을 빼내어 창작·표현으로 발산. 기술력과 창의력의 원천"},
    "희신(喜神)": {"오행": "화", "설명": "재성(財星) — 식상이 생하는 재물. 노력의 결실, 실질적 수입. 적극적 활동이 돈이 됨"},
    "기신(忌神)": {"오행": "수", "설명": "비겁(比劫) — 이미 강한 水를 더 강하게 만듦. 경쟁 심화, 재물 분산, 독단적 행동"},
    "구신(仇神)": {"오행": "금", "설명": "인성(印星) — 금생수로 水를 더 강하게 생함. 과보호, 의존, 게으름 유발"},
    "한신(閒神)": {"오행": "토", "설명": "관성(官星) — 적당한 제어와 규율. 과하면 압박, 적당하면 직장운·명예운"},
}

# 오행별 길흉 점수 (용신 기준, +는 길, -는 흉)
OHAENG_SCORE = {
    "목": +3,   # 용신 — 가장 좋음
    "화": +2,   # 희신 — 좋음
    "토": 0,    # 한신 — 중립
    "금": -1,   # 구신 — 약간 나쁨
    "수": -2,   # 기신 — 나쁨
}


def assess_daily_yongsin(cheongan: str, jiji: str) -> dict:
    """오늘 일진의 오행이 용신/기신 중 어디에 해당하는지 분석."""
    cg_oh = CHEONGAN_OHAENG[cheongan]
    jj_oh = JIJI_OHAENG[jiji]

    cg_score = OHAENG_SCORE.get(cg_oh, 0)
    jj_score = OHAENG_SCORE.get(jj_oh, 0)
    total = cg_score + jj_score

    # 지장간 오행도 고려
    jjg = JIJANGGAN.get(jiji, ())
    jjg_scores = [OHAENG_SCORE.get(CHEONGAN_OHAENG.get(s, ""), 0) for s in jjg]
    jjg_avg = sum(jjg_scores) / len(jjg_scores) if jjg_scores else 0
    total_weighted = total + jjg_avg * 0.5

    # 종합 판단
    if total_weighted >= 3:
        grade = "대길(大吉)"
        desc = "용신·희신이 강하게 작용. 적극적으로 움직이면 좋은 결과"
    elif total_weighted >= 1:
        grade = "길(吉)"
        desc = "용신 기운이 돕는 날. 계획 실행에 좋음"
    elif total_weighted >= -1:
        grade = "평(平)"
        desc = "특별히 좋지도 나쁘지도 않은 날. 평소대로 행동"
    elif total_weighted >= -3:
        grade = "소흉(小凶)"
        desc = "기신 기운이 작용. 큰 결정은 미루고 조심히"
    else:
        grade = "흉(凶)"
        desc = "기신·구신이 강함. 무리하지 말고 방어적으로"

    # 천간·지지 각각의 용신 관계
    cg_role = next((k for k, v in YONGSIN.items() if v["오행"] == cg_oh), "한신(閒神)")
    jj_role = next((k for k, v in YONGSIN.items() if v["오행"] == jj_oh), "한신(閒神)")

    return {
        "등급": grade,
        "설명": desc,
        "점수": round(total_weighted, 1),
        "천간_역할": f"{cheongan}({cg_oh}) = {cg_role}",
        "지지_역할": f"{jiji}({jj_oh}) = {jj_role}",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  천간 합/충 (天干 合·沖)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 천간 오합 (五合) — 음양이 만나 합
CHEONGAN_HAP = {
    "甲": ("己", "토", "甲己합화토 — 의리·신뢰의 합"),
    "己": ("甲", "토", "甲己합화토 — 의리·신뢰의 합"),
    "乙": ("庚", "금", "乙庚합화금 — 인연·계약의 합"),
    "庚": ("乙", "금", "乙庚합화금 — 인연·계약의 합"),
    "丙": ("辛", "수", "丙辛합화수 — 변화·전환의 합"),
    "辛": ("丙", "수", "丙辛합화수 — 변화·전환의 합"),
    "丁": ("壬", "목", "丁壬합화목 — 지혜·창작의 합"),
    "壬": ("丁", "목", "丁壬합화목 — 지혜·창작의 합"),
    "戊": ("癸", "화", "戊癸합화화 — 열정·행동의 합"),
    "癸": ("戊", "화", "戊癸합화화 — 열정·행동의 합"),
}

# 천간 충 (沖) — 같은 오행 음양 대립
CHEONGAN_CHUNG = {
    "甲": ("庚", "甲庚충 — 목금 충돌. 계획과 현실의 갈등"),
    "庚": ("甲", "甲庚충 — 금목 충돌. 결단과 성장의 충돌"),
    "乙": ("辛", "乙辛충 — 목금 충돌. 유연함과 날카로움의 대립"),
    "辛": ("乙", "乙辛충 — 금목 충돌. 예민함과 부드러움의 대립"),
    "丙": ("壬", "丙壬충 — 화수 충돌. 재물과 자아의 정면 대결"),
    "壬": ("丙", "丙壬충 — 수화 충돌. 자아와 재물의 정면 대결"),
    "丁": ("癸", "丁癸충 — 화수 충돌. 안정과 불안의 대립"),
    "癸": ("丁", "丁癸충 — 수화 충돌. 감정과 이성의 충돌"),
}

# 원국 천간: 甲(년), 己(월), 壬(일), 戊(시)
WONKUK_CHEONGAN = ["甲", "己", "壬", "戊"]
WONKUK_CG_POS = {0: "년간(甲)", 1: "월간(己)", 2: "일간(壬)", 3: "시간(戊)"}


def check_cheongan_relations(day_cg: str) -> list[str]:
    """오늘 일진 천간과 원국 천간들의 합/충 관계를 분석."""
    results = []

    for i, wc in enumerate(WONKUK_CHEONGAN):
        pos = WONKUK_CG_POS[i]

        # 합 체크
        hap_data = CHEONGAN_HAP.get(day_cg)
        if hap_data and hap_data[0] == wc:
            results.append(f"🤝 {day_cg}-{wc} 천간합 [{pos}]: {hap_data[2]}")

        # 충 체크
        chung_data = CHEONGAN_CHUNG.get(day_cg)
        if chung_data and chung_data[0] == wc:
            results.append(f"⚡ {day_cg}-{wc} 천간충 [{pos}]: {chung_data[1]}")

        # 같은 천간 (비견/겁재 관계)
        if day_cg == wc and i != 2:  # 일간 자신은 제외
            results.append(f"🔄 {day_cg}={wc} 동간 [{pos}]: 같은 기운 중복 → 비견/겁재 에너지 강화")

    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  오행 강약(五行 强弱) 분석
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 원국의 기본 오행 분포 (천간+지지 본기)
# 甲(목) 子(수) / 己(토) 巳(화) / 壬(수) 寅(목) / 戊(토) 申(금)
WONKUK_BASE_OHAENG = {"목": 2, "화": 1, "토": 2, "금": 1, "수": 2}


def get_daily_ohaeng_balance(day_cg: str, day_jj: str) -> dict:
    """오늘 일진 추가 시 오행 밸런스 변화를 분석."""
    # 원국 기본 + 오늘 일진 + 지장간
    balance = dict(WONKUK_BASE_OHAENG)

    # 일진 천간
    cg_oh = CHEONGAN_OHAENG[day_cg]
    balance[cg_oh] = balance.get(cg_oh, 0) + 1

    # 일진 지지 (본기)
    jj_oh = JIJI_OHAENG[day_jj]
    balance[jj_oh] = balance.get(jj_oh, 0) + 1

    # 지장간 (본기만 0.5 가중)
    jjg = JIJANGGAN.get(day_jj, ())
    if jjg:
        bongi = jjg[-1]  # 본기 (마지막)
        bongi_oh = CHEONGAN_OHAENG.get(bongi, "")
        if bongi_oh:
            balance[bongi_oh] = balance.get(bongi_oh, 0) + 0.5

    total = sum(balance.values())
    max_oh = max(balance, key=balance.get)
    min_oh = min(balance, key=balance.get)

    # 壬水(일간) 기준 강약 판단
    water_support = balance.get("수", 0) + balance.get("금", 0)  # 비겁 + 인성
    water_drain = balance.get("목", 0) + balance.get("화", 0) + balance.get("토", 0)  # 식상 + 재성 + 관성

    if water_support > water_drain:
        strength = "신강(身强)"
        strength_desc = "壬水 기운이 강함 → 식상(목)·재성(화)으로 설기하면 좋음"
    elif water_support < water_drain - 1:
        strength = "신약(身弱)"
        strength_desc = "壬水 기운이 약함 → 인성(금)·비겁(수)의 도움이 필요"
    else:
        strength = "중화(中和)"
        strength_desc = "壬水 기운이 균형 → 용신(목) 방향으로 설기하면 최적"

    return {
        "분포": balance,
        "최강": f"{max_oh}({balance[max_oh]})",
        "최약": f"{min_oh}({balance[min_oh]})",
        "신강약": strength,
        "설명": strength_desc,
        "수_지원": round(water_support, 1),
        "수_소모": round(water_drain, 1),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  지장간(支藏干) — 지지 속에 숨은 천간
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# (여기, 중기, 본기) 순서. 본기가 가장 강함
JIJANGGAN = {
    "子": ("壬", "癸", "癸"),    # 여기 壬, 본기 癸
    "丑": ("癸", "辛", "己"),    # 여기 癸, 중기 辛, 본기 己
    "寅": ("戊", "丙", "甲"),    # 여기 戊, 중기 丙, 본기 甲
    "卯": ("甲", "乙", "乙"),    # 여기 甲, 본기 乙
    "辰": ("乙", "癸", "戊"),    # 여기 乙, 중기 癸, 본기 戊
    "巳": ("戊", "庚", "丙"),    # 여기 戊, 중기 庚, 본기 丙
    "午": ("丙", "己", "丁"),    # 여기 丙, 중기 己, 본기 丁
    "未": ("丁", "乙", "己"),    # 여기 丁, 중기 乙, 본기 己
    "申": ("己", "壬", "庚"),    # 여기 己, 중기 壬, 본기 庚
    "酉": ("庚", "辛", "辛"),    # 여기 庚, 본기 辛
    "戌": ("辛", "丁", "戊"),    # 여기 辛, 중기 丁, 본기 戊
    "亥": ("戊", "甲", "壬"),    # 여기 戊, 중기 甲, 본기 壬
}


def get_jijanggan_sipsung(jiji: str) -> list[tuple[str, str, str]]:
    """지지의 지장간을 壬水 기준 십성으로 변환. [(천간, 십성, 역할)] 반환."""
    stems = JIJANGGAN.get(jiji, ())
    roles = ["여기", "중기", "본기"]
    result = []
    for i, stem in enumerate(stems):
        ss = SIPSUNG_CHEONGAN[stem]
        result.append((stem, ss, roles[i]))
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  12운성 (壬水 일간 기준)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TWELVE_STAGES = {
    "申": "장생(長生)", "酉": "목욕(沐浴)", "戌": "관대(冠帶)", "亥": "건록(建祿)",
    "子": "제왕(帝旺)", "丑": "쇠(衰)", "寅": "병(病)", "卯": "사(死)",
    "辰": "묘(墓)", "巳": "절(絕)", "午": "태(胎)", "未": "양(養)",
}

TWELVE_STAGES_DESC = {
    "장생(長生)": "새로운 시작의 에너지. 기운이 솟아남. 새 프로젝트, 학습 시작에 좋음",
    "목욕(沐浴)": "변화·불안정. 감정 기복 주의. 중요한 결정은 미루는 게 좋음",
    "관대(冠帶)": "성장·준비. 자신감 상승. 면접, 발표에 유리",
    "건록(建祿)": "최고 안정. 직장·수입 안정. 실력 발휘에 최적",
    "제왕(帝旺)": "절정의 힘. 과욕 주의하면 최고 성과. 리더십 발휘",
    "쇠(衰)": "하강 시작. 무리하지 말고 정리. 건강 관리 필수",
    "병(病)": "에너지 저하. 건강 주의. 충전에 집중",
    "사(死)": "전환·마무리. 끝과 새 시작의 경계. 과거 정리에 좋음",
    "묘(墓)": "저장·축적. 재물 모으기 좋음. 내면 성찰",
    "절(絕)": "단절·재생. 오래된 것과의 이별. 비움의 시간",
    "태(胎)": "잉태. 새 계획을 품는 시기. 아직 드러내지 말 것",
    "양(養)": "양육·준비. 조용히 실력을 키우는 시기. 학습에 좋음",
}

# 12운성 에너지 수치 (운세 등급 계산용, 10점 만점)
TWELVE_STAGES_SCORE = {
    "장생(長生)": 8, "목욕(沐浴)": 5, "관대(冠帶)": 7, "건록(建祿)": 9,
    "제왕(帝旺)": 10, "쇠(衰)": 4, "병(病)": 3, "사(死)": 2,
    "묘(墓)": 5, "절(絕)": 1, "태(胎)": 4, "양(養)": 6,
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  공망(空亡) — 해당 旬에서 비어있는 지지
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 60甲子는 6旬으로 나뉨. 각 旬은 10일(천간 1순환).
# 10천간에 12지지를 배정하면 2개가 남음 = 공망.

GONGMANG_BY_XUN = {
    # 旬 시작 간지 인덱스: (공망 지지1, 공망 지지2)
    0: ("戌", "亥"),   # 甲子旬: 戌亥 공망
    10: ("申", "酉"),  # 甲戌旬: 申酉 공망
    20: ("午", "未"),  # 甲申旬: 午未 공망
    30: ("辰", "巳"),  # 甲午旬: 辰巳 공망
    40: ("寅", "卯"),  # 甲辰旬: 寅卯 공망
    50: ("子", "丑"),  # 甲寅旬: 子丑 공망
}


def get_gongmang(ganji_idx: int) -> tuple[str, str]:
    """60갑자 인덱스로부터 해당 旬의 공망 지지 2개를 반환."""
    xun_start = (ganji_idx // 10) * 10
    return GONGMANG_BY_XUN[xun_start]


def check_gongmang_effect(ganji_idx: int) -> str | None:
    """일진의 공망이 원국 지지와 겹치는지 확인. 겹치면 설명 반환."""
    gm1, gm2 = get_gongmang(ganji_idx)
    wonkuk_names = {"子": "년지", "巳": "월지", "寅": "일지", "申": "시지"}
    effects = []
    for gm in (gm1, gm2):
        if gm in wonkuk_names:
            pos = wonkuk_names[gm]
            effects.append(f"{gm}({pos}) 공망")
    if not effects:
        return None
    return "오늘 " + ", ".join(effects) + " — 해당 궁의 일이 허(虛)해지기 쉬움. 과신 금물, 실질적 결과 확인 필요"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  형·파·해 (刑·破·害)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 형(刑) — 고통·시련·법적 문제
HYUNG = {
    "寅": ["巳", "申"],  # 寅巳申 삼형 (무은지형)
    "巳": ["寅", "申"],
    "申": ["寅", "巳"],
    "丑": ["戌", "未"],  # 丑戌未 삼형 (지세지형)
    "戌": ["丑", "未"],
    "未": ["丑", "戌"],
    "子": ["卯"],        # 子卯형 (무례지형)
    "卯": ["子"],
    "辰": ["辰"],        # 자형 (辰辰, 午午, 酉酉, 亥亥)
    "午": ["午"],
    "酉": ["酉"],
    "亥": ["亥"],
}

# 파(破) — 파괴·손상
PA = {
    "子": "酉", "酉": "子", "丑": "辰", "辰": "丑",
    "寅": "亥", "亥": "寅", "卯": "午", "午": "卯",
    "巳": "申", "申": "巳", "未": "戌", "戌": "未",
}

# 해(害) — 원망·방해·건강 악화
HAE = {
    "子": "未", "未": "子", "丑": "午", "午": "丑",
    "寅": "巳", "巳": "寅", "卯": "辰", "辰": "卯",
    "申": "亥", "亥": "申", "酉": "戌", "戌": "酉",
}

WONKUK_JIJI = ["子", "巳", "寅", "申"]
WONKUK_POS = {0: "년지(子)", 1: "월지(巳)", 2: "일지(寅)", 3: "시지(申)"}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  충·합 (기존)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CHUNG_PAIRS = {
    "子": "午", "午": "子", "丑": "未", "未": "丑",
    "寅": "申", "申": "寅", "卯": "酉", "酉": "卯",
    "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳",
}

HAP_PAIRS = {
    "子": "丑", "丑": "子", "寅": "亥", "亥": "寅",
    "卯": "戌", "戌": "卯", "辰": "酉", "酉": "辰",
    "巳": "申", "申": "巳", "午": "未", "未": "午",
}

SAMHAP = {
    "申": ("子", "辰", "수국"), "子": ("申", "辰", "수국"), "辰": ("申", "子", "수국"),
    "寅": ("午", "戌", "화국"), "午": ("寅", "戌", "화국"), "戌": ("寅", "午", "화국"),
    "巳": ("酉", "丑", "금국"), "酉": ("巳", "丑", "금국"), "丑": ("巳", "酉", "금국"),
    "亥": ("卯", "未", "목국"), "卯": ("亥", "未", "목국"), "未": ("亥", "卯", "목국"),
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  신살(神殺) — 확장
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SINSAL = {
    "역마(驛馬)": {"지지": ["寅", "申"], "설명": "이동·변화·이직. 출장, 여행, 이사 가능성"},
    "도화(桃花)": {"지지": ["酉"], "설명": "매력·인기·이성운. 대인관계 좋으나 유혹 주의"},
    "화개(華蓋)": {"지지": ["辰"], "설명": "학문·예술·영감. 창작, 기술 연구에 좋음"},
    "천을귀인(天乙貴人)": {"지지": ["卯", "巳"], "설명": "귀인의 도움. 어려운 일이 풀림"},
    "문창귀인(文昌貴人)": {"지지": ["巳"], "설명": "시험·문서·계약에 유리. 합격·승인"},
    "장성(將星)": {"지지": ["子"], "설명": "리더십·권위. 주도적으로 일을 이끌기에 좋음"},
    "금여(金輿)": {"지지": ["辰"], "설명": "안정·풍요. 재물과 명예가 함께 오는 길한 살"},
    "천덕귀인(天德貴人)": {"지지": ["丑"], "설명": "하늘의 덕. 위기에서 도움, 소송 유리"},
    "월덕귀인(月德貴人)": {"지지": ["壬"], "설명": "월의 덕. 사고·질병 예방, 평안"},  # 천간 기준이지만 참고용
    "양인(羊刃)": {"지지": ["子"], "설명": "날카로운 기운. 결단력 있으나 과격함 주의"},
    "겁살(劫殺)": {"지지": ["巳"], "설명": "도난·사기 주의. 문서 확인 철저히"},
    "재살(災殺)": {"지지": ["午"], "설명": "사고·재해 주의. 안전 운전, 위험 활동 자제"},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  납음오행(納音五行) — 60甲子 고유 오행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 60甲子 순서대로, 2개씩 같은 납음
_NAPEUM_LIST = [
    "해중금(海中金)", "해중금(海中金)",     # 甲子, 乙丑
    "노중화(爐中火)", "노중화(爐中火)",     # 丙寅, 丁卯
    "대림목(大林木)", "대림목(大林木)",     # 戊辰, 己巳
    "노방토(路傍土)", "노방토(路傍土)",     # 庚午, 辛未
    "검봉금(劍鋒金)", "검봉금(劍鋒金)",     # 壬申, 癸酉
    "산두화(山頭火)", "산두화(山頭火)",     # 甲戌, 乙亥
    "간하수(澗下水)", "간하수(澗下水)",     # 丙子, 丁丑
    "성두토(城頭土)", "성두토(城頭土)",     # 戊寅, 己卯
    "백랍금(白蠟金)", "백랍금(白蠟金)",     # 庚辰, 辛巳
    "양류목(楊柳木)", "양류목(楊柳木)",     # 壬午, 癸未
    "천중수(泉中水)", "천중수(泉中水)",     # 甲申, 乙酉
    "옥상토(屋上土)", "옥상토(屋上土)",     # 丙戌, 丁亥
    "벽력화(霹靂火)", "벽력화(霹靂火)",     # 戊子, 己丑
    "송백목(松柏木)", "송백목(松柏木)",     # 庚寅, 辛卯
    "장류수(長流水)", "장류수(長流水)",     # 壬辰, 癸巳
    "사중금(沙中金)", "사중금(沙中金)",     # 甲午, 乙未
    "산하화(山下火)", "산하화(山下火)",     # 丙申, 丁酉
    "평지목(平地木)", "평지목(平地木)",     # 戊戌, 己亥
    "벽상토(壁上土)", "벽상토(壁上土)",     # 庚子, 辛丑
    "금박금(金箔金)", "금박금(金箔金)",     # 壬寅, 癸卯
    "복등화(覆燈火)", "복등화(覆燈火)",     # 甲辰, 乙巳
    "천하수(天河水)", "천하수(天河水)",     # 丙午, 丁未
    "대역토(大驛土)", "대역토(大驛土)",     # 戊申, 己酉
    "차천금(釵釧金)", "차천금(釵釧金)",     # 庚戌, 辛亥
    "상자목(桑柘木)", "상자목(桑柘木)",     # 壬子, 癸丑
    "대계수(大溪水)", "대계수(大溪水)",     # 甲寅, 乙卯
    "사중토(沙中土)", "사중토(沙中土)",     # 丙辰, 丁巳
    "천상화(天上火)", "천상화(天上火)",     # 戊午, 己未
    "석류목(石榴木)", "석류목(石榴木)",     # 庚申, 辛酉
    "대해수(大海水)", "대해수(大海水)",     # 壬戌, 癸亥
]

# 납음과 壬水의 상성
NAPEUM_COMPAT = {
    "금": "금생수(金生水) — 나를 생해주는 기운. 도움과 지원의 날",
    "수": "비화(比和) — 같은 수 기운. 동료·협력 에너지",
    "목": "수생목(水生木) — 내가 에너지를 쓰는 날. 창작·봉사에 좋으나 피로 주의",
    "화": "수극화(水克火) — 내가 제어하는 기운. 재물운이나 에너지 소모",
    "토": "토극수(土克水) — 나를 억제하는 기운. 압박감 있으나 절제 배움",
}


def get_napeum(ganji_idx: int) -> str:
    """60갑자 인덱스로 납음오행을 반환."""
    return _NAPEUM_LIST[ganji_idx]


def get_napeum_element(napeum: str) -> str:
    """납음에서 오행 추출."""
    if "금" in napeum.split("(")[0][-1:]:
        return "금"
    if "수" in napeum.split("(")[0][-1:]:
        return "수"
    if "목" in napeum.split("(")[0][-1:]:
        return "목"
    if "화" in napeum.split("(")[0][-1:]:
        return "화"
    if "토" in napeum.split("(")[0][-1:]:
        return "토"
    # 한자 기준
    name = napeum.split("(")[1].rstrip(")")
    if name.endswith("金"):
        return "금"
    if name.endswith("水"):
        return "수"
    if name.endswith("木"):
        return "목"
    if name.endswith("火"):
        return "화"
    if name.endswith("土"):
        return "토"
    return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  시진(時辰) — 12시진 간지 계산
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 시간대 → 지지
SIJIN_RANGES = [
    (23, 1, "子"), (1, 3, "丑"), (3, 5, "寅"), (5, 7, "卯"),
    (7, 9, "辰"), (9, 11, "巳"), (11, 13, "午"), (13, 15, "未"),
    (15, 17, "申"), (17, 19, "酉"), (19, 21, "戌"), (21, 23, "亥"),
]

# 일간에 따른 시두법(時頭法) — 일간으로 자시(子時)의 천간 결정
SIDU = {
    "甲": "甲", "己": "甲",  # 甲子~
    "乙": "丙", "庚": "丙",  # 丙子~
    "丙": "戊", "辛": "戊",  # 戊子~
    "丁": "壬", "壬": "壬",  # 壬子~
    "戊": "壬", "癸": "甲",  # 실제: 戊→壬, 癸→甲 (오류 방지)
}
# 정확한 시두법
SIDU_CORRECT = {"甲": 0, "己": 0, "乙": 2, "庚": 2, "丙": 4, "辛": 4, "丁": 6, "壬": 6, "戊": 8, "癸": 8}


def get_hour_jiji(hour: int) -> str:
    """시간(0~23)으로 시진 지지를 반환."""
    if hour == 23 or hour == 0:
        return "子"
    for start, end, jj in SIJIN_RANGES:
        if start <= hour < end:
            return jj
    return "子"


def get_hour_ganji(day_cheongan: str, hour: int) -> tuple[str, str]:
    """일간과 시간으로 시진의 천간·지지를 반환."""
    jiji = get_hour_jiji(hour)
    jiji_idx = JIJI.index(jiji)
    base_cg_idx = SIDU_CORRECT.get(day_cheongan, 0)
    cg_idx = (base_cg_idx + jiji_idx) % 10
    return CHEONGAN[cg_idx], jiji


def get_best_hours(day_cheongan: str) -> list[dict]:
    """오늘의 길시(吉時)와 흉시(凶時)를 반환."""
    results = []
    for start, end, jj in SIJIN_RANGES:
        cg, _ = get_hour_ganji(day_cheongan, start)
        ss_cg = SIPSUNG_CHEONGAN[cg]
        ss_jj = SIPSUNG_JIJI[jj]
        stage = TWELVE_STAGES.get(jj, "")
        score = TWELVE_STAGES_SCORE.get(stage, 5)

        # 길흉 판단
        good_ss = {"정인", "정재", "식신", "정관"}
        bad_ss = {"겁재", "상관", "편관"}
        ss_score = 0
        if ss_cg in good_ss:
            ss_score += 2
        if ss_jj in good_ss:
            ss_score += 2
        if ss_cg in bad_ss:
            ss_score -= 1
        if ss_jj in bad_ss:
            ss_score -= 1

        total = score + ss_score
        hour_str = f"{start:02d}:00~{end:02d}:00" if start < end else f"{start:02d}:00~01:00"

        results.append({
            "시간": hour_str,
            "간지": f"{cg}{jj}",
            "십성": f"{ss_cg}+{ss_jj}",
            "12운성": stage.split("(")[0] if stage else "",
            "점수": total,
        })

    return sorted(results, key=lambda x: x["점수"], reverse=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  절기(節氣) — 2026년 24절기
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 2026년 절기 날짜 (절기만, 중기 제외 — 월 경계는 절기로 결정)
JEOLGI_2026 = [
    (date(2026, 1, 5), "소한(小寒)", "丑월 시작"),
    (date(2026, 2, 4), "입춘(立春)", "寅월 시작 — 새해 시작"),
    (date(2026, 3, 5), "경칩(驚蟄)", "卯월 시작"),
    (date(2026, 4, 5), "청명(清明)", "辰월 시작"),
    (date(2026, 5, 5), "입하(立夏)", "巳월 시작"),
    (date(2026, 6, 5), "망종(芒種)", "午월 시작"),
    (date(2026, 7, 7), "소서(小暑)", "未월 시작"),
    (date(2026, 8, 7), "입추(立秋)", "申월 시작"),
    (date(2026, 9, 7), "백로(白露)", "酉월 시작"),
    (date(2026, 10, 8), "한로(寒露)", "戌월 시작"),
    (date(2026, 11, 7), "입동(立冬)", "亥월 시작"),
    (date(2026, 12, 7), "대설(大雪)", "子월 시작"),
]


def get_current_jeolgi(target_date: date) -> tuple[str, str, str | None]:
    """현재 절기와 다음 절기 정보를 반환. (현재절기, 월지지, 다음절기정보)"""
    current_jeolgi = "동지(冬至)"
    current_month = "丑"
    next_info = None

    for i, (jdate, jname, jdesc) in enumerate(JEOLGI_2026):
        if target_date < jdate:
            days_left = (jdate - target_date).days
            next_info = f"{jname} ({jdate.month}/{jdate.day}, {days_left}일 후)"
            break
        current_jeolgi = jname
        current_month = jdesc.split("월")[0][-1] if "월" in jdesc else current_month

    return current_jeolgi, current_month, next_info


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  일진(日辰) 계산
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_REF_DATE = date(2026, 1, 1)
_REF_GANJI_IDX = 18  # 壬午


def get_daily_ganji(target: date) -> tuple[str, str, int]:
    """주어진 날짜의 일진(천간, 지지)과 60갑자 인덱스를 반환."""
    delta_days = (target - _REF_DATE).days
    ganji_idx = (_REF_GANJI_IDX + delta_days) % 60
    cheongan = CHEONGAN[ganji_idx % 10]
    jiji = JIJI[ganji_idx % 12]
    return cheongan, jiji, ganji_idx


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  종합 분석 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_daily_analysis(target_date: date | None = None) -> str:
    """특정 날짜의 일진 종합 분석 텍스트를 반환."""
    if target_date is None:
        target_date = datetime.now(KST).date()

    cheongan, jiji, ganji_idx = get_daily_ganji(target_date)

    lines = []
    lines.append(f"[오늘의 일진: {cheongan}{jiji} ({CHEONGAN_KR[cheongan]}/{JIJI_KR[jiji]})]")

    # ★ 용신 분석 (가장 중요)
    yongsin = assess_daily_yongsin(cheongan, jiji)
    lines.append(f"- ★ 용신 판정: {yongsin['등급']} (점수 {yongsin['점수']}) — {yongsin['설명']}")
    lines.append(f"  천간: {yongsin['천간_역할']}")
    lines.append(f"  지지: {yongsin['지지_역할']}")

    # 납음오행
    napeum = get_napeum(ganji_idx)
    nap_elem = get_napeum_element(napeum)
    nap_compat = NAPEUM_COMPAT.get(nap_elem, "")
    lines.append(f"- 납음: {napeum} → {nap_compat}")

    # 십성 분석 (천간)
    cg_sipsung = SIPSUNG_CHEONGAN[cheongan]
    jj_sipsung = SIPSUNG_JIJI[jiji]
    lines.append(f"- 천간 {cheongan}({CHEONGAN_KR[cheongan]}) = {cg_sipsung}: {SIPSUNG_MEANING[cg_sipsung]}")
    lines.append(f"- 지지 {jiji}({JIJI_KR[jiji]}) = {jj_sipsung}: {SIPSUNG_MEANING[jj_sipsung]}")

    # 지장간 분석
    jjg = get_jijanggan_sipsung(jiji)
    jjg_str = ", ".join(f"{role} {stem}({ss})" for stem, ss, role in jjg)
    lines.append(f"- 지장간: {jjg_str}")

    # 12운성
    stage = TWELVE_STAGES.get(jiji, "")
    if stage:
        desc = TWELVE_STAGES_DESC.get(stage, "")
        score = TWELVE_STAGES_SCORE.get(stage, 5)
        lines.append(f"- 12운성: {stage} (에너지 {score}/10) — {desc}")

    # 절기 정보
    jeolgi, month_jj, next_jeolgi = get_current_jeolgi(target_date)
    jeolgi_line = f"- 절기: {jeolgi} ({month_jj}월)"
    if next_jeolgi:
        jeolgi_line += f" | 다음: {next_jeolgi}"
    lines.append(jeolgi_line)

    # 원국 지지와의 관계 (충·합·삼합·형·파·해)
    interactions = []
    for i, wj in enumerate(WONKUK_JIJI):
        pos = WONKUK_POS[i]

        if CHUNG_PAIRS.get(jiji) == wj:
            interactions.append(f"  ⚡ {jiji}-{wj} 충(衝) [{pos}]: 긴장·변동·충돌의 에너지")
        if HAP_PAIRS.get(jiji) == wj:
            interactions.append(f"  🤝 {jiji}-{wj} 합(合) [{pos}]: 조화·결합·협력의 에너지")

        samhap_data = SAMHAP.get(jiji)
        if samhap_data and wj in (samhap_data[0], samhap_data[1]):
            interactions.append(f"  🔺 {jiji}-{wj} 반합 [{pos}]: {samhap_data[2]} 형성")

        hyung_targets = HYUNG.get(jiji, [])
        if wj in hyung_targets:
            interactions.append(f"  ⚠️ {jiji}-{wj} 형(刑) [{pos}]: 시련·갈등·법적 문제 주의")

        if PA.get(jiji) == wj:
            interactions.append(f"  💔 {jiji}-{wj} 파(破) [{pos}]: 파괴·손상 에너지. 기존 것이 깨질 수 있음")

        if HAE.get(jiji) == wj:
            interactions.append(f"  😤 {jiji}-{wj} 해(害) [{pos}]: 원망·방해. 건강 악화 또는 배신 주의")

    # 천간 합/충 관계 (신규)
    cg_relations = check_cheongan_relations(cheongan)
    if cg_relations:
        interactions.extend(cg_relations)

    if interactions:
        lines.append("- 원국과의 관계:")
        lines.extend(interactions)
    else:
        lines.append("- 원국과의 관계: 특별한 충·합·형 없음 (평온한 날)")

    # 공망 체크
    gm_effect = check_gongmang_effect(ganji_idx)
    gm1, gm2 = get_gongmang(ganji_idx)
    lines.append(f"- 공망: {gm1}{gm2}")
    if gm_effect:
        lines.append(f"  ⚠️ {gm_effect}")

    # 신살 체크
    active_sinsal = []
    for name, data in SINSAL.items():
        if jiji in data["지지"]:
            active_sinsal.append(f"  ✦ {name}: {data['설명']}")
    if active_sinsal:
        lines.append("- 발동 신살:")
        lines.extend(active_sinsal)

    # 길시·흉시 (상위 3개 / 하위 2개)
    hours = get_best_hours(cheongan)
    lines.append("- 오늘의 길시(吉時):")
    for h in hours[:3]:
        lines.append(f"  ⭐ {h['시간']} {h['간지']} [{h['십성']}] {h['12운성']}")
    lines.append("- 오늘의 주의 시간:")
    for h in hours[-2:]:
        lines.append(f"  ⛔ {h['시간']} {h['간지']} [{h['십성']}] {h['12운성']}")

    # 오행 강약 분석 (신규)
    ohaeng = get_daily_ohaeng_balance(cheongan, jiji)
    dist = ohaeng["분포"]
    dist_str = " ".join(f"{k}{v}" for k, v in sorted(dist.items(), key=lambda x: -x[1]))
    lines.append(f"- 오행 밸런스: {dist_str}")
    lines.append(f"  {ohaeng['신강약']}: {ohaeng['설명']}")
    lines.append(f"  (수 지원: {ohaeng['수_지원']} vs 수 소모: {ohaeng['수_소모']})")

    return "\n".join(lines)


def get_week_analysis(start_date: date | None = None) -> str:
    """이번 주(월~일) 7일간의 일진 요약을 반환."""
    if start_date is None:
        start_date = datetime.now(KST).date()

    weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
    lines = ["[이번 주 일진 흐름]"]

    for i in range(7):
        d = start_date + timedelta(days=i)
        cg, jj, idx = get_daily_ganji(d)
        stage = TWELVE_STAGES.get(jj, "")
        score = TWELVE_STAGES_SCORE.get(stage, 5)
        cg_ss = SIPSUNG_CHEONGAN[cg]
        jj_ss = SIPSUNG_JIJI[jj]

        # 충/합/형 간단 표시
        markers = []
        for wj in WONKUK_JIJI:
            if CHUNG_PAIRS.get(jj) == wj:
                markers.append("⚡충")
            if HAP_PAIRS.get(jj) == wj:
                markers.append("🤝합")
            hyung_targets = HYUNG.get(jj, [])
            if wj in hyung_targets:
                markers.append("⚠️형")

        # 공망 표시
        gm_eff = check_gongmang_effect(idx)
        if gm_eff:
            markers.append("🕳️공망")

        # 신살 표시
        for name, data in SINSAL.items():
            if jj in data["지지"]:
                short = name.split("(")[0]
                markers.append(f"✦{short}")

        marker_str = f" [{', '.join(markers)}]" if markers else ""
        stage_short = stage.split("(")[0] if stage else ""

        lines.append(
            f"  {weekday_names[i]} {d.month}/{d.day}: "
            f"{cg}{jj} [{cg_ss}+{jj_ss}] {stage_short}({score}점){marker_str}"
        )

    return "\n".join(lines)
