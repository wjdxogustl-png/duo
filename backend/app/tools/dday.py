"""사용자가 직접 입력한 체류 예정 종료일 기준 D-day 계산.

법적 판단(연장 가능 여부 등)은 하지 않는다. 날짜 관리 기능에 한정.
"""
from datetime import date

from .. import memory

REMIND_AT = [90, 60, 30, 14, 7, 3, 1]
DISCLAIMER = "이 날짜는 사용자가 직접 입력한 값입니다. 체류 관련 절차는 출입국·외국인청 공식 안내를 확인하세요."


def compute_dday(end_date: str, today: date | None = None) -> dict:
    """순수 함수(테스트 대상). end_date 형식: YYYY-MM-DD"""
    today = today or date.today()
    end = date.fromisoformat(end_date)
    days_left = (end - today).days
    upcoming = [d for d in REMIND_AT if d <= days_left]
    return {
        "end_date": end.isoformat(),
        "days_left": days_left,
        "label": f"D-{days_left}" if days_left > 0 else ("D-Day" if days_left == 0 else f"D+{-days_left}"),
        "next_reminder_at": f"D-{upcoming[0]}" if upcoming else None,
        "disclaimer": DISCLAIMER,
    }


def set_dday_reminder(end_date: str) -> dict:
    result = compute_dday(end_date)
    state = memory.load()
    state["dday"] = result["end_date"]
    memory.save(state)
    return result
