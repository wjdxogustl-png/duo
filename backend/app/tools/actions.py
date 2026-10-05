"""액션 카드: 에이전트가 판단한 '사용자가 바로 할 수 있는 다음 행동'을 화면 버튼으로 내민다.

무엇을 제안할지는 LLM이 정하고, 이 코드는 카드가 엉뚱한 곳으로 연결되지 않게 검증만 한다.
- say  : 누르면 message 가 사용자의 말로 전송된다 (실제 실행은 다음 턴에 에이전트가 도구로 한다)
- call : 공식 상담 창구(data/hotlines.json)나 DB 에 있는 연락처로만 전화 연결
- link : DB 에 있는 지원사업 출처(source_url)로만 연결
기억(Memory)은 바꾸지 않는다. 화면에 보여 줄 카드만 돌려준다.
"""
import re
from typing import Literal

from pydantic import BaseModel, Field

from .hotlines import load_hotlines
from .programs import load_programs

MAX_ACTIONS = 3


class Action(BaseModel):
    """화면에 버튼으로 보여 줄 다음 행동 하나."""

    kind: Literal["say", "call", "link"] = Field(description=(
        "say: 누르면 message 가 사용자의 말로 전송됨 (신청서 만들기, D-day 등록, 사업 자세히 보기 등 에이전트가 할 일) / "
        "call: phone 으로 전화 연결 / link: url 을 새 창으로 열기"
    ))
    label: str = Field(description="버튼 글자. 응답 언어로 짧게 (예: 신청서 초안 만들기)")
    reason: str = Field(description="왜 이 행동을 권하는지. 사용자 상황과 이어서 응답 언어로 한 문장")
    message: str | None = Field(None, description="kind=say 일 때 사용자가 보낸 것처럼 전송할 문장 (응답 언어, 사용자 말투)")
    phone: str | None = Field(None, description="kind=call 일 때 번호. 공식 상담 창구 또는 지원사업 contact 에 있는 번호만")
    url: str | None = Field(None, description="kind=link 일 때 주소. search_programs 결과의 source_url 만")


def _digits(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


def _known_phones() -> set[str]:
    phones = {_digits(h["number"]) for h in load_hotlines()}
    for p in load_programs():
        for num in re.findall(r"\d[\d-]{1,}\d", p.get("contact") or ""):
            phones.add(_digits(num))
    return phones


def _check(a: dict, phones: set[str], urls: set[str]) -> str | None:
    """카드가 쓸 수 없으면 이유를, 쓸 수 있으면 None 을 돌려준다(순수 함수)."""
    if not (a.get("label") or "").strip():
        return "label 없음"
    if a["kind"] == "say" and not (a.get("message") or "").strip():
        return "say 인데 message 없음"
    if a["kind"] == "call" and _digits(a.get("phone")) not in phones:
        return "공식 창구·DB 에 없는 번호"
    if a["kind"] == "link" and (a.get("url") or "") not in urls:
        return "DB 에 없는 주소"
    return None


def suggest_actions(actions: list[dict]) -> dict:
    phones = _known_phones()
    urls = {p["source_url"] for p in load_programs() if p.get("source_url")}
    shown, dropped = [], []
    for a in actions:
        reason = _check(a, phones, urls)
        if reason:
            dropped.append({"label": a.get("label"), "why": reason})
        elif len(shown) >= MAX_ACTIONS:
            dropped.append({"label": a.get("label"), "why": f"최대 {MAX_ACTIONS}개"})
        else:
            keep = {"say": "message", "call": "phone", "link": "url"}[a["kind"]]
            shown.append({k: a[k] for k in ("kind", "label", "reason", keep)})
    return {"shown": shown, "dropped": dropped}
