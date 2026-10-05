"""처음 보는 평가 사례(holdout)를 대량으로 만든다. 에이전트 프롬프트를 고친 뒤 그 효과가 원래 100문항에만
맞춘 것인지 확인하는 용도다.

공정성을 위해
- 문제를 만드는 모델은 에이전트 시스템 프롬프트와 기존 cases.jsonl 을 보지 않는다. 분류 정의(RUBRIC)만 본다.
- 만든 정답을 다른 호출이 문장만 보고 다시 매긴다(블라인드 재채점). 두 정답이 어긋나면 label_agree=false 로
  표시해 '정답 자체가 애매한 사례'로 따로 집계한다. 어긋난 사례를 지우거나 정답을 고치지 않는다.
- 이 세트의 결과를 보고 에이전트 프롬프트를 고치면 더 이상 holdout 이 아니다. 고쳤다면 새로 만들어 다시 잰다.

실행 (backend 폴더에서, 로그인한 Claude Code 구독 사용)
  python -m eval.generate_cases                      # 1000개 → eval/cases_holdout.jsonl
  python -m eval.generate_cases --scale 0.1          # 100개만 (빠른 확인)
  python -m eval.run_eval --mode both --cases cases_holdout.jsonl
"""
import argparse
import json
import random
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.claude_cli_llm import _cli_path, _extract_json, _run_cli

EVAL_DIR = Path(__file__).resolve().parent

NEEDS = ["생활비", "주거", "의료·건강", "돌봄", "일자리", "직장문제", "언어",
         "행정·체류", "자녀교육", "고립·정서", "안전", "기타"]

RUBRIC = """필요 분류 (사용자에게 실제로 필요한 도움의 종류. 한 사례에 여러 개일 수 있다)
- 생활비: 돈이 부족함, 생계·공과금·송금 어려움
- 주거: 살 곳, 집 상태, 이사, 집주인 문제
- 의료·건강: 아프거나 다침, 임신, 약, 건강보험, 정신건강 치료
- 돌봄: 아이·환자·노인·본인을 돌봐 줄 사람이나 맡길 곳이 없음
- 일자리: 일을 잃었거나 잃게 됨, 새 일을 구해야 함
- 직장문제: 지금 직장 안의 문제 (임금체불, 부당대우, 과로, 계약 위반, 산재 처리)
- 언어: 한국어가 부족해서 해야 할 일을 못 하거나 배우고 싶음
- 행정·체류: 비자·체류 자격·체류 기간·외국인등록, 체류 조건과 얽힌 이직·근무, 은행·휴대폰 개통 등 행정 절차
- 자녀교육: 자녀의 학교·학습·진학
- 고립·정서: 외로움, 우울, 고향 가족과의 이별로 인한 마음 고생
- 안전: 폭력, 학대, 사기, 위협, 착취
- 기타: 위에 없지만 도움이 필요한 것 (운전면허, 교통 등)"""

# 유형 → (배치 수, 언어, 만드는 규칙). 배치 하나에 BATCH 개.
BATCH = 25
PLAN = {
    "간접표현": (16, ["ko"], "사용자가 도움이 필요하다고 직접 말하지 않고 상황만 말한다. 한 번의 말(history 없음). "
                         "expected 는 그 말에서 드러나는 실제 필요 1~2개. not_needs 는 []."),
    "여러턴결합": (8, ["ko"], "history 에 사용자가 앞서 한 말 1~3개(배경 정보), message 에 지금 말. 지금 말만 보면 "
                          "드러나지 않거나 다른 필요로 보이지만, 앞의 말과 합치면 실제 필요가 보이는 사례. "
                          "expected 는 합쳐야 보이는 필요를 반드시 포함. not_needs 는 []."),
    "함정·부정": (8, ["ko"], "필요처럼 보이는 주제를 말하지만 부정·해결됨·농담·반어라서 그 필요는 아닌 사례. "
                         "not_needs 는 그렇게 아닌 필요(1개 이상). expected 는 실제 필요가 있으면 그것, 없으면 []."),
    "다국어": (4, ["en", "vi", "zh", "ja"], "한국어가 아닌 언어로 된 간접 표현. 한 번의 말(history 없음). "
                                          "expected 는 실제 필요 1~2개. not_needs 는 []."),
    "필요없음": (4, ["ko"], "인사, 감사, 잡담, 좋은 소식, 단순 정보 질문처럼 아무 지원도 필요 없는 말. "
                          "expected 는 [], not_needs 는 [\"*\"]."),
}

