"""공식 상담 창구(data/hotlines.json). 번호마다 공식 출처와 확인일을 함께 둔다.

액션 카드의 전화 번호 검증과 시스템 프롬프트의 상담 창구 안내가 모두 이 파일을 읽는다.
"""
import json

from ..memory import DATA_DIR

HOTLINES_PATH = DATA_DIR / "hotlines.json"


def load_hotlines() -> list[dict]:
    return json.loads(HOTLINES_PATH.read_text(encoding="utf-8"))


def prompt_lines() -> str:
    """시스템 프롬프트에 넣을 창구 목록: '번호 이름 (운영 시간) — 연결할 상황' 한 줄씩."""
    return "\n".join(f"  {h['number']} {h['name']} ({h['hours']}) — {h['when']}" for h in load_hotlines())
