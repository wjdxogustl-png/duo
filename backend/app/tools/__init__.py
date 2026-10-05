"""LangChain 도구 등록. 에이전트는 이 목록에서 필요한 도구를 스스로 골라 호출한다.

각 도구의 실제 로직은 같은 폴더의 모듈에 있고, 여기서는 이름·설명·입력 스키마만 붙인다.
설명(description)은 모델이 도구를 고르는 기준이므로 구체적으로 쓴다.
"""
import json
from typing import Literal

from langchain_core.tools import StructuredTool, tool

from pydantic import BaseModel, Field

from . import dday, programs, risk, roadmap
from .draft import draft_application as _draft_application
from .actions import Action, suggest_actions as _suggest_actions
from .situation import SituationNote, note_situation as _note_situation
from .profile import ProfileUpdate, save_profile as _save_profile


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _with_pipeline(save):
    """기억을 바꾸는 도구 뒤에 변경 파이프라인(app/pipeline.py)을 붙인다. 결과의 pipeline 에 보고가 담긴다."""
    def run(**kw):
        from .. import memory, pipeline  # 순환 import 방지
        before = memory.load()
        result = save(kw)
        report = pipeline.after_change(before)
        if report:
            result["pipeline"] = report
        return _json(result)
    return run


PIPELINE_NOTE = (
    " 저장으로 바뀐 것이 있으면 결과의 pipeline 에 코드가 이미 다시 계산·검증한 내용"
    "(정착 안정도, 로드맵 추가·제외 단계, 검증된 지원사업)이 담긴다. "
    "같은 목적으로 score_risk · build_roadmap · search_programs 를 다시 부르지 말고, "
    "pipeline.summary 를 근거로 무엇이 왜 바뀌었는지 사용자에게 짧게 설명한다. "
    "verified 에 없는 사업은 안내하지 않는다."
)


save_profile = StructuredTool.from_function(
    func=_with_pipeline(_save_profile),
    name="save_profile",
    description=(
        "대화에서 알아낸 사용자 정보를 프로필에 저장한다. 새 정보를 알게 될 때마다 호출한다. "
        "결과의 missing_required 가 비어 있지 않으면 그 항목을 사용자에게 자연스럽게 되묻는다."
        + PIPELINE_NOTE
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
    """팀이 직접 조사한 경남 지원사업 DB를 검색한다. 인자를 모두 비우면 전체 목록을 돌려준다.
    category 값: 한국어교육, 법률상담, 노동상담, 자녀교육, 취업, 멘토링, 생활, 행정.
    로드맵 단계의 category 를 그대로 넣으면 해당 단계에 맞는 사업을 찾을 수 있다.
    결과의 address(주소), languages(상담·통역 언어 코드), schedule, cost 로 사용자 상황에 맞는지 판단한다.
    note 에 확인이 필요하다고 적힌 정보는 단정하지 말고, 방문 전에 전화로 확인하라고 함께 안내한다."""
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
def draft_application(program_id: str, preferred_time: str = "", motivation: str = "", requests: str = "") -> str:
    """사용자가 지원사업에 신청하고 싶어 하면, 그 사업의 신청서 초안을 만들어 화면에 보여 준다.
    program_id 는 search_programs 결과의 id. 이름·지역·거주 기간·한국어 수준은 프로필에서 자동으로 채운다.
    preferred_time·motivation·requests 는 사용자가 대화에서 말한 사실로만 짧게 쓴다 (한국어, 사용자 1인칭).
    모르는 내용은 지어내지 말고 비워 둔다. 사용자가 화면에서 직접 고치고 채운다.
    연락처는 채팅으로 묻지 않는다(화면에서 직접 입력). 외국인등록번호·여권번호·계좌번호는 묻지도 적지도 않는다.
    대신 제출하지 않는다. 결과의 empty_fields 는 사용자가 채울 칸이므로 답장에서 짧게 알려 준다."""
    return _json(_draft_application(program_id, preferred_time, motivation, requests))


note_situation = StructuredTool.from_function(
    func=_with_pipeline(_note_situation),
    name="note_situation",
    description=(
        "대화에서 추론한 사용자의 상황과 숨은 필요를 근거와 함께 기억한다. "
        "사용자가 직접 요청하지 않았어도, 말 속에 드러난 어려움·변화·계획이 있으면 호출한다 "
        "(예: '월세가 밀렸어요' → 생활비, '다음 주부터 야간 근무' + 어린 자녀 → 돌봄). "
        "need 는 하나만 고를 수 있으므로, 한 상황에 서로 다른 필요가 함께 드러나면 필요마다 따로 호출한다 "
        "(예: 혼자 사는데 다리를 다침 → 의료·건강 + 돌봄, 고용허가 노동자의 공장 폐업 → 일자리 + 행정·체류). "
        "특히 이전 말과 합쳐서 새로 보이는 숨은 필요는 겉으로 보이는 필요와 별도로 꼭 기록한다. "
        "사용자가 부정했거나 이미 해결됐다고 말한 필요는 기록하지 않는다. "
        "이미 기억한 상황이 바뀌었거나 해결됐으면 그 id 로 갱신한다. "
        "프로필 항목(지역·자녀 유무 등)은 save_profile 로, 그 밖의 상황은 이 도구로 저장한다."
        + PIPELINE_NOTE
    ),
    args_schema=SituationNote,
)


class ActionList(BaseModel):
    actions: list[Action] = Field(description="제안할 다음 행동 1~3개. 가장 중요한 것을 앞에")


suggest_actions = StructuredTool.from_function(
    func=lambda actions: _json(_suggest_actions([a.model_dump() if hasattr(a, "model_dump") else a for a in actions])),
    name="suggest_actions",
    description=(
        "사용자가 지금 바로 할 수 있는 다음 행동 1~3개를 화면에 버튼(액션 카드)으로 보여 준다. "
        "판단한 상황·로드맵·지원사업에서 실제로 도움이 될 행동이 보이면, 다른 도구를 다 부른 뒤 답장 글을 쓰기 전에 호출한다. "
        "사용자가 묻지 않았어도 곧 필요해질 행동을 먼저 내민다 (예: 신청서 초안 만들기, 체류 종료일 등록, 상담 창구 전화). "
        "되묻는 질문이 있어도 지금 할 수 있는 행동이 있으면 함께 제안하고, 할 수 있는 행동이 하나도 없을 때만 부르지 않는다. "
        "폭력·임금체불·생명 위험처럼 급한 상황이면 알맞은 공식 상담 창구의 call 카드를 맨 앞에 둔다. "
        "결과의 dropped 는 검증에서 빠진 카드이므로 답장에서 그 행동을 안내하지 않는다."
    ),
    args_schema=ActionList,
)


ALL_TOOLS = [
    save_profile,
    note_situation,
    build_roadmap,
    update_roadmap_step,
    search_programs,
    score_risk,
    set_dday_reminder,
    draft_application,
    suggest_actions,
]
