"""간접 표현 평가: 키워드 방식 vs 맥락 추론 에이전트.

실행 (backend 폴더에서)
  python -m eval.run_eval --mode keyword          # 키워드 방식만 (LLM 호출 없음, 즉시)
  python -m eval.run_eval --mode both             # 둘 다. 에이전트는 .env 의 LLM_PROVIDER 로 실행
  python -m eval.run_eval --mode both --limit 10  # 앞의 10개만
  python -m eval.run_eval --mode agent --cat 여러턴결합  # 한 유형만
결과는 eval/results/ 에 JSON(전체 기록)과 Markdown(완료보고서용 표)으로 저장된다.

채점: 에이전트가 이번 턴에 기억한 '열린 상황'의 필요 종류(note_situation)를 정답과 비교한다.
  - 정답(expected)이 있으면: 정답 중 하나 이상을 찾고, 함정(not_needs)은 하나도 고르지 않아야 맞음
  - 정답이 없으면: 함정을 고르지 않아야 맞음. not_needs 가 ["*"] 이면 아무 필요도 고르지 않아야 맞음
"""
import argparse
import json
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

EVAL_DIR = Path(__file__).resolve().parent
ACK = "네, 알겠어요."  # 여러 턴 사례에서 이전 턴의 에이전트 답장 자리 (내용으로 힌트를 주지 않는다)


def load_cases(limit: int | None = None, cats: list[str] | None = None) -> list[dict]:
    lines = (EVAL_DIR / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]
    if cats:
        cases = [c for c in cases if c["cat"] in cats]
    return cases[:limit] if limit else cases


def is_correct(case: dict, predicted: set[str]) -> bool:
    expected, traps = set(case["expected"]), set(case["not_needs"])
    if "*" in traps:
        return not predicted
    if predicted & traps:
        return False
    return bool(predicted & expected) if expected else True


def run_keyword(case: dict) -> dict:
    from .keyword_baseline import predict
    text = " ".join(case["history"] + [case["message"]])
    return {"predicted": sorted(predict(text))}


def run_agent(case: dict, run_id: str) -> dict:
    from app import agent, memory
    uid = f"eval_{run_id}_{case['id']}"
    history = []
    for h in case["history"]:
        history += [{"role": "user", "content": h}, {"role": "assistant", "content": ACK}]
    memory.save({**memory.empty_state(), "history": history}, uid)
    started = time.perf_counter()
    try:
        r = agent.run(uid, case["message"], case["lang"])
        situations = memory.load(uid).get("situations") or []
        predicted = {s["need"] for s in situations if s.get("status") != "해결됨"}
        return {
            "predicted": sorted(predicted),
            "situations": [{k: s.get(k) for k in ("need", "understanding", "evidence", "confidence", "urgency")}
                           for s in situations],
            "tools": [c["tool"] for c in r["trace"]],
            "reply": r["reply"],
            "seconds": round(time.perf_counter() - started, 1),
        }
    except Exception as e:  # noqa: BLE001  한 사례가 실패해도 나머지는 계속한다
        return {"predicted": [], "error": f"{type(e).__name__}: {e}", "seconds": round(time.perf_counter() - started, 1)}
    finally:
        memory.reset(uid)


def summarize(cases: list[dict], results: dict[str, list[dict]]) -> dict:
    summary = {}
    for method, rows in results.items():
        by_cat = defaultdict(lambda: [0, 0])
        for case, row in zip(cases, rows):
            ok = is_correct(case, set(row["predicted"]))
            row["correct"] = ok
            by_cat[case["cat"]][0] += ok
            by_cat[case["cat"]][1] += 1
        total = sum(v[0] for v in by_cat.values())
        summary[method] = {"total": [total, len(rows)], "by_cat": dict(by_cat)}
    return summary


