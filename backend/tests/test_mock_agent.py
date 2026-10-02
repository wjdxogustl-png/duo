"""mock 모드로 시연 시나리오 전체를 키 없이 검증한다.

실행: (backend 폴더에서) python -m pytest -q tests/test_mock_agent.py
"""
import pytest

from app import agent, memory


@pytest.fixture(autouse=True)
def mock_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setattr(memory, "USERS_DIR", tmp_path / "users")
    monkeypatch.setattr(memory, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr("app.tools.document.OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr("app.tools.document.TEMPLATE_PATH", tmp_path / "tpl.docx")


def tools_of(r):
    return [c["tool"] for c in r["trace"]]


def test_vietnamese_scenario_end_to_end():
    u = "vi_demo"
    r = agent.run(u, "Tôi sống ở Gimhae, đến Hàn Quốc được 2 tháng, có con trai.")
    assert r["provider"] == "mock"
    assert tools_of(r) == ["save_profile"]
    p = r["state"]["profile"]
    assert (p["region"], p["months_in_korea"], p["has_children"], p["language"]) == ("김해", 2, True, "vi")
    assert "Tiếng Hàn" in r["reply"]  # 다음 빠진 항목(한국어 수준)을 베트남어로 되묻는다

    r = agent.run(u, "1")
    assert r["state"]["profile"]["korean_level"] == 1
    r = agent.run(u, "Tôi làm việc ở nhà máy.")
    assert r["state"]["profile"]["job_status"] == "employed"
    r = agent.run(u, "không")                    # 도와줄 사람 없음
    r = agent.run(u, "có, tôi bị nợ lương")       # 직장 어려움 있음
    r = agent.run(u, "chưa")                     # 지원사업 이용 경험 없음

    called = tools_of(r)
    assert "score_risk" in called and "build_roadmap" in called and "search_programs" in called
    assert r["state"]["roadmap"], "로드맵이 만들어져야 한다"
    assert "Lộ trình" in r["reply"] or "thứ tự" in r["reply"]
    assert "1345" in r["reply"]

    r = agent.run(u, "Thị thực của tôi hết hạn ngày 2027-01-01")
    assert tools_of(r) == ["set_dday_reminder"]
    assert r["state"]["dday"] == "2027-01-01"

    r = agent.run(u, "Làm đơn đăng ký lớp tiếng Hàn giúp tôi")
    assert "generate_application_doc" not in tools_of(r)   # 이름·연락처를 먼저 묻는다
    r = agent.run(u, "Tên tôi là Nguyen Van A, 010-1234-5678, buổi tối ngày thường")
    assert "generate_application_doc" in tools_of(r)
    assert r["files"] and r["files"][0].startswith("/api/files/")

    b = agent.briefing(u, "vi")
    assert b["trace"] == [] and "D-" in b["reply"]


def test_korean_first_message_with_everything():
    r = agent.run("ko_demo", "창원에 살고 한국에 온 지 1달 됐어요. 아이는 없고 공장에서 일해요. 한국어는 조금 해요. "
                             "도와줄 사람이 없어요. 직장 문제는 없어요. 지원사업은 처음 들어요.")
    called = tools_of(r)
    assert called[0] == "save_profile"
    assert {"score_risk", "build_roadmap", "search_programs"} <= set(called)
    assert "정착 안정도 점수" in r["reply"]


def test_step_done_updates_roadmap():
    u = "done_demo"
    agent.run(u, "김해 2개월 아이 없음 회사 다녀요 한국어 거의 못해요 도와줄 사람 있어요 직장 문제는 없어요 센터 이용해 봤어요")
    r = agent.run(u, "은행 계좌 만들었어요")
    assert "update_roadmap_step" in tools_of(r)
    assert any(s["id"] == "bank_phone" and s["done"] for s in r["state"]["roadmap"])
