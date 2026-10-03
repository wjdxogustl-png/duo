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
