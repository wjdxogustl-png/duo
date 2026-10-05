"""변경 파이프라인: 기억(Memory)이 바뀌면 영향받는 계산을 코드가 순서대로 다시 한다.

대화 → 정보 추출(save_profile · note_situation) → Memory 변경
  → 변경 감지 → 영향 분석 → Risk 재평가 → Roadmap 갱신 → 지원사업 재검색 → 결과 검증
  → (LLM) 사용자에게 변화 설명

LLM이 score_risk · build_roadmap · search_programs 를 빠짐없이 다시 불러 주기를 기대하지 않고,
저장 도구가 끝나는 즉시 이 코드가 처리해 그 보고(무엇이 왜 바뀌었는지)를 도구 결과에 붙인다.
LLM은 보고를 근거로 변화를 설명만 한다. 정확해야 하는 재계산·검증은 모두 여기서 한다.
"""
from . import memory
from .tools.profile import REQUIRED_FIELDS
from .tools.programs import load_programs, normalize_region, search_programs
from .tools.risk import CRITERIA, compute_score
from .tools.roadmap import ROADMAP_KEYS, build_roadmap, generate_steps

RISK_KEYS = {key for _, _, key, _ in CRITERIA}

# 상황 기억의 필요 종류 → 지원사업 DB 분류
NEED_CATEGORIES = {
    "생활비": ["생활"], "주거": ["생활"], "의료·건강": ["생활"], "돌봄": ["생활", "자녀교육"],
    "일자리": ["취업"], "직장문제": ["노동상담"], "언어": ["한국어교육"],
    "행정·체류": ["행정", "법률상담"], "자녀교육": ["자녀교육"], "고립·정서": ["멘토링"],
    "안전": ["법률상담"], "기타": [],
}

FIELD_LABELS = {
    "name": "이름", "language": "언어", "region": "거주 지역", "months_in_korea": "한국 거주 개월 수",
    "has_spouse": "배우자 동거", "has_children": "자녀", "job_status": "일자리 상태",
    "korean_level": "한국어 수준", "has_local_support": "주변 도움", "workplace_issue": "직장 내 어려움",
    "knows_support_programs": "지원사업 인지",
}

PROGRAM_FIELDS = ("id", "name", "region", "category", "target", "cost", "schedule", "contact", "address",
                  "languages", "how_to_apply", "source_url", "checked_at", "verification", "note")


def detect_changes(before: dict, after: dict) -> dict:
    """저장 전후 상태를 비교해 바뀐 프로필 항목과 상황을 찾는다(순수 함수)."""
    bp, ap = before["profile"], after["profile"]
    profile = [
        {"field": k, "label": FIELD_LABELS.get(k, k), "before": bp.get(k), "after": ap.get(k)}
        for k in sorted(set(bp) | set(ap)) if bp.get(k) != ap.get(k)
    ]
    old = {s["id"]: s for s in before.get("situations") or []}
    situations = []
    for s in after.get("situations") or []:
        o = old.get(s["id"])
        if o is None:
            kind = "new" if s.get("status") != "해결됨" else None
        elif o.get("status") != "해결됨" and s.get("status") == "해결됨":
            kind = "resolved"
        elif any(o.get(k) != s.get(k) for k in ("need", "urgency", "status")):
            kind = "updated"
        else:
            kind = None
        if kind:
            situations.append({"id": s["id"], "change": kind, "need": s.get("need"), "urgency": s.get("urgency")})
    return {"profile": profile, "situations": situations}


def analyze_impact(changes: dict, before: dict, after: dict) -> dict:
    """바뀐 것마다 무엇을 다시 계산해야 하는지 정한다(순수 함수). 값은 다시 하는 이유."""
    fields = {c["field"] for c in changes["profile"]}
    ready = all(f in after["profile"] for f in REQUIRED_FIELDS)
    impact = {}
    if fields & RISK_KEYS:
        impact["risk"] = sorted(fields & RISK_KEYS)
    if fields & ROADMAP_KEYS and (before["roadmap"] or ready):
        impact["roadmap"] = sorted(fields & ROADMAP_KEYS)
    elif fields and ready and not before["roadmap"]:
        impact["roadmap"] = ["필수 항목이 모두 채워짐"]
    reasons = []
    if "region" in fields:
        reasons.append("region")
    if "roadmap" in impact:
        reasons.append("roadmap")
    if any(s["change"] in ("new", "updated") for s in changes["situations"]):
        reasons.append("situations")
    if reasons:
        impact["programs"] = reasons
    return impact


