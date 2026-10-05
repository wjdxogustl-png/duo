"""Claude + LangChain 도구 호출 루프.

AgentExecutor 대신 bind_tools 로 루프를 직접 돌린다. 버전 변화에 덜 민감하고,
매 도구 호출을 trace 로 남겨 화면의 '도구 로그 패널'과 시연영상에 그대로 보여 줄 수 있다.
"""
import json
import time
from datetime import date, datetime, timedelta

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from . import llm, memory
from .tools import ALL_TOOLS
from .tools.hotlines import prompt_lines
from .tools.dday import compute_dday

MAX_STEPS = 8
BRIEFING_INTERVAL = timedelta(hours=6)  # 마지막 브리핑 후 이 시간 안에는 다시 브리핑하지 않는다
LANG_NAMES = {"ko": "한국어", "en": "English", "vi": "Tiếng Việt", "ja": "日本語", "zh": "简体中文"}

SYSTEM_PROMPT = """너는 경상남도에 새로 정착한 이주민을 돕는 '정착 도우미' 에이전트다.
오늘 날짜: {today}. 응답 언어: {language} (사용자가 다른 언어로 말하면 그 언어로 답한다).

가장 중요한 일: 맥락을 읽고 스스로 판단하기
키워드에 반응하지 말고, 사람 상담사처럼 말의 뜻을 읽는다. 사용자의 말을 받을 때마다 속으로 다음을 판단한다.
- 겉으로 묻는 것은 무엇인가?
- 말 속에 드러난 숨은 필요는 무엇인가? 사용자는 지원이 필요하다고 직접 말하지 않는 경우가 많다.
  예) "이번 달 월세가 밀렸어요" → 생활비 어려움 / "아이 학원을 끊어야 할 것 같아요" → 교육이 아니라 돈 문제일 수 있음
  예) "요즘 저녁에 일을 하나 더 해요" → 경제적 압박, 피로, 저녁 수업에 못 올 가능성
- 아래 [기억하고 있는 상황]·[프로필]과 이어지는가? 예전에 들은 말과 지금 말을 합치면 새로 보이는 문제가 있는가?
  예) 예전 "아이가 6살이에요" + 지금 "다음 주부터 야간 근무예요" → 밤에 아이를 맡길 곳이 비는 문제
  이전 말과 합칠 때는 지금 말의 겉 주제에서 멈추지 말고, 이전 말이 이 사람에게 어떤 조건을 만드는지 따라가 본다.
  예) 고용허가·유학 등 체류 자격 + 폐업·이직·근무 시간 변화 → 직장 문제이면서 체류 자격 문제 (행정·체류)
  예) 체류 기간이 정해져 있음 + 회사를 옮기고 싶음 → 옮기는 시기와 절차가 체류에 걸리는 문제 (행정·체류)
  예) 한국어를 거의 못함 + 학교·병원·관공서에 가야 함 → 그 자리에서 말이 통하지 않는 문제 (언어)
  예) 혼자 삶 + 다치거나 아픔 → 치료뿐 아니라 일상을 도와줄 사람이 없는 문제 (돌봄)
  이렇게 합쳐서 보이는 필요는 겉으로 보이는 필요와 따로 note_situation 으로 기록한다.
- 부정·반어·농담을 구분한다. "돈 걱정은 없어요, 시간이 문제죠"는 돈이 아니라 시간 문제다.
- 확신이 낮으면 단정하지 말고, 짐작한 내용을 부드럽게 확인하는 질문을 한 번 한다.
판단한 상황과 숨은 필요는 note_situation 으로 근거(사용자 원문)와 함께 기억한다. 해결됐거나 바뀌면 같은 id 로 갱신한다.
그다음 그 필요를 실제로 도울 수 있는 곳(지원사업 DB, 로드맵 단계, 공식 상담 창구)에 연결하고,
사용자가 묻지 않았어도 곧 필요해질 것이 보이면 미리 알려 준다.

일하는 방식
1. 대화에서 새 정보를 알게 되면 바로 save_profile 로 저장한다. 필수 항목이 비어 있으면 한 번에 1~2개씩 쉽게 되묻는다.
   단, 사용자가 급한 어려움을 말하면 프로필 질문보다 그 어려움을 먼저 다룬다.
2. 필수 항목이 채워지면 score_risk 로 정착 안정도를 확인하고, build_roadmap 으로 순서가 있는 할 일을 만든다.
   score_risk 결과의 missing 이 있으면 그 항목을 먼저 쉽게 되묻고, save_profile 로 저장한 뒤 다시 score_risk 를 호출한다.
3. recommend_mentoring_first 가 true 면 멘토·상담(search_programs category=멘토링 또는 노동상담)을 먼저 제안한다.
4. 로드맵 단계마다 search_programs 로 실제 지원사업을 찾아 연결한다. DB에 없는 사업을 지어내지 않는다.
5. 사용자가 지원사업에 신청하고 싶어 하면 draft_application 으로 신청서 초안을 만든다. 초안은 화면에 보이고 사용자가 직접 고친다.
   이름·연락처를 채팅으로 모으지 않는다. 외국인등록번호·여권번호·계좌번호는 묻지도 받지도 않는다.
   제출은 사용자가 기관에 직접 한다고 안내하고, 대신 제출하겠다고 말하지 않는다.
6. 사용자가 체류 종료일을 말하면 set_dday_reminder 로 저장한다.
7. 서로 의존하지 않는 도구(예: 여러 단계의 search_programs)는 한 번에 함께 호출한다.
8. save_profile · note_situation 결과에 pipeline 이 있으면, 바뀐 정보 때문에 정착 안정도·로드맵·지원사업이
   이미 다시 계산되고 검증된 것이다. pipeline.summary 를 근거로 "무엇이 바뀌어서 무엇이 달라졌는지"를
   사용자에게 쉬운 말로 설명한다 (예: 회사를 그만두셔서 로드맵에 취업 지원 단계를 넣었어요).
   summary 에 없는 변화를 지어내지 않고, checks.no_match 분야는 공식 상담 창구로 안내한다.
9. 사용자가 지금 바로 할 수 있는 다음 행동이 보이면, 다른 도구를 모두 부른 뒤 suggest_actions 로 1~3개를 버튼으로 내민다.
   묻지 않았어도 판단한 상황에서 곧 필요해질 행동을 먼저 제안한다 (예: 신청서 초안 만들기, 체류 종료일 등록, 상담 창구 전화).
   되묻는 질문이 있어도 지금 할 수 있는 행동(전화·신청 등)이 있으면 함께 제안한다. 할 수 있는 행동이 하나도 없을 때만 부르지 않는다.
10. 답장 글은 모든 도구 호출(suggest_actions 포함)이 끝난 뒤 맨 마지막에 한 번에 쓴다.
   답장에는 이해한 상황과 도울 내용을 담고, 버튼으로 내민 행동은 한 문장으로만 짧게 언급한다.
   버튼은 답장을 돕는 것이지 대신하지 않는다. 버튼만 띄우고 답장을 한 줄로 끝내지 않는다.
11. 위기 상황이면 지원사업보다 전문 창구 연결이 먼저다. note_situation 의 urgency 가 높음이고
   폭력·임금체불·생명 위험과 관련되면, search_programs 보다 먼저 아래 공식 상담 창구 중 알맞은 곳을
   suggest_actions 의 call 카드로 제안한다 (카드 순서도 창구가 맨 앞). 생명·안전이 위험하면 112·119 를 가장 먼저 안내한다.
   예) 석 달째 월급을 못 받음 → 1350 (모국어 상담이 필요하면 1644-0644 도) / 남편에게 맞아 집에 못 감 → 112 또는 1366, 1577-1366

지켜야 할 것
- 비자·체류 자격·법률 문제에 대해 판단하거나 단정하지 않는다. "출입국·외국인청(1345) 등 공식 기관에서 확인하세요"라고 연결한다.
- 지원사업 정보에는 출처(source_url)가 있으면 함께 알려 준다.
- 짧고 쉬운 문장으로 답한다. 한국어가 서툰 사용자를 기준으로 쓴다.
- 질문은 한 번에 최대 2개만 한다.
- 저장·생성·검색했다고 말하려면 반드시 그 도구를 실제로 호출한다. 도구를 부르지 않고 했다고 말하지 않는다.
- 채팅창은 마크다운을 표시하지 못한다. 굵게(**), 제목(#), 표를 쓰지 말고 짧은 문단과 줄바꿈으로 쓴다. 목록이 필요하면 "1." 같은 번호만 쓴다.
- DB에 맞는 지원사업이 없으면 지어내지 말고, 아래 공식 상담 창구 중 알맞은 곳을 안내한다. 이 목록에 없는 번호는 안내하지 않는다.
{hotlines}

{context}
"""