def write_report(cases, results, summary, meta) -> Path:
    out = EVAL_DIR / "results"
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (out / f"{stamp}.json").write_text(json.dumps(
        {"meta": meta, "summary": summary, "cases": cases, "results": results}, ensure_ascii=False, indent=1,
    ), encoding="utf-8")

    methods = list(results)
    names = {"keyword": "키워드 방식", "agent": f"에이전트 ({meta.get('provider')})"}
    cats = list(dict.fromkeys(c["cat"] for c in cases))
    pct = lambda a, b: f"{a}/{b} ({a / b:.0%})" if b else "-"  # noqa: E731
    lines = [
        f"# 간접 표현 평가 결과 ({meta['started']})", "",
        f"- 사례 {len(cases)}개 · 방법: {', '.join(names[m] for m in methods)}",
        "- 채점: 정답 필요를 하나 이상 찾고 함정 필요는 고르지 않으면 정답. '필요없음'은 아무것도 고르지 않아야 정답", "",
        "| 유형 | " + " | ".join(names[m] for m in methods) + " |",
        "|---|" + "---|" * len(methods),
    ]
    for cat in cats:
        lines.append(f"| {cat} | " + " | ".join(pct(*summary[m]["by_cat"].get(cat, [0, 0])) for m in methods) + " |")
    lines.append("| **전체** | " + " | ".join(f"**{pct(*summary[m]['total'])}**" for m in methods) + " |")
    if "agent" in results:
        secs = [r["seconds"] for r in results["agent"] if "seconds" in r]
        errors = [r for r in results["agent"] if r.get("error")]
        lines += ["", f"- 에이전트 평균 응답 {sum(secs) / len(secs):.1f}초 · 오류 {len(errors)}건"]

    lines += ["", "## 틀린 사례", ""]
    for m in methods:
        lines += [f"### {names[m]}", ""]
        wrong = [(c, r) for c, r in zip(cases, results[m]) if not r["correct"]]
        if not wrong:
            lines += ["(없음)", ""]
            continue
        lines += ["| id | 문장 | 정답 | 함정 | 판단 |", "|---|---|---|---|---|"]
        for c, r in wrong:
            msg = (" / ".join(c["history"]) + " → " if c["history"] else "") + c["message"]
            lines.append(f"| {c['id']} | {msg} | {', '.join(c['expected']) or '-'} | "
                         f"{', '.join(c['not_needs']) or '-'} | {', '.join(r['predicted']) or '(없음)'}"
                         + (f" ⚠ {r['error'][:60]}" if r.get("error") else "") + " |")
        lines.append("")
    path = out / f"{stamp}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["keyword", "agent", "both"], default="both")
    p.add_argument("--limit", type=int)
    p.add_argument("--cat", action="append", help="이 유형만 실행 (여러 번 줄 수 있음, 예: --cat 여러턴결합)")
    p.add_argument("--workers", type=int, default=4, help="에이전트 동시 실행 수")
    args = p.parse_args()

    load_dotenv()
    from app import llm
    cases = load_cases(args.limit, args.cat)
    meta = {"started": datetime.now().isoformat(timespec="seconds"), "provider": llm.provider_name()}
    results: dict[str, list[dict]] = {}

    if args.mode in ("keyword", "both"):
        results["keyword"] = [run_keyword(c) for c in cases]
    if args.mode in ("agent", "both"):
        run_id = uuid.uuid4().hex[:6]
        done = 0

        def one(c):
            nonlocal done
            r = run_agent(c, run_id)
            done += 1
            mark = "오류" if r.get("error") else ", ".join(r["predicted"]) or "(없음)"
            print(f"[{done}/{len(cases)}] {c['id']} {r['seconds']}s → {mark}", flush=True)
            return r

        with ThreadPoolExecutor(args.workers) as pool:
            results["agent"] = list(pool.map(one, cases))

    summary = summarize(cases, results)
    path = write_report(cases, results, summary, meta)
    for m, s in summary.items():
        print(f"{m}: {s['total'][0]}/{s['total'][1]}  " + "  ".join(f"{k} {v[0]}/{v[1]}" for k, v in s["by_cat"].items()))
    print(f"보고서: {path}")


if __name__ == "__main__":
    main()
