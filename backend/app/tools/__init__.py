"""LangChain 도구 등록. 에이전트는 이 목록에서 필요한 도구를 스스로 골라 호출한다.

각 도구의 실제 로직은 같은 폴더의 모듈에 있고, 여기서는 이름·설명·입력 스키마만 붙인다.
설명(description)은 모델이 도구를 고르는 기준이므로 구체적으로 쓴다.
"""
import json
from typing import Literal

from langchain_core.tools import StructuredTool, tool

from . import dday, document, programs, risk, roadmap
from .profile import ProfileUpdate, save_profile as _save_profile


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


save_profile = StructuredTool.from_function(
    func=lambda **kw: _json(_save_profile(kw)),
    name="save_profile",
    description=(
        "대화에서 알아낸 사용자 정보를 프로필에 저장한다. 새 정보를 알게 될 때마다 호출한다. "
        "결과의 missing_required 가 비어 있지 않으면 그 항목을 사용자에게 자연스럽게 되묻는다."
    ),
    args_schema=ProfileUpdate,
)


@tool
def build_roadmap() -> str:
    """저장된 프로필을 바탕으로 정착 로드맵(해야 할 일 순서)을 만든다. 프로필 필수 항목이 채워진 뒤 호출한다."""
    return _json(roadmap.build_roadmap())


@tool
def update_roadmap_step(step_id: str, done: bool) -> str:
    """사용자가 로드맵의 한 단계를 마쳤다고 말하면 해당 단계의 완료 여부를 기록한다."""
    return _json(roadmap.update_step(step_id, done))


@tool
def search_programs(
    region: str | None = None,
    category: Literal["한국어교육", "법률상담", "노동상담", "자녀교육", "취업", "멘토링", "생활", "행정"] | None = None,
    keyword: str | None = None,
) -> str:
    """팀이 직접 조사한 경남 지원사업 DB를 검색한다.
    category 값: 한국어교육, 법률상담, 노동상담, 자녀교육, 취업, 멘토링, 생활, 행정.
    로드맵 단계의 category 를 그대로 넣으면 해당 단계에 맞는 사업을 찾을 수 있다."""
    return _json(programs.search_programs(region, category, keyword))


@tool
def score_risk() -> str:
    """팀 채점 기준으로 정착 안정도 점수를 계산한다. recommend_mentoring_first 가 true 면
    다른 안내보다 멘토·상담 연계를 먼저 제안한다.
    결과의 missing 이 비어 있지 않으면(complete=false) 판정하지 않은 것이다. 그 항목을 먼저 쉽게 되묻고,
    save_profile 로 저장한 뒤 다시 score_risk 를 호출한다."""
    return _json(risk.score_risk())


@tool
def set_dday_reminder(end_date: str) -> str:
    """사용자가 직접 말한 체류 예정 종료일(YYYY-MM-DD)을 저장하고 D-day를 계산한다.
    연장 가능 여부 같은 법적 판단은 하지 않는다."""
    return _json(dday.set_dday_reminder(end_date))


@tool
def generate_application_doc(name: str, phone: str, institution: str, preferred_time: str) -> str:
    """한국어교육 신청서 초안(docx)을 만든다. 이름·연락처·희망 기관·희망 시간대를 모두 확인한 뒤 호출한다.
    결과의 download_url 을 사용자에게 알려 주고, 직접 제출해야 한다고 안내한다."""
    return _json(document.generate_application_doc(name, phone, institution, preferred_time))


ALL_TOOLS = [
    save_profile,
    build_roadmap,
    update_roadmap_step,
    search_programs,
    score_risk,
    set_dday_reminder,
    generate_application_doc,
]