# 모델이 텍스트 없이 끝났을 때 대신 보여 줄 문장(빈 assistant 메시지는 API가 거부한다)
FALLBACK_REPLY = {
    "ko": "죄송해요, 답을 만들지 못했어요. 한 번 더 말씀해 주세요.",
    "en": "Sorry, I couldn't make a reply. Could you say that again?",
    "vi": "Xin lỗi, mình chưa trả lời được. Bạn nói lại giúp mình nhé?",
    "ja": "すみません、うまく答えられませんでした。もう一度言っていただけますか？",
    "zh": "抱歉，我没能给出回答。请再说一遍好吗？",
}


def clean_history(history: list[dict]) -> list[dict]:
    """API 규칙(user 로 시작, 역할 교대, 빈 내용 금지)에 맞게 대화 기록을 정리한다(테스트 대상).
    능동 브리핑은 assistant 만 저장하고 MAX_HISTORY 로 앞이 잘리기도 해서 규칙이 깨질 수 있다."""
    out: list[dict] = []
    for h in history:
        content = (h.get("content") or "").strip()
        if not content:
            continue
        if not out and h["role"] != "user":
            continue
        if out and out[-1]["role"] == h["role"]:
            out[-1] = {"role": h["role"], "content": out[-1]["content"] + "\n\n" + content}
        else:
            out.append({"role": h["role"], "content": content})
    return out


TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}


def _text_of(msg: AIMessage) -> str:
    if isinstance(msg.content, str):
        return msg.content
    return "".join(b.get("text", "") for b in msg.content if isinstance(b, dict) and b.get("type") == "text")


def _days_ago(iso: str | None) -> int | None:
    if not iso:
        return None
    return (datetime.now() - datetime.fromisoformat(iso)).days


def context_block(state: dict) -> str:
    """에이전트가 매 턴 다시 읽는 장기 기억: 프로필, 기억하고 있는 상황, 로드맵 진행, D-day.
    대화 기록(최근 30개)이 잘려도 맥락이 이어지게 한다. 해석은 하지 않고 사실만 넘긴다."""
    lines = ["[프로필]", json.dumps(state["profile"], ensure_ascii=False) if state["profile"] else "(아직 없음)"]

    situations = state.get("situations") or []
    lines.append("\n[기억하고 있는 상황] (id · 필요 · 이해한 내용 · 근거 · 확신 · 급함 · 상태 · 처음 들은 지 며칠)")
    if situations:
        for s in situations:
            lines.append(
                f"- {s['id']} · {s.get('need')} · {s.get('understanding')} · 근거 \"{s.get('evidence')}\" · "
                f"{s.get('confidence')} · {s.get('urgency')} · {s.get('status')} · {_days_ago(s.get('created_at'))}일 전"
                + (f" · 다음에 할 일: {s['follow_up']}" if s.get("follow_up") else "")
            )
    else:
        lines.append("(아직 없음)")

    if state["roadmap"]:
        done = [s["title"] for s in state["roadmap"] if s["done"]]
        todo = [s["title"] for s in state["roadmap"] if not s["done"]]
        lines.append(f"\n[로드맵] 끝낸 단계: {done or '없음'} / 남은 단계: {todo or '없음'}")
    if state["dday"]:
        lines.append(f"\n[체류 종료일] {state['dday']} ({compute_dday(state['dday'])['label']})")
    last = next((h for h in reversed(state["history"]) if h["role"] == "user"), None)
    if state.get("last_briefing_at"):
        lines.append(f"\n[마지막 방문 브리핑] {_days_ago(state['last_briefing_at'])}일 전")
    if last is None:
        lines.append("\n(첫 대화)")
    return "\n".join(lines)


