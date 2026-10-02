"""정착 안정도 채점 (팀 자체 채점 기준).

점수가 높을수록 안정적. THRESHOLD 미만이면 멘토·상담 연계를 먼저 제안한다.
채점 기준표는 발표 때 그대로 공개할 수 있도록 이 파일에만 둔다.
"""
from .. import memory

THRESHOLD = 50

KOREAN_POINTS = {0: 0, 1: 10, 2: 20, 3: 25}


def _months_points(m: int) -> int:
    if m >= 12:
        return 20
    if m >= 6:
        return 12
    if m >= 3:
        return 6
    return 0


# (항목, 최대점수, 프로필 키, 점수 함수)
CRITERIA = [
    ("한국어 수준", 25, "korean_level", lambda v: KOREAN_POINTS[v]),
    ("주변 도움 가능", 20, "has_local_support", lambda v: 20 if v else 0),
    ("직장 내 어려움 없음", 20, "workplace_issue", lambda v: 0 if v else 20),
    ("지원사업 인지", 15, "knows_support_programs", lambda v: 15 if v else 0),
    ("정착 경과 기간", 20, "months_in_korea", _months_points),
]


def compute_score(profile: dict) -> dict:
    """프로필만으로 점수를 계산하는 순수 함수(테스트 대상).
    모르는 항목이 있으면 판정하지 않고 되물을 항목(missing)만 돌려준다."""
    breakdown, missing, total = [], [], 0
    for label, max_pts, key, fn in CRITERIA:
        if key not in profile:
            missing.append(key)
            pts = 0
        else:
            pts = fn(profile[key])
        total += pts
        breakdown.append({"item": label, "points": pts, "max": max_pts})
    if missing:
        return {
            "complete": False,
            "score": None,
            "threshold": THRESHOLD,
            "recommend_mentoring_first": None,
            "breakdown": breakdown,
            "missing": missing,
        }
    return {
        "complete": True,
        "score": total,
        "threshold": THRESHOLD,
        "recommend_mentoring_first": total < THRESHOLD,
        "breakdown": breakdown,
        "missing": missing,
    }


def score_risk() -> dict:
    return compute_score(memory.load()["profile"])
