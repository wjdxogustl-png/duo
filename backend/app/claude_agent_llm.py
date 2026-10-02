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
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .claude_cli_llm import _cli_path

BACKEND_DIR = Path(__file__).resolve().parents[1]

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
                "args": ["-m", "app.mcp_server"],
                "env": {
                    "SETTLE_USER_ID": user_id,
                    "SETTLE_TRACE_FILE": str(trace_file),
                    "PYTHONPATH": str(BACKEND_DIR),
                    "PYTHONIOENCODING": "utf-8",
                },
            }}}, ensure_ascii=False), encoding="utf-8")

            cmd = [
                self.cli, "-p",
                "--output-format", "json",
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

            try:
                outer = json.loads(proc.stdout)
            except ValueError:
                raise RuntimeError(f"claude CLI 오류 (코드 {proc.returncode}): {(proc.stderr or proc.stdout).strip()[:500]}") from None
            if outer.get("is_error") or proc.returncode != 0:
                msg = outer.get("result") or proc.stderr.strip()
                if "login" in str(msg).lower():
                    msg = f"{msg} → 터미널에서 claude 를 실행해 로그인하세요."
                raise RuntimeError(f"claude CLI 오류: {msg}")

            trace = []
            if trace_file.exists():
                for line in trace_file.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        trace.append(json.loads(line))
            return (outer.get("result") or "").strip(), trace