PERSONA = {
    "from": ["베트남", "필리핀", "캄보디아", "네팔", "우즈베키스탄", "중국", "몽골", "인도네시아", "태국", "미얀마",
             "스리랑카", "일본", "방글라데시", "카자흐스탄"],
    "who": ["고용허가 노동자", "결혼이민자", "유학생", "외국인 계절근로자", "방문취업 동포", "난민 신청자",
            "전문직 취업자", "중도입국 청소년의 부모", "한국인과 이혼한 결혼이민자", "선원(어업)"],
    "where": ["창원", "김해", "진주", "양산", "거제", "통영", "사천", "밀양", "함안", "거창", "창녕", "고성",
              "남해", "하동", "산청", "함양", "합천", "의령"],
    "work": ["조선소", "자동차 부품 공장", "농장", "양식장", "식당", "물류센터", "건설 현장", "요양원", "편의점",
             "가정주부", "대학 연구실", "어선", "비닐하우스", "숙박업소"],
    "family": ["혼자 삶", "배우자와 삶", "어린 자녀가 있음", "고향에 가족을 둠", "시부모와 삶", "임신 중",
               "초등학생 자녀", "한부모"],
}

GEN_SYSTEM = """너는 이주민 지원 AI의 평가용 문장을 만드는 연구 보조다. 실제 경남 거주 이주민이 상담 채팅에 쓸 법한
자연스럽고 구체적인 문장을 만든다. 표현·상황·말투를 다양하게 하고, 같은 패턴을 반복하지 않는다.
정답은 아래 분류 정의에 따라 정직하게 매긴다. 애매하면 사람 상담사 다수가 동의할 정답을 고른다.

""" + RUBRIC + """

출력은 JSON 배열 하나만. 각 원소: {"history": [문자열...], "message": 문자열, "expected": [분류...], "not_needs": [분류...]}
분류 이름은 위 목록의 철자 그대로 쓴다."""

LABEL_SYSTEM = """너는 이주민 상담 문장을 분류하는 평가자다. 각 사례에서 사용자의 말(history 는 앞서 한 말,
message 는 지금 말)을 읽고, 사용자에게 실제로 필요한 도움을 분류한다.
- needs: 실제 필요 (없으면 [])
- denied: 말에 언급됐지만 부정·해결됨·농담이라 필요가 아닌 것 (없으면 [])

""" + RUBRIC + """

출력은 JSON 배열 하나만. 입력 순서대로 {"i": 번호, "needs": [...], "denied": [...]}."""


def _call(system: str, prompt: str, model: str) -> list | None:
    for _ in range(3):  # 형식이 깨지면 다시 시도
        try:
            text = _run_cli(_cli_path(), model, system, prompt, 900)
        except Exception as e:  # noqa: BLE001
            print("  호출 실패:", str(e)[:120], flush=True)
            continue
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except ValueError:
                pass
        data = _extract_json(text)
        if isinstance(data, list):
            return data
    return None


def _valid(c: dict) -> bool:
    if not isinstance(c, dict) or not isinstance(c.get("message"), str) or not c["message"].strip():
        return False
    if not isinstance(c.get("history", []), list):
        return False
    ok = set(NEEDS) | {"*"}
    return set(c.get("expected", [])) <= ok and set(c.get("not_needs", [])) <= ok


