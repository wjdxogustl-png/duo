"""Claude Code가 직접 도구를 실행하며 한 턴을 끝내는 모드 (LLM_PROVIDER=claude_agent).

claude_cli 모드와의 차이
- claude_cli  : Claude는 판단만 하고, 도구 실행은 우리 파이썬 루프(agent.py)가 한다.
- claude_agent: Claude Code가 MCP 서버(app/mcp_server.py)로 도구 7개에 직접 연결되어,
                도구 선택·실행·결과 확인·다음 행동을 스스로 반복한 뒤 최종 답만 돌려준다.

안전장치
- Claude Code 내장 도구(Bash, 파일 읽기·쓰기 등)는 모두 끈다 (--tools "").
- 우리 MCP 서버의 도구만 허용하고 (--allowedTools mcp__settle), 그 외 권한 요청은 자동 거부한다.
- 구독 로그인으로 실행되도록 ANTHROPIC_API_KEY 는 넘기지 않는다.
"""
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .claude_cli_llm import _cli_path

BACKEND_DIR = Path(__file__).resolve().parents[1]
log = logging.getLogger("settle-agent")

AGENT_NOTE = """

## 도구 사용
너에게는 settle 서버의 도구 7개(mcp__settle__save_profile 등)가 연결되어 있다. 위 행동 원칙에 따라 직접 호출하라.
서로 의존하지 않는 도구는 한 번에 함께 호출하라.
모든 도구 실행을 마친 뒤, 사용자에게 보여 줄 최종 답장만 출력하라. 도구 이름이나 내부 과정은 답장에 쓰지 않는다.
"""


def _transcript(messages) -> str:
    lines = []
    for m in messages[:-1]:
        if isinstance(m, HumanMessage):
            lines.append(f"[사용자] {m.content}")
        elif isinstance(m, AIMessage) and m.content:
            lines.append(f"[어시스턴트] {m.content}")
    current = messages[-1].content
    if not lines:
        return current
    return "## 이전 대화\n" + "\n\n".join(lines) + "\n\n## 지금 사용자 메시지\n" + current


class ClaudeAgentRunner:
    """agent.py 가 run_turn(messages) 로 한 턴을 통째로 맡긴다."""

    def __init__(self, tools=None):
        self.cli = _cli_path()
        self.model = os.getenv("CLAUDE_CLI_MODEL", "sonnet")
        self.timeout = int(os.getenv("CLAUDE_CLI_TIMEOUT", "180"))

    def run_turn(self, messages, user_id: str) -> tuple[str, list[dict]]:
        system = next((m.content for m in messages if isinstance(m, SystemMessage)), "")
        convo = [m for m in messages if not isinstance(m, SystemMessage)]

        with tempfile.TemporaryDirectory(prefix="settle_") as tmp:
            trace_file = Path(tmp) / "trace.jsonl"
            config_file = Path(tmp) / "mcp.json"
            config_file.write_text(json.dumps({"mcpServers": {"settle": {
                "type": "stdio",
                "command": sys.executable,  # 지금 백엔드를 돌리는 가상환경의 파이썬
                "args": ["-m", "app.mcp_server", "--user", user_id, "--trace", str(trace_file)],
                "env": {
                    "SETTLE_USER_ID": user_id,
                    "SETTLE_TRACE_FILE": str(trace_file),
                    "PYTHONPATH": str(BACKEND_DIR),
                    "PYTHONIOENCODING": "utf-8",
                },
            }}}, ensure_ascii=False), encoding="utf-8")

            cmd = [
                self.cli, "-p",
                "--output-format", "stream-json", "--verbose",  # 연결 상태·도구 호출을 한 줄씩 받는다
                "--tools", "",
                "--mcp-config", str(config_file),
                "--strict-mcp-config",
                "--allowedTools", "mcp__settle",
                "--permission-prompts", "none",
                "--system-prompt", system + AGENT_NOTE,
                "--model", self.model,
                "--no-session-persistence",
            ]
            env = os.environ.copy()
            env.pop("ANTHROPIC_API_KEY", None)
            proc = subprocess.run(
                cmd, input=_transcript(convo), capture_output=True, text=True,
                encoding="utf-8", timeout=self.timeout, env=env, cwd=str(BACKEND_DIR),
            )

            return _parse_stream(proc, trace_file)


def _short(name: str) -> str:
    return name.split("__")[-1] if name.startswith("mcp__") else name


def _parse_stream(proc, trace_file: Path) -> tuple[str, list[dict]]:
    events = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
    result = next((e for e in reversed(events) if e.get("type") == "result"), None)
    if result is None:
        raise RuntimeError(f"claude CLI 오류 (코드 {proc.returncode}): {(proc.stderr or proc.stdout).strip()[:500]}")
    if result.get("is_error") or proc.returncode != 0:
        msg = result.get("result") or proc.stderr.strip()
        if "login" in str(msg).lower():
            msg = f"{msg} → 터미널에서 claude 를 실행해 로그인하세요."
        raise RuntimeError(f"claude CLI 오류: {msg}")

    # 1) MCP 서버가 실제로 붙었는지 확인한다. 안 붙었으면 Claude가 도구 없이 '했다'고 말하게 되므로 오류로 알린다.
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), None)
    if init is not None:
        servers = {m.get("name"): m.get("status") for m in init.get("mcp_servers") or []}
        log.info("claude_agent MCP 상태: %s", servers)
        if servers.get("settle") != "connected":
            raise RuntimeError(
                f"MCP 서버(settle) 연결 실패: 상태={servers.get('settle')}. "
                "backend 폴더에서 `python -m app.mcp_server` 를 실행해 오류가 나는지 확인하세요."
            )
    if result.get("permission_denials"):
        log.warning("claude_agent 권한 거부: %s", result["permission_denials"])

    # 2) 도구 호출 기록: MCP 서버가 남긴 파일(소요 시간 포함)을 우선, 없으면 스트림에서 복원한다.
    trace = []
    if trace_file.exists():
        for line in trace_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                trace.append(json.loads(line))
    if not trace:
        pending = {}
        for e in events:
            content = (e.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") == "tool_use":
                    pending[block.get("id")] = {"tool": _short(block.get("name", "")), "args": block.get("input") or {}, "result": None, "ms": 0}
                    trace.append(pending[block.get("id")])
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in pending:
                    c = block.get("content")
                    text = c if isinstance(c, str) else "".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
                    try:
                        pending[block["tool_use_id"]]["result"] = json.loads(text)
                    except ValueError:
                        pending[block["tool_use_id"]]["result"] = text
    log.info("claude_agent 도구 호출: %s", [t["tool"] for t in trace])
    return (result.get("result") or "").strip(), trace
