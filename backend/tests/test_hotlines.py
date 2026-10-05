"""공식 상담 창구(data/hotlines.json): 출처가 있는 번호만 쓰고, call 카드 검증과 프롬프트가 같은 목록을 읽는지."""
import re

import pytest
from fastapi.testclient import TestClient

from app import agent
from app.main import app
from app.tools import actions
from app.tools.hotlines import load_hotlines, prompt_lines

FIELDS = {"number", "name", "languages", "hours", "when", "source_url", "checked_at"}


def test_every_hotline_has_source_and_date():
    hotlines = load_hotlines()
    assert {"112", "119", "1366", "1577-1366", "1345", "1350", "1644-0644", "129"} <= {h["number"] for h in hotlines}
    for h in hotlines:
        assert FIELDS <= set(h), h["number"]
        assert h["source_url"].startswith("https://"), h["number"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", h["checked_at"]), h["number"]
        assert h["languages"] and h["when"].strip()


@pytest.fixture
def no_programs(monkeypatch):
    monkeypatch.setattr(actions, "load_programs", lambda: [])
    monkeypatch.setattr(actions, "_chosen_call", lambda: "")


@pytest.mark.parametrize("phone", ["112", "119", "1366", "1577-1366", "15771366", "1345", "1350", "1644-0644", "129"])
def test_hotline_numbers_allowed_as_call(no_programs, phone):
    r = actions.suggest_actions([{"kind": "call", "label": "전화", "reason": "이유", "phone": phone}])
    assert r["shown"] and not r["dropped"]


@pytest.mark.parametrize("phone", ["1577-0000", "1588-1366", "113", "010-1234-5678"])
def test_unknown_numbers_rejected(no_programs, phone):
    r = actions.suggest_actions([{"kind": "call", "label": "전화", "reason": "이유", "phone": phone}])
    assert r["shown"] == [] and r["dropped"][0]["why"] == "공식 창구·DB 에 없는 번호"


def test_system_prompt_lists_every_hotline():
    prompt = agent.SYSTEM_PROMPT.format(today="2026-10-05", language="한국어", context="", hotlines=prompt_lines())
    for h in load_hotlines():
        assert h["number"] in prompt
    assert "112·119 를 가장 먼저" in prompt


def test_hotlines_api():
    assert TestClient(app).get("/api/hotlines").json() == load_hotlines()
