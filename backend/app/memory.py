"""사용자별 상태(Memory)를 JSON 파일로 저장한다.

저장 항목: profile(온보딩 정보), roadmap(단계 목록 + 완료 여부), dday(체류 종료일), history(대화).
대회 MVP 규모에서는 파일 저장으로 충분하다. 필요하면 SQLite로 교체.
"""
import json
import re
from contextvars import ContextVar
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
USERS_DIR = DATA_DIR / "users"
OUTPUT_DIR = DATA_DIR / "output"

# 도구 함수가 "지금 누구의 요청인지" 알 수 있도록 요청마다 설정한다.
current_user: ContextVar[str] = ContextVar("current_user", default="demo")

MAX_HISTORY = 30


def _safe_id(user_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", user_id)[:64] or "demo"


def _path(user_id: str) -> Path:
    return USERS_DIR / f"{_safe_id(user_id)}.json"


def empty_state() -> dict:
    return {"profile": {}, "roadmap": [], "dday": None, "history": [], "last_briefing_at": None, "situations": []}


def load(user_id: str | None = None) -> dict:
    p = _path(user_id or current_user.get())
    if not p.exists():
        return empty_state()
    return {**empty_state(), **json.loads(p.read_text(encoding="utf-8"))}


def save(state: dict, user_id: str | None = None) -> None:
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    state["history"] = state.get("history", [])[-MAX_HISTORY:]
    _path(user_id or current_user.get()).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def reset(user_id: str) -> None:
    p = _path(user_id)
    if p.exists():
        p.unlink()
