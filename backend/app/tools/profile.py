"""온보딩 프로필 정의와 저장."""
from typing import Literal

from pydantic import BaseModel, Field

from .. import memory


class ProfileUpdate(BaseModel):
    """대화에서 알아낸 항목만 채운다. 모르는 항목은 비워 둔다."""

    name: str | None = Field(None, description="사용자 이름(신청서 작성용)")
    language: Literal["ko", "en", "vi", "ja", "zh"] | None = Field(None, description="사용자가 편한 언어")
    region: str | None = Field(None, description="거주 시·군. 예: 창원, 김해, 진주")
    months_in_korea: int | None = Field(None, ge=0, description="한국 입국 후 경과 개월 수")
    has_spouse: bool | None = Field(None, description="배우자와 함께 거주하는지")
    has_children: bool | None = Field(None, description="자녀가 있는지")
    job_status: Literal["employed", "seeking", "student", "other"] | None = None
    korean_level: int | None = Field(None, ge=0, le=3, description="0=거의 못함, 1=기초, 2=일상대화, 3=능숙")
    has_local_support: bool | None = Field(None, description="주변에 도움을 청할 사람이 있는지")
    workplace_issue: bool | None = Field(None, description="직장에서 차별·갈등 등 어려움이 있는지")
    knows_support_programs: bool | None = Field(None, description="지자체 지원사업을 알고 이용해 본 적이 있는지")


# 로드맵·위험도 계산에 꼭 필요한 항목
REQUIRED_FIELDS = ["region", "months_in_korea", "korean_level", "has_children", "job_status"]


def save_profile(update: dict) -> dict:
    state = memory.load()
    clean = {k: v for k, v in update.items() if v is not None}
    state["profile"].update(clean)
    memory.save(state)
    missing = [f for f in REQUIRED_FIELDS if f not in state["profile"]]
    return {"profile": state["profile"], "missing_required": missing}