def actions_of(trace: list[dict]) -> list[dict]:
    """이번 턴의 마지막 suggest_actions 호출에서 검증을 통과한 카드(테스트 대상)."""
    for c in reversed(trace):
        if c["tool"] == "suggest_actions" and isinstance(c.get("result"), dict):
            return c["result"].get("shown") or []
    return []


def draft_of(trace: list[dict]) -> dict | None:
    """이번 턴에 만든 마지막 신청서 초안(테스트 대상)."""
    for c in reversed(trace):
        if c["tool"] == "draft_application" and isinstance(c.get("result"), dict) and c["result"].get("draft"):
            return c["result"]["draft"]
    return None


def run(user_id: str, message: str, language: str = "ko", internal: bool = False) -> dict:
    """한 턴 실행. internal=True 면 사용자 메시지를 대화 기록에 남기지 않는다(능동 브리핑용)."""
    memory.current_user.set(user_id)
    started = time.perf_counter()
    state = memory.load()

    lang = state["profile"].get("language") or language
    messages = [SystemMessage(SYSTEM_PROMPT.format(
        today=date.today().isoformat(), language=LANG_NAMES.get(lang, lang), context=context_block(state),
        hotlines=prompt_lines(),
    ))]
    history = clean_history(state["history"])
    # 이번 메시지도 user 이므로 기록이 user 로 끝나면 합쳐서 역할 교대를 지킨다 (내용을 버리지 않는다).
    # 브리핑(internal)은 시스템 알림으로 시작해야 하므로 앞의 user 기록은 빼고 보낸다.
    message_for_model = message
    if history and history[-1]["role"] == "user":
        last = history.pop()["content"]
        if not internal:
            message_for_model = last + "\n\n" + message
    for h in history:
        messages.append(HumanMessage(h["content"]) if h["role"] == "user" else AIMessage(h["content"]))
    messages.append(HumanMessage(message_for_model))

    model, provider = llm.get_model(ALL_TOOLS)
    trace = []
    reply = ""
    if hasattr(model, "run_turn"):
        # claude_agent 모드: Claude Code가 MCP로 도구를 직접 실행하며 한 턴을 끝낸다
        reply, trace = model.run_turn(messages, user_id)
    else:
        reply = _run_loop(model, messages, trace)
    if not reply.strip():
        reply = FALLBACK_REPLY.get(lang, FALLBACK_REPLY["ko"])
    actions = actions_of(trace)
    draft = draft_of(trace)

    # 도구가 상태를 바꿨을 수 있으므로 다시 읽은 뒤 대화 기록만 추가 (빈 내용은 저장하지 않는다)
    state = memory.load()
    if not internal and message.strip():
        state["history"].append({"role": "user", "content": message})
    # 액션 카드도 함께 저장해 새로고침 뒤에도 마지막 답장의 버튼이 다시 보이게 한다
    state["history"].append({"role": "assistant", "content": reply, **({"actions": actions} if actions else {}),
                             **({"draft_id": draft["id"]} if draft else {})})
    memory.save(state)

    return {
        "reply": reply,
        "trace": trace,
        "actions": actions,
        "draft": draft,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "provider": provider,
        "state": {
            **{k: state[k] for k in ("profile", "roadmap", "dday", "situations")},
            "dday_label": compute_dday(state["dday"])["label"] if state["dday"] else None,
        },
    }


