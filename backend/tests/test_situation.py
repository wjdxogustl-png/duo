"""상황 기억: 저장·갱신과, 다음 턴 프롬프트·재방문 브리핑에 다시 들어가는지 확인한다."""
import json

import pytest

from app import agent, memory
from app.tools import note_situation


@pytest.fixture(autouse=True)
def tmp_users(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "USERS_DIR", tmp_path / "users")
    memory.current_user.set("sit")


def call(**kw):
    return json.loads(note_situation.invoke(kw))


def test_create_then_update_by_id():
    r = call(need="돌봄", understanding="야간 근무로 바뀌어 6살 자녀를 밤에 맡길 곳이 없을 수 있음",
             evidence="다음 주부터 야간 근무예요", confidence="추정", urgency="높음")
    sid = r["saved"]["id"]
    assert len(r["open_situations"]) == 1

    r = call(id=sid, need="돌봄", understanding="이웃이 밤에 아이를 봐 주기로 함",
             evidence="옆집에서 봐 준대요", confidence="확인됨", urgency="낮음", status="해결됨")
    state = memory.load()
    assert len(state["situations"]) == 1                 # 새로 만들지 않고 갱신
    assert state["situations"][0]["status"] == "해결됨"
    assert r["open_situations"] == []


def test_context_and_briefing_include_situations():
    memory.save({**memory.empty_state(), "profile": {"region": "김해"}})
    call(need="생활비", understanding="월세가 밀려 생활비가 부족함", evidence="이번 달 월세가 밀렸어요",
         confidence="확인됨", urgency="높음", follow_up="긴급 생계지원 상담(129) 연락했는지 확인")
    ctx = agent.context_block(memory.load())
    assert "월세가 밀려" in ctx and "129" in ctx          # 다음 턴 프롬프트에 근거와 할 일이 들어간다

    facts = agent.briefing_facts("sit")
    assert facts["open_situations"][0]["need"] == "생활비"


def test_briefing_with_situation_only():
    call(need="고립·정서", understanding="주변에 아는 사람이 없어 외로움", evidence="여기 아는 사람이 없어요",
         confidence="확인됨", urgency="보통")
    assert agent.briefing_facts("sit") is not None        # 프로필이 없어도 기억한 상황이 있으면 먼저 말을 건다