def _risk_stage(before: dict, after: dict) -> dict:
    old, new = compute_score(before["profile"]), compute_score(after["profile"])
    changed_items = [
        {"item": n["item"], "before": o["points"], "after": n["points"], "max": n["max"]}
        for o, n in zip(old["breakdown"], new["breakdown"]) if o["points"] != n["points"]
    ]
    return {
        "before": old["score"], "after": new["score"], "threshold": new["threshold"],
        "complete": new["complete"], "missing": new["missing"],
        "recommend_mentoring_first": new["recommend_mentoring_first"],
        "crossed_threshold": bool(old["complete"] and new["complete"]
                                  and old["recommend_mentoring_first"] != new["recommend_mentoring_first"]),
        "changed_items": changed_items,
    }


def _roadmap_stage(before: dict) -> dict:
    res = build_roadmap()  # 이미 끝낸 단계의 완료 표시는 유지된다
    old_ids = {s["id"] for s in before["roadmap"]}
    new_ids = {s["id"] for s in res["steps"]}
    brief = lambda s: {k: s[k] for k in ("id", "title", "category")}  # noqa: E731
    return {
        "added": [brief(s) for s in res["steps"] if s["id"] not in old_ids],
        "removed": [brief(s) | {"was_done": bool(s.get("done"))} for s in before["roadmap"] if s["id"] not in new_ids],
        "next_step": brief(res["next_step"]) if res["next_step"] else None,
    }


def _program_targets(impact: dict, changes: dict, roadmap: dict | None, after: dict) -> dict[str, str]:
    """다시 검색할 지원사업 분류 → 이유."""
    targets: dict[str, str] = {}
    reasons = impact.get("programs") or []
    if "region" in reasons:
        for s in after["roadmap"]:
            if not s["done"]:
                targets.setdefault(s["category"], "거주 지역이 바뀜")
    if roadmap:
        for s in roadmap["added"]:
            targets.setdefault(s["category"], f"새 로드맵 단계: {s['title']}")
    for s in changes["situations"]:
        if s["change"] in ("new", "updated"):
            for c in NEED_CATEGORIES.get(s["need"], []):
                targets.setdefault(c, f"새로 알게 된 상황: {s['need']}")
    return targets


def _programs_stage(targets: dict[str, str], region: str | None) -> dict:
    return {cat: {"reason": why, "found": search_programs(region, cat)["programs"]} for cat, why in targets.items()}


def verify(before: dict, after: dict, programs: dict) -> dict:
    """사용자에게 말하기 전에 결과를 확인한다. 통과한 지원사업만 verified 에 남긴다."""
    issues: list[str] = []
    db = {p["id"]: p for p in load_programs()}
    region = normalize_region(after["profile"].get("region"))
    verified, no_match = {}, []
    for cat, r in programs.items():
        ok = []
        for p in r["found"]:
            src = db.get(p.get("id"))
            if src is None:
                issues.append(f"DB에 없는 사업이 검색됨: {p.get('id')}")
            elif src.get("is_sample"):
                issues.append(f"{src['id']}: 예시 데이터라 안내하지 않음")
            elif not src.get("source_url"):
                issues.append(f"{src['id']}: 출처(source_url)가 없어 안내하지 않음")
            elif region and normalize_region(src["region"]) not in (region, "경남"):
                issues.append(f"{src['id']}: 사용자 지역({region})과 맞지 않음")
            else:
                ok.append({k: src.get(k) for k in PROGRAM_FIELDS})
        verified[cat] = ok
        if not ok:
            no_match.append(cat)

    if after["roadmap"]:
        expected = [s["id"] for s in generate_steps(after["profile"])]
        if [s["id"] for s in after["roadmap"]] != expected:
            issues.append("로드맵이 현재 프로필 규칙과 맞지 않음")
        kept = {s["id"] for s in after["roadmap"]}
        lost = [s["id"] for s in before["roadmap"]
                if s.get("done") and s["id"] in kept
                and not next(n for n in after["roadmap"] if n["id"] == s["id"])["done"]]
        if lost:
            issues.append(f"완료했던 단계의 완료 표시가 사라짐: {lost}")
    return {"ok": not any("로드맵" in i or "DB에 없는" in i for i in issues),
            "issues": issues, "verified_programs": verified, "no_match": no_match}


