"""액션 카드 검증: 지어낸 번호·주소는 버리고, 검증된 카드만 화면으로 넘기는지."""
import json

import pytest

from app.agent import actions_of
from app.mcp_server import _tool_list
from app.tools import actions, suggest_actions

PROGRAMS = [
    {"name": "김해 한국어 교실", "contact": "055-123-4567 (평일), 132", "source_url": "https://example.go.kr/a"},
    {"name": "주소 없는 사업", "contact": "기관 대표번호 기입", "source_url": ""},
]


@pytest.fixture(autouse=True)
def fake_db(monkeypatch):
    monkeypatch.setattr(actions, "load_programs", lambda: PROGRAMS)


def card(kind, **kw):
    return {"kind": kind, "label": kw.pop("label", "버튼"), "reason": "이유", **kw}


def test_keeps_valid_cards():
    r = actions.suggest_actions([
        card("say", message="신청서 만들어 주세요"),
        card("call", phone="1577-1366"),                 # 공식 창구 (하이픈 있어도 같은 번호)
        card("link", url="https://example.go.kr/a"),     # DB 의 source_url
    ])
    assert [a["kind"] for a in r["shown"]] == ["say", "call", "link"]
    assert r["dropped"] == []
    assert r["shown"][0] == {"kind": "say", "label": "버튼", "reason": "이유", "message": "신청서 만들어 주세요"}


def test_program_contact_number_is_allowed():
    assert actions.suggest_actions([card("call", phone="0551234567")])["shown"]
    assert actions.suggest_actions([card("call", phone="132")])["shown"]   # 세 자리 대표번호도


@pytest.mark.parametrize("bad", [
    card("call", phone="010-9999-9999"),          # 어디에도 없는 번호
    card("link", url="https://made-up.example"),  # DB 에 없는 주소
    card("link", url=""),                         # 빈 source_url 과 맞아떨어지면 안 된다
    card("say", message=" "),                     # 보낼 말 없음
    card("say", label="", message="안녕"),         # 버튼 글자 없음
])
def test_drops_unverified_cards(bad):
    r = actions.suggest_actions([bad])
    assert r["shown"] == [] and len(r["dropped"]) == 1


def test_at_most_three():
    r = actions.suggest_actions([card("say", label=str(i), message="m") for i in range(5)])
    assert [a["label"] for a in r["shown"]] == ["0", "1", "2"]
    assert len(r["dropped"]) == 2


def test_langchain_tool_accepts_dicts():
    out = json.loads(suggest_actions.invoke({"actions": [card("call", phone="129")]}))
    assert out["shown"][0]["phone"] == "129"


def test_mcp_schema_keeps_nested_defs():
    schema = next(t for t in _tool_list() if t["name"] == "suggest_actions")["inputSchema"]
    assert schema["properties"]["actions"]["items"]["$ref"] == "#/$defs/Action"
    assert "Action" in schema["$defs"]


def test_actions_of_uses_last_call():
    trace = [
        {"tool": "suggest_actions", "result": {"shown": [{"label": "old"}]}},
        {"tool": "search_programs", "result": {}},
        {"tool": "suggest_actions", "result": {"shown": [{"label": "new"}]}},
    ]
    assert actions_of(trace) == [{"label": "new"}]
    assert actions_of([{"tool": "save_profile", "result": {}}]) == []
