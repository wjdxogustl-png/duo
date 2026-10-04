"""평가 세트 형식과 채점 규칙 (LLM 호출 없음)."""
from typing import get_args

from app.tools.situation import NeedType
from eval.keyword_baseline import KEYWORDS, predict
from eval.run_eval import is_correct, load_cases

NEEDS = set(get_args(NeedType))


def test_cases_are_well_formed():
    cases = load_cases()
    assert len(cases) == 100
    assert len({c["id"] for c in cases}) == 100
    for c in cases:
        assert set(c["expected"]) <= NEEDS, c["id"]
        assert set(c["not_needs"]) <= NEEDS | {"*"}, c["id"]
        assert not set(c["expected"]) & set(c["not_needs"]), c["id"]
    assert set(KEYWORDS) <= NEEDS


def test_scoring_rules():
    case = {"expected": ["생활비", "주거"], "not_needs": []}
    assert is_correct(case, {"생활비"})            # 정답 중 하나만 찾아도 맞음
    assert not is_correct(case, set())

    trap = {"expected": [], "not_needs": ["생활비"]}
    assert is_correct(trap, set())
    assert is_correct(trap, {"돌봄"})
    assert not is_correct(trap, {"생활비"})        # 함정을 고르면 틀림

    nothing = {"expected": [], "not_needs": ["*"]}
    assert is_correct(nothing, set())
    assert not is_correct(nothing, {"기타"})       # 필요 없는 대화에 아무것도 고르지 않아야 맞음


def test_keyword_baseline_falls_for_negation():
    assert "생활비" in predict("돈 걱정은 없어요. 그냥 시간이 너무 없네요.")


def test_stops_on_usage_limit_and_resumes(tmp_path, monkeypatch):
    """사용량 한도에 걸리면 채점하지 않고 멈추고, 다시 실행하면 끝난 사례는 건너뛴다."""
    import json
    import sys

    import pytest

    from eval import run_eval

    (tmp_path / "cases.jsonl").write_text("\n".join(json.dumps(
        {"id": f"T{i}", "cat": "간접표현", "lang": "ko", "history": [], "message": f"m{i}",
         "expected": ["생활비"], "not_needs": []}) for i in range(4)), encoding="utf-8")
    monkeypatch.setattr(run_eval, "EVAL_DIR", tmp_path)
    monkeypatch.setattr(sys, "argv", ["run_eval", "--mode", "agent", "--workers", "1"])
    calls = []

    def limited(case, run_id):
        calls.append(case["id"])
        if case["id"] == "T2":
            return {"predicted": [], "error": "RuntimeError: claude CLI 오류: Claude AI usage limit reached", "seconds": 0}
        return {"predicted": ["생활비"], "seconds": 0}

    monkeypatch.setattr(run_eval, "run_agent", limited)
    with pytest.raises(SystemExit) as e:
        run_eval.main()
    assert e.value.code == 2
    progress = next((tmp_path / "results").glob("_progress_*.jsonl"))
    assert len(progress.read_text(encoding="utf-8").splitlines()) == 2   # T0, T1 만 저장 (T2 는 채점 안 함)
    assert "T3" not in calls                                              # 한도 뒤로는 돌리지 않는다

    calls.clear()
    monkeypatch.setattr(run_eval, "run_agent", lambda c, r: calls.append(c["id"]) or {"predicted": ["생활비"], "seconds": 0})
    run_eval.main()
    assert calls == ["T2", "T3"]                                          # 남은 것만 이어서
    assert not progress.exists()
    report = next((tmp_path / "results").glob("*.md")).read_text(encoding="utf-8")
    assert "4/4 (100%)" in report