def _summary(changes, risk, roadmap, checks) -> list[str]:
    """LLM이 사용자에게 설명할 근거. 사실만 적는다."""
    out = []
    for c in changes["profile"]:
        out.append(f"{c['label']}: {c['before'] if c['before'] is not None else '(없음)'} → {c['after']}")
    for s in changes["situations"]:
        out.append({"new": "새 상황", "updated": "상황 변경", "resolved": "상황 해결"}[s["change"]]
                   + f": {s['need']} (급함 {s['urgency']})")
    if risk:
        if risk["complete"] and risk["before"] != risk["after"]:
            out.append(f"정착 안정도: {risk['before'] if risk['before'] is not None else '미판정'} → {risk['after']}"
                       f" (기준 {risk['threshold']})")
        if risk["crossed_threshold"]:
            out.append("멘토·상담 우선 여부가 바뀜: " + ("이제 멘토·상담을 먼저 권함" if risk["recommend_mentoring_first"]
                                                 else "더 이상 멘토·상담을 먼저 권하지 않음"))
        if not risk["complete"]:
            out.append(f"정착 안정도 판정에 더 필요한 항목: {risk['missing']}")
    if roadmap:
        out += [f"로드맵 단계 추가: {s['title']}" for s in roadmap["added"]]
        out += [f"로드맵 단계 제외: {s['title']}" + (" (이미 완료했던 단계)" if s["was_done"] else "")
                for s in roadmap["removed"]]
    for cat, ps in checks["verified_programs"].items():
        if ps:
            out.append(f"지원사업({cat}): " + ", ".join(p["name"] for p in ps))
    if checks["no_match"]:
        out.append(f"확인된 지원사업이 없는 분야(공식 상담 창구로 안내): {checks['no_match']}")
    return out


def after_change(before: dict) -> dict | None:
    """저장 도구 실행 직후 호출. 바뀐 것이 없으면 None."""
    after = memory.load()
    changes = detect_changes(before, after)
    if not changes["profile"] and not changes["situations"]:
        return None
    steps = [{"stage": "detect", "detail": ", ".join(
        [f"{c['field']}: {c['before']} → {c['after']}" for c in changes["profile"]]
        + [f"{s['change']}: {s['need']}" for s in changes["situations"]])}]

    impact = analyze_impact(changes, before, after)
    steps.append({"stage": "impact", "detail": ", ".join(impact) or "-"})

    risk = roadmap = None
    if "risk" in impact:
        risk = _risk_stage(before, after)
        steps.append({"stage": "risk", "detail": f"{risk['before']} → {risk['after']}"})
    if "roadmap" in impact:
        roadmap = _roadmap_stage(before)
        after = memory.load()
        steps.append({"stage": "roadmap", "detail": " ".join(
            [f"+{s['id']}" for s in roadmap["added"]] + [f"-{s['id']}" for s in roadmap["removed"]]) or "="})

    programs = _programs_stage(_program_targets(impact, changes, roadmap, after), after["profile"].get("region"))
    if programs:
        steps.append({"stage": "programs", "detail": ", ".join(f"{c} {len(r['found'])}" for c, r in programs.items())})

    checks = verify(before, after, programs)
    steps.append({"stage": "verify", "detail": "ok" if checks["ok"] and not checks["issues"]
                  else f"{len(checks['issues'])} issue(s)"})

    return {
        "changes": changes,
        "impact": impact,
        "risk": risk,
        "roadmap": roadmap,
        "programs": {c: {"reason": r["reason"], "verified": checks["verified_programs"][c]} for c, r in programs.items()},
        "checks": {"ok": checks["ok"], "issues": checks["issues"], "no_match": checks["no_match"]},
        "summary": _summary(changes, risk, roadmap, checks),
        "steps": steps,
    }
