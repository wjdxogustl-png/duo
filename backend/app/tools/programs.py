"""팀이 직접 조사한 지원사업 DB(data/programs.json) 검색."""
import json
import re

from ..memory import DATA_DIR

PROGRAMS_PATH = DATA_DIR / "programs.json"


def load_programs() -> list[dict]:
    return json.loads(PROGRAMS_PATH.read_text(encoding="utf-8"))


def normalize_region(r: str | None) -> str | None:
    """"김해시", "창원특례시", "경상남도" 처럼 표기가 달라도 DB 값("김해", "창원", "경남")과 맞춘다."""
    if not r:
        return r
    r = r.strip().replace("경상남도", "경남")
    return re.sub(r"(특례시|시|군)$", "", r)


def search_programs(region: str | None = None, category: str | None = None, keyword: str | None = None) -> dict:
    region = normalize_region(region)
    results = []
    for p in load_programs():
        # region 이 "경남"인 사업은 도 전체 대상이므로 어느 시군에서 검색해도 포함.
        # 검색어가 "경남"이면 도 전체를 찾는 것이므로 지역으로 거르지 않는다.
        if region and region != "경남" and normalize_region(p["region"]) not in (region, "경남"):
            continue
        if category and p["category"] != category:
            continue
        if keyword and keyword not in (p["name"] + p["target"] + p["how_to_apply"]):
            continue
        results.append(p)
    return {"count": len(results), "programs": results}