def generate_batch(cat: str, lang: str, rule: str, seed: int, model: str) -> list[dict]:
    rnd = random.Random(seed)
    personas = ["; ".join(rnd.choice(v) for v in PERSONA.values()) for _ in range(BATCH)]
    prompt = (
        f"유형: {cat}\n규칙: {rule}\n언어: {lang} (message 와 history 를 이 언어로 쓴다)\n"
        f"사례 {BATCH}개를 만든다. 아래 인물 설정을 하나씩 참고해 상황을 다양하게 한다 (설정을 문장에 그대로 나열하지 않는다).\n"
        + "\n".join(f"{i + 1}. {p}" for i, p in enumerate(personas))
    )
    out = _call(GEN_SYSTEM, prompt, model) or []
    return [{"cat": cat, "lang": lang, "history": c.get("history", []), "message": c["message"].strip(),
             "expected": c.get("expected", []), "not_needs": c.get("not_needs", [])}
            for c in out if _valid(c)]


def relabel(cases: list[dict], model: str) -> list[dict | None]:
    prompt = "\n".join(json.dumps({"i": i, "history": c["history"], "message": c["message"]}, ensure_ascii=False)
                       for i, c in enumerate(cases))
    out = _call(LABEL_SYSTEM, prompt, model) or []
    by_i = {r.get("i"): r for r in out if isinstance(r, dict)}
    return [by_i.get(i) for i in range(len(cases))]


def agrees(case: dict, label: dict | None) -> bool:
    """만든 정답과 블라인드 재채점이 같은 결론인지 (run_eval.is_correct 와 같은 기준)."""
    if not label:
        return False
    needs = set(label.get("needs") or [])
    expected, traps = set(case["expected"]), set(case["not_needs"])
    if "*" in traps:
        return not needs
    if needs & traps:
        return False
    return bool(needs & expected) if expected else True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scale", type=float, default=1.0, help="배치 수 배율 (1.0 = 약 1000개)")
    p.add_argument("--model", default="opus", help="문제 생성·재채점 모델 (에이전트와 다른 모델 권장)")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out", default="cases_holdout.jsonl")
    args = p.parse_args()

    jobs = []
    for cat, (n, langs, rule) in PLAN.items():
        for b in range(max(1, round(n * args.scale))):
            jobs.append((cat, langs[b % len(langs)], rule, zlib.crc32(f"{cat}-{b}".encode())))
    print(f"생성 배치 {len(jobs)}개 × {BATCH}", flush=True)

    with ThreadPoolExecutor(args.workers) as pool:
        batches = list(pool.map(lambda j: generate_batch(*j, args.model), jobs))
    for (cat, lang, *_), b in zip(jobs, batches):
        print(f"  {cat} {lang}: {len(b)}개", flush=True)

    existing = {json.loads(line)["message"] for line in (EVAL_DIR / "cases.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()}
    seen, cases = set(existing), []
    for b in batches:
        for c in b:
            if c["message"] not in seen:
                seen.add(c["message"])
                cases.append(c)
    print(f"중복 제거 후 {len(cases)}개. 블라인드 재채점 중…", flush=True)

    chunks = [cases[i:i + BATCH] for i in range(0, len(cases), BATCH)]
    with ThreadPoolExecutor(args.workers) as pool:
        labels = [x for chunk in pool.map(lambda ch: relabel(ch, args.model), chunks) for x in chunk]

    counters: dict[str, int] = {}
    for c, lab in zip(cases, labels):
        prefix = "H" + "ABCDE"[list(PLAN).index(c["cat"])]
        counters[prefix] = counters.get(prefix, 0) + 1
        c["id"] = f"{prefix}{counters[prefix]:03d}"
        c["relabel"] = lab
        c["label_agree"] = agrees(c, lab)

    out = EVAL_DIR / args.out
    out.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in cases) + "\n", encoding="utf-8")
    agree = sum(c["label_agree"] for c in cases)
    print(f"저장: {out} ({len(cases)}개, 정답 일치 {agree}개 / 애매 {len(cases) - agree}개)", flush=True)


if __name__ == "__main__":
    main()