def _run_loop(model, messages, trace) -> str:
    """도구 호출 루프: 모델이 판단하고 파이썬이 도구를 실행한다.
    도구를 부르기 전에 쓴 글도 모아 답장에 넣는다 (본문 → 도구 → 한 줄 순서로 써도 본문이 남게)."""
    texts = []
    for _ in range(MAX_STEPS):
        ai: AIMessage = model.invoke(messages)
        messages.append(ai)
        if _text_of(ai).strip():
            texts.append(_text_of(ai).strip())
        if not ai.tool_calls:
            return "\n\n".join(texts)
        for call in ai.tool_calls:
            t0 = time.perf_counter()
            try:
                result = TOOLS_BY_NAME[call["name"]].invoke(call["args"])
            except Exception as e:  # 도구 오류도 모델에게 돌려줘서 스스로 수습하게 한다
                result = json.dumps({"error": str(e)}, ensure_ascii=False)
            trace.append({
                "tool": call["name"],
                "args": call["args"],
                "result": json.loads(result) if result.startswith("{") else result,
                "ms": round((time.perf_counter() - t0) * 1000),
            })
            messages.append(ToolMessage(result, tool_call_id=call["id"]))
    return "처리 단계가 너무 많아 멈췄습니다. 질문을 조금 나눠서 다시 말씀해 주세요."


def briefing_facts(user_id: str) -> dict | None:
    """재방문 시 에이전트가 먼저 말할 근거가 되는 사실. 아는 것이 없으면 None.
    무엇을 먼저 말할지는 정하지 않는다. 그 판단은 에이전트가 한다."""
    state = memory.load(user_id)
    open_situations = [s for s in state.get("situations") or [] if s.get("status") != "해결됨"]
    if not state["profile"] and not open_situations:
        return None
    facts = {
        "pending_steps": [s["title"] for s in state["roadmap"] if not s["done"]][:3],
        "open_situations": [
            {k: s.get(k) for k in ("id", "need", "understanding", "urgency", "follow_up")}
            | {"days_ago": _days_ago(s.get("created_at"))}
            for s in open_situations
        ],
        "days_since_last_visit": _days_ago(state.get("last_briefing_at")),
    }
    if state["dday"]:
        facts["dday"] = compute_dday(state["dday"])
    return facts


def briefing(user_id: str, language: str = "ko", force: bool = False) -> dict | None:
    """force=True 면 시간 제한 없이 브리핑한다(시연용)."""
    facts = briefing_facts(user_id)
    if facts is None:
        return None
    state = memory.load(user_id)
    last = state.get("last_briefing_at")
    if not force and last and datetime.now() - datetime.fromisoformat(last) < BRIEFING_INTERVAL:
        return None
    prompt = (
        "[시스템 알림: 사용자가 다시 방문했다. 사용자는 아직 아무 말도 하지 않았다. "
        "아래 사실과 기억하고 있는 상황을 바탕으로, 지난 시간 동안 사용자에게 무슨 일이 생겼을지, "
        "지금 무엇이 가장 필요할지 스스로 판단해 먼저 짧게 말을 걸어라. "
        "열려 있는 급한 상황이 있으면 그 뒤로 어떻게 됐는지 먼저 안부를 묻고, "
        "곧 다가오는 일(D-day 등)이 있으면 미리 알려 주고, 할 일은 가장 중요한 하나만 제안한다. "
        "사실에 없는 일을 지어내지 않는다. 도구는 필요할 때만 쓴다.]\n"
        + json.dumps(facts, ensure_ascii=False)
    )
    result = run(user_id, prompt, language, internal=True)
    state = memory.load(user_id)
    state["last_briefing_at"] = datetime.now().isoformat(timespec="seconds")
    memory.save(state, user_id)
    return result
