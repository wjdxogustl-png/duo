"""상황 기억: 에이전트가 대화에서 추론한 '사용자의 상황과 숨은 필요'를 근거와 함께 저장한다.

판단(무엇이 필요한지, 얼마나 급한지, 과거 상황과 어떻게 이어지는지)은 LLM이 하고,
이 코드는 그 판단을 시각과 함께 기록·갱신만 한다. 키워드 규칙은 없다.
다음 대화와 재방문 브리핑 때 이 기록이 다시 에이전트에게 주어져 맥락이 이어진다.
"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .. import memory

MAX_SITUATIONS = 30

NeedType = Literal[
    "생활비", "주거", "의료·건강", "돌봄", "일자리", "직장문제", "언어",
    "행정·체류", "자녀교육", "고립·정서", "안전", "기타",
]


class SituationNote(BaseModel):
    """에이전트가 이해한 상황 하나. 새 상황이면 id 를 비우고, 기존 상황을 고치면 id 를 넣는다."""

    id: str | None = Field(None, description="기존 상황을 갱신·해결할 때 그 상황의 id. 새 상황이면 비운다")
    need: NeedType = Field(description=(
        "이 상황에서 드러난 필요의 종류. 겉으로 보이는 주제가 아니라 실제로 도와야 할 문제로 고른다. "
        "행정·체류: 비자·체류 자격·체류 기간, 직장 변경·폐업·근무 시간이 체류 조건에 걸리는 경우, 외국인등록·통장·휴대폰 개통 / "
        "돌봄: 아이·환자·본인을 돌봐 줄 사람이 없거나 사라지는 경우 / "
        "언어: 한국어가 부족해 상담·학교·병원 등 해야 할 일을 못 하게 되는 경우 / "
        "직장문제: 임금체불·부당대우 등 지금 직장 안의 문제 / 일자리: 일을 잃거나 새로 구해야 함"
    ))
    understanding: str = Field(description="에이전트가 이해한 상황과 숨은 필요 (사용자 말의 해석, 1~2문장, 응답 언어로)")
    evidence: str = Field(description="그렇게 판단한 근거가 된 사용자의 말 (원문 그대로 짧게 인용)")
    confidence: Literal["확인됨", "추정"] = Field(description="사용자가 직접 확인했으면 확인됨, 추론만 했으면 추정")
    urgency: Literal["높음", "보통", "낮음"] = Field(description="지금 얼마나 급한지")
    status: Literal["열림", "해결됨"] = Field("열림", description="해결됐다고 판단되면 해결됨")
    follow_up: str | None = Field(None, description="다음 대화·재방문 때 먼저 확인하거나 미리 알려 줄 것")


def note_situation(note: dict) -> dict:
    state = memory.load()
    situations = state.setdefault("situations", [])
    now = datetime.now().isoformat(timespec="seconds")
    data = {k: v for k, v in note.items() if k != "id" and v is not None}

    target = next((s for s in situations if note.get("id") and s["id"] == note["id"]), None)
    if target:
        target.update(data, updated_at=now)
    else:
        target = {"id": uuid.uuid4().hex[:6], **data, "created_at": now, "updated_at": now}
        situations.append(target)
    state["situations"] = situations[-MAX_SITUATIONS:]
    memory.save(state)
    return {
        "saved": target,
        "open_situations": [s for s in state["situations"] if s.get("status") != "해결됨"],
    }
