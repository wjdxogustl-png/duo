"""Claude Code CLI(`claude -p`)를 LLM으로 쓰는 모드 (LLM_PROVIDER=claude_cli).

VS Code·터미널에 로그인한 Claude 구독으로 동작하므로 API 키가 필요 없다.
개인 개발·테스트용이다. 구독 플랜의 `claude -p` 사용량은 월간 Agent SDK 크레딧에서 차감된다.

동작 방식
- Claude Code의 내장 도구(Bash, 파일 편집 등)는 모두 끈다(--tools ""). Claude는 판단만 한다.
- 우리 도구 7개의 설명과 대화 내용을 프롬프트로 넘기고, Claude가 JSON으로
  {"tool_calls": [...]} 또는 {"reply": "..."} 를 답하게 한다.
- 도구 실행은 지금처럼 agent.py 루프의 파이썬 코드가 한다. 그래서 배시 보안 문제가 없다.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

PROTOCOL = """

## 응답 형식 (반드시 지킬 것)
너는 아래 '사용 가능한 도구'를 직접 실행할 수 없다. 도구가 필요하면 호출 요청을 JSON으로 내면
시스템이 실행하고 결과를 대화에 붙여 다시 보여 준다.
답은 JSON 객체 하나만 출력한다. 앞뒤에 설명, 코드블록 표시(```)를 붙이지 않는다.
- 도구를 호출할 때: {"tool_calls": [{"name": "도구이름", "args": {...}}]}
  서로 의존하지 않는 도구는 한 번에 여러 개 넣는다.
- 사용자에게 답할 때: {"reply": "사용자에게 보여 줄 문장"}
"""


def _cli_path() -> str:
    custom = os.getenv("CLAUDE_CLI_PATH")
    if custom:
        return custom
    found = shutil.which("claude")
    if found:
        return found
    win = Path(os.path.expanduser("~")) / ".local" / "bin" / "claude.exe"  # Windows 기본 설치 위치
    if win.exists():
        return str(win)
    raise RuntimeError("claude 명령을 찾을 수 없습니다. Claude Code CLI를 설치하거나 .env에 CLAUDE_CLI_PATH를 지정하세요.")


def _simplify(prop: dict) -> dict:
    """JSON 스키마를 짧게 줄인다 (title 제거, Optional 의 null 분기 제거)."""
    prop = {k: v for k, v in prop.items() if k not in ("title", "default")}
    if "anyOf" in prop:
        branches = [b for b in prop.pop("anyOf") if b.get("type") != "null"]
        if len(branches) == 1:
            prop.update(branches[0])
        else:
            prop["anyOf"] = branches
    return prop


def _tool_specs(tools) -> str:
    specs = []
    for t in tools:
        schema = t.tool_call_schema.model_json_schema() if hasattr(t, "tool_call_schema") else {}
        specs.append({
            "name": t.name,
            "description": t.description,
            "args": {k: _simplify(v) for k, v in schema.get("properties", {}).items()},
            "required": schema.get("required", []),
        })
    return "\n".join(json.dumps(s, ensure_ascii=False) for s in specs)


def _transcript(messages) -> str:
    lines = []
    for m in messages:
        if isinstance(m, SystemMessage):
            continue
        if isinstance(m, HumanMessage):
            lines.append(f"[사용자]\n{m.content}")
        elif isinstance(m, AIMessage):
            if m.tool_calls:
                calls = [{"name": c["name"], "args": c["args"]} for c in m.tool_calls]
                lines.append(f"[어시스턴트: 도구 호출]\n{json.dumps(calls, ensure_ascii=False)}")
            elif m.content:
                lines.append(f"[어시스턴트]\n{m.content}")
        elif isinstance(m, ToolMessage):
            lines.append(f"[도구 결과]\n{m.content}")
    return "\n\n".join(lines)


def _extract_json(text: str) -> dict | None:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except ValueError:
            return None
    return None


def write_system_prompt(folder: str | Path, system: str) -> str:
    """시스템 프롬프트를 파일로 저장해 --system-prompt-file 로 넘긴다.
    Windows 에서 npm 으로 설치한 claude 는 claude.CMD 로 실행되는데, 이때 여러 줄 인자는
    첫 줄에서 잘린다. 그래서 --system-prompt 로 넘기면 행동 원칙이 대부분 빠진다."""
    path = Path(folder) / "system_prompt.txt"
    path.write_text(system, encoding="utf-8")
    return str(path)


def _run_cli(cli: str, model: str, system: str, prompt: str, timeout: int) -> str:
    """내장 도구를 모두 끈 채 `claude -p` 를 한 번 실행하고 결과 글을 돌려준다."""
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)  # 구독 로그인으로 실행되게 한다
    with tempfile.TemporaryDirectory(prefix="settle_") as tmp:
        cmd = [
            cli, "-p",
            "--output-format", "json",
            "--tools", "",
            "--system-prompt-file", write_system_prompt(tmp, system),
            "--model", model,
            "--no-session-persistence",
            "--strict-mcp-config",
        ]
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            encoding="utf-8", timeout=timeout, env=env,
        )
    try:
        outer = json.loads(proc.stdout)
    except ValueError:
        raise RuntimeError(f"claude CLI 오류 (코드 {proc.returncode}): {(proc.stderr or proc.stdout).strip()[:500]}") from None
    if outer.get("is_error") or proc.returncode != 0:
        msg = outer.get("result") or proc.stderr.strip()
        if "login" in str(msg).lower():
            msg = f"{msg} → 터미널에서 claude 를 실행해 로그인하세요."
        raise RuntimeError(f"claude CLI 오류: {msg}")
    return outer.get("result") or ""


def run_cli_text(system: str, prompt: str) -> str:
    """도구 없이 글만 받을 때 (화면 문구 번역 등)."""
    return _run_cli(_cli_path(), os.getenv("CLAUDE_CLI_MODEL", "sonnet"), system, prompt,
                    int(os.getenv("CLAUDE_CLI_TIMEOUT", "120")))


class ClaudeCLIModel:
    """invoke(messages) -> AIMessage. agent.py 루프가 기대하는 형태를 흉내 낸다."""

    def __init__(self, tools):
        self.tools = tools
        self.tool_names = {t.name for t in tools}
        self.cli = _cli_path()
        self.model = os.getenv("CLAUDE_CLI_MODEL", "sonnet")
        self.timeout = int(os.getenv("CLAUDE_CLI_TIMEOUT", "120"))

    def invoke(self, messages):
        system = next((m.content for m in messages if isinstance(m, SystemMessage)), "")
        prompt = (
            "## 사용 가능한 도구\n" + _tool_specs(self.tools)
            + "\n\n## 지금까지의 대화\n" + _transcript(messages)
            + "\n\n위 대화의 다음 차례다. 응답 형식에 맞는 JSON 하나만 출력하라."
        )
        text = _run_cli(self.cli, self.model, system + PROTOCOL, prompt, self.timeout)

        data = _extract_json(text)
        if not isinstance(data, dict):
            return AIMessage(text)  # 형식을 안 지키면 그냥 답장으로 취급
        calls = [
            {"name": c["name"], "args": c.get("args") or {}, "id": f"cli_{uuid.uuid4().hex[:8]}", "type": "tool_call"}
            for c in data.get("tool_calls") or []
            if isinstance(c, dict) and c.get("name") in self.tool_names
        ]
        if calls:
            return AIMessage("", tool_calls=calls)
        return AIMessage(str(data.get("reply") or text))
