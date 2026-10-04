"""변경 파이프라인: 기억이 바뀌면 변경 감지 → 영향 분석 → Risk·Roadmap·지원사업 재계산 → 검증이 코드로 일어나는지 확인한다."""
import json

import pytest

from app import memory
from app.tools import build_roadmap, note_situation, programs, save_profile, update_roadmap_step

BASE = {"region": "김해", "months_in_korea": 2, "korean_level": 1, "has_children": False,
        "job_status": "employed", "has_local_support": True, "workplace_issue": False,
        "knows_support_programs": True}

DB = [
    {"id": "GH-JOB-1", "name": "김해 외국인 취업 지원", "region": "김해", "category": "취업", "target": "외국인 주민",
     "how_to_apply": "방문", "source_url": "https://example.org/job", "checked_at": "2026-10-03"},
    {"id": "GN-JOB-2", "name": "경남 이주민 일자리 상담", "region": "경남", "category": "취업", "target": "도민",
     "how_to_apply": "전화", "source_url": "", "checked_at": "2026-10-03"},
    {"id": "SAMPLE-1", "is_sample": True, "name": "[예시] 취업", "region": "김해", "category": "취업", "target": "-",
     "how_to_apply": "-", "source_url": "https://example.org", "checked_at": "2026-10-03"},
    {"id": "CW-KO-1", "name": "창원 한국어 교실", "region": "창원", "category": "한국어교육", "target": "외국인",
     "how_to_apply": "방문", "source_url": "https://example.org/ko", "checked_at": "2026-10-03"},
    {"id": "GN-ADM-1", "name": "경남 외국인 행정 도움", "region": "경남", "category": "행정", "target": "외국인",
     "how_to_apply": "전화", "source_url": "https://example.org/adm", "checked_at": "2026-10-03"},
]


@pytest.fixture(autouse=True)
def tmp_data(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "USERS_DIR", tmp_path / "users")
    db = tmp_path / "programs.json"
    db.write_text(json.dumps(DB, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(programs, "PROGRAMS_PATH", db)
    memory.current_user.set("pipe")


def save(**kw):
    return json.loads(save_profile.invoke(kw))


def onboarded():
    """필수 항목이 모두 있고 로드맵까지 만든 사용자."""
    memory.save({**memory.empty_state(), "profile": dict(BASE)})
    build_roadmap.invoke({})


def test_no_change_no_pipeline():
    onboarded()
    assert "pipeline" not in save(region="김해")


def test_job_loss_updates_roadmap_and_finds_verified_programs():
    onboarded()
    p = save(job_status="seeking")["pipeline"]

    assert p["changes"]["profile"] == [{"field": "job_status", "label": "일자리 상태",
                                        "before": "employed", "after": "seeking"}]
    assert p["impact"] == {"roadmap": ["job_status"], "programs": ["roadmap"]}
    assert [s["id"] for s in p["roadmap"]["added"]] == ["job_support"]
    assert any(s["id"] == "job_support" for s in memory.load()["roadmap"])   # 실제로 저장됨

    # 검증: 출처 없는 사업과 예시 데이터는 걸러지고, 출처 있는 지역 사업만 남는다
    assert [x["id"] for x in p["programs"]["취업"]["verified"]] == ["GH-JOB-1"]
    assert any("GN-JOB-2" in i for i in p["checks"]["issues"])
    assert any("SAMPLE-1" in i for i in p["checks"]["issues"])
    assert p["checks"]["ok"]
    assert "로드맵 단계 추가: 취업 지원 프로그램 확인" in p["summary"]
    assert [s["stage"] for s in p["steps"]] == ["detect", "impact", "roadmap", "programs", "verify"]


def test_risk_reevaluated_and_threshold_crossing_reported():
    onboarded()
    p = save(workplace_issue=True, has_local_support=False, knows_support_programs=False)["pipeline"]
    r = p["risk"]
    assert (r["before"], r["after"]) == (65, 10)
    assert r["crossed_threshold"] and r["recommend_mentoring_first"]
    assert {i["item"] for i in r["changed_items"]} == {"주변 도움 가능", "직장 내 어려움 없음", "지원사업 인지"}
    assert any("이제 멘토·상담을 먼저 권함" in s for s in p["summary"])


def test_done_steps_kept_and_removed_done_step_reported():
    onboarded()
    update_roadmap_step.invoke({"step_id": "korean_class", "done": True})
    update_roadmap_step.invoke({"step_id": "registration_check", "done": True})

    p = save(months_in_korea=12)["pipeline"]
    roadmap = {s["id"]: s for s in memory.load()["roadmap"]}
    assert roadmap["korean_class"]["done"]                       # 남아 있는 단계의 완료 표시 유지
    assert "registration_check" not in roadmap                   # 12개월이면 더 이상 해당하지 않음
    removed = {s["id"]: s for s in p["roadmap"]["removed"]}
    assert removed["registration_check"]["was_done"]
    assert not any("완료 표시가 사라짐" in i for i in p["checks"]["issues"])


def test_region_change_researches_open_steps():
    onboarded()
    p = save(region="창원")["pipeline"]
    assert p["impact"] == {"programs": ["region"]}
    assert "한국어교육" in p["programs"]                          # 남은 단계의 분류를 새 지역으로 다시 찾음
    assert [x["id"] for x in p["programs"]["한국어교육"]["verified"]] == ["CW-KO-1"]


def test_first_complete_profile_builds_roadmap():
    memory.save({**memory.empty_state(), "profile": {k: v for k, v in BASE.items() if k != "job_status"}})
    p = save(job_status="employed")["pipeline"]
    assert "roadmap" in p["impact"] and memory.load()["roadmap"]


def test_new_situation_searches_programs_for_need():
    memory.save({**memory.empty_state(), "profile": {"region": "김해"}})
    r = json.loads(note_situation.invoke({
        "need": "행정·체류", "understanding": "고용허가 노동자인데 공장이 문을 닫아 사업장 변경 절차가 필요함",
        "evidence": "사장님이 다음 달에 공장 문 닫는대요", "confidence": "추정", "urgency": "높음"}))
    p = r["pipeline"]
    assert p["changes"]["situations"][0]["change"] == "new"
    assert set(p["programs"]) == {"행정", "법률상담"}
    assert [x["id"] for x in p["programs"]["행정"]["verified"]] == ["GN-ADM-1"]
    assert "법률상담" in p["checks"]["no_match"]
