"""규칙 기반 정착 로드맵 생성.

각 규칙은 (조건, 단계)로 구성된다. 조건이 참인 단계만 priority 순서로 나열한다.
법적 판단은 하지 않고 '확인하기 / 신청하기 / 상담받기' 수준의 행동만 안내한다.
TODO(정태현): 팀 조사 결과에 맞게 규칙과 문구를 다듬기.
"""
from .. import memory

RULES = [
    {
        "id": "registration_check",
        "title": "외국인등록·체류지 신고 여부 확인 (출입국·외국인청 공식 안내 확인)",
        "category": "행정",
        "priority": 10,
        "when": lambda p: p.get("months_in_korea", 99) <= 3,
    },
    {
        "id": "bank_phone",
        "title": "은행 계좌·휴대전화 개통",
        "category": "생활",
        "priority": 20,
        "when": lambda p: p.get("months_in_korea", 99) <= 3,
    },
    {
        "id": "health_insurance",
        "title": "건강보험 가입 여부 확인",
        "category": "생활",
        "priority": 30,
        "when": lambda p: p.get("months_in_korea", 99) <= 6,
    },
    {
        "id": "community",
        "title": "지역 이주민 커뮤니티·멘토 연결",
        "category": "멘토링",
        "priority": 35,
        "when": lambda p: p.get("has_local_support") is False,
    },
    {
        "id": "korean_class",
        "title": "한국어교육 신청",
        "category": "한국어교육",
        "priority": 40,
        "when": lambda p: p.get("korean_level", 3) <= 1,
    },
    {
        "id": "children_school",
        "title": "자녀 보육·학교 정보 확인",
        "category": "자녀교육",
        "priority": 50,
        "when": lambda p: p.get("has_children") is True,
    },
    {
        "id": "workplace_counsel",
        "title": "직장 고충 상담 받기",
        "category": "노동상담",
        "priority": 60,
        "when": lambda p: p.get("workplace_issue") is True,
    },
    {
        "id": "job_support",
        "title": "취업 지원 프로그램 확인",
        "category": "취업",
        "priority": 70,
        "when": lambda p: p.get("job_status") == "seeking",
    },
    {
        "id": "law_counsel",
        "title": "생활법률상담 창구 알아두기",
        "category": "법률상담",
        "priority": 90,
        "when": lambda p: True,
    },
]


def generate_steps(profile: dict) -> list[dict]:
    """프로필만으로 단계 목록을 계산하는 순수 함수(테스트 대상)."""
    steps = [r for r in RULES if r["when"](profile)]
    steps.sort(key=lambda r: r["priority"])
    return [
        {"order": i + 1, "id": r["id"], "title": r["title"], "category": r["category"], "done": False}
        for i, r in enumerate(steps)
    ]


def build_roadmap() -> dict:
    state = memory.load()
    steps = generate_steps(state["profile"])
    done_ids = {s["id"] for s in state["roadmap"] if s.get("done")}
    for s in steps:
        s["done"] = s["id"] in done_ids
    state["roadmap"] = steps
    memory.save(state)
    return {"steps": steps, "next_step": next((s for s in steps if not s["done"]), None)}


def update_step(step_id: str, done: bool) -> dict:
    state = memory.load()
    for s in state["roadmap"]:
        if s["id"] == step_id:
            s["done"] = done
            memory.save(state)
            return {"ok": True, "step": s}
    return {"ok": False, "error": f"로드맵에 없는 단계입니다: {step_id}"}
