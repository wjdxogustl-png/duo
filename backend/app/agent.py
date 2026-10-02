"""Claude + LangChain 도구 호출 루프.

AgentExecutor 대신 bind_tools 로 루프를 직접 돌린다. 버전 변화에 덜 민감하고,
매 도구 호출을 trace 로 남겨 화면의 '도구 로그 패널'과 시연영상에 그대로 보여 줄 수 있다.
"""
import json
import time
from datetime import date

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from . import llm, memory
from .tools import ALL_TOOLS
from .tools.dday import compute_dday

MAX_STEPS = 8
LANG_NAMES = {"ko": "한국어", "en": "English", "vi": "Tiếng Việt", "ja": "日本語", "zh": "简体中文"}

SYSTEM_PROMPT = """너는 경상남도에 새로 정착한 이주민을 돕는 '정착 도우미' 에이전트다.
오늘 날짜: {today}. 응답 언어: {language} (사용자가 다른 언어로 말하면 그 언어로 답한다).

일하는 방식
1. 대화에서 새 정보를 알게 되면 바로 save_profile 로 저장한다. 필수 항목이 비어 있으면 한 번에 1~2개씩 쉽게 되묻는다.
2. 필수 항목이 채워지면 score_risk 로 정착 안정도를 확인하고, build_roadmap 으로 순서가 있는 할 일을 만든다.
3. recommend_mentoring_first 가 true 면 멘토·상담(search_programs category=멘토링 또는 노동상담)을 먼저 제안한다.
4. 로드맵 단계마다 search_programs 로 실제 지원사업을 찾아 연결한다. DB에 없는 사업을 지어내지 않는다.
5. 신청서가 필요하면 필요한 값을 모두 확인한 뒤 generate_application_doc 을 호출하고 다운로드 링크를 안내한다.
6. 사용자가 체류 종료일을 말하면 set_dday_reminder 로 저장한다.

지켜야 할 것
- 비자·체류 자격·법률 문제에 대해 판단하거나 단정하지 않는다. "출입국·외국인청(1345) 등 공식 기관에서 확인하세요"라고 연결한다.
- 지원사업 정보에는 출처(source_url)가 있으면 함께 알려 준다.
- 짧고 쉬운 문장으로 답한다. 한국어가 서툰 사용자를 기준으로 쓴다.
"""


FALLBACK_REPLY = {
    "ko": "죄송해요, 답을 만들지 못했어요. 한 번 더 말씀해 주세요.",
    "en": "Sorry, I couldn't make a reply. Could you say that again?",
    "vi": "Xin lỗi, mình chưa trả lời được. Bạn nói lại giúp mình nhé?",
    "ja": "すみません、うまく答えられませんでした。もう一度言っていただけますか？",
    "zh": "抱歉，我没能给出回答。请再说一遍好吗？",
}


def _clean_history(history: list[dict]) -> list[dict]:
    """API 규칙에 맞게 정리: user 로 시작, 같은 역할 연속은 합치고, 빈 내용은 버린다."""
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


def run(user_id: str, message: str, language: str = "ko", internal: bool = False) -> dict:
    """한 턴 실행. internal=True 면 사용자 메시지를 대화 기록에 남기지 않는다(능동 브리핑용)."""
    memory.current_user.set(user_id)
    started = time.perf_counter()
    state = memory.load()

    lang = state["profile"].get("language") or language
    messages = [SystemMessage(SYSTEM_PROMPT.format(today=date.today().isoformat(), language=LANG_NAMES.get(lang, lang)))]
    history = _clean_history(state["history"])
    if history and history[-1]["role"] == "user":  # 이번 메시지와 user 가 연속되지 않게
        history = history[:-1]
    for h in history:
        messages.append(HumanMessage(h["content"]) if h["role"] == "user" else AIMessage(h["content"]))
    messages.append(HumanMessage(message))

    model, provider = llm.get_model(ALL_TOOLS)
    trace, files = [], []
    reply = ""
    if hasattr(model, "run_turn"):
        # claude_agent 모드: Claude Code가 MCP로 도구를 직접 실행하며 한 턴을 끝낸다
        reply, trace = model.run_turn(messages, user_id)
        for c in trace:
            r = c.get("result")
            if c["tool"] == "generate_application_doc" and isinstance(r, dict) and r.get("download_url"):
                files.append(r["download_url"])
    else:
        reply = _run_loop(model, messages, trace, files)
    if not reply.strip():
        reply = FALLBACK_REPLY.get(lang, FALLBACK_REPLY["ko"])

    # 도구가 상태를 바꿨을 수 있으므로 다시 읽은 뒤 대화 기록만 추가
    state = memory.load()
    if not internal:
        state["history"].append({"role": "user", "content": message})
    state["history"].append({"role": "assistant", "content": reply})
    memory.save(state)

    return {
        "reply": reply,
        "trace": trace,
        "files": files,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "provider": provider,
        "state": {k: state[k] for k in ("profile", "roadmap", "dday")},
    }


def _run_loop(model, messages, trace, files) -> str:
    """도구 호출 루프: 모델이 판단하고 파이썬이 도구를 실행한다."""
    for _ in range(MAX_STEPS):
        ai: AIMessage = model.invoke(messages)
        messages.append(ai)
        if not ai.tool_calls:
            return _text_of(ai)
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
            if call["name"] == "generate_application_doc" and '"download_url"' in result:
                files.append(json.loads(result)["download_url"])
            messages.append(ToolMessage(result, tool_call_id=call["id"]))
    return "처리 단계가 너무 많아 멈췄습니다. 질문을 조금 나눠서 다시 말씀해 주세요."


def briefing_facts(user_id: str) -> dict | None:
    """재방문 시 에이전트가 먼저 말할 근거(규칙 기반). 프로필이 없으면 None."""
    state = memory.load(user_id)
    if not state["profile"]:
        return None
    facts = {"pending_steps": [s["title"] for s in state["roadmap"] if not s["done"]][:3]}
    if state["dday"]:
        facts["dday"] = compute_dday(state["dday"])
    return facts


def briefing(user_id: str, language: str = "ko") -> dict | None:
    facts = briefing_facts(user_id)
    if facts is None:
        return None
    prompt = (
        "[시스템 알림: 사용자가 다시 방문했다. 아래 사실을 바탕으로 먼저 짧게 인사하고, "
        "D-day가 있으면 알려 주고, 남은 단계 중 다음 할 일 하나를 제안해라. 도구는 필요할 때만 쓴다.]\n"
        + json.dumps(facts, ensure_ascii=False)
    )
    return run(user_id, prompt, language, internal=True)
