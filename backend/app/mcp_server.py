"""정착 도우미 도구들을 Claude Code에 연결하는 MCP 서버 (표준 입출력, 추가 패키지 없음).

claude_agent 모드에서 백엔드가 `claude -p --mcp-config ...`로 Claude Code를 실행하면,
Claude Code가 이 서버를 띄워 도구 목록을 받고, 필요할 때마다 직접 도구를 호출한다.

환경 변수
  SETTLE_USER_ID    : 어느 사용자의 데이터(프로필·로드맵)를 다룰지
  SETTLE_TRACE_FILE : 도구 호출 기록을 한 줄씩 남길 파일 (화면의 '에이전트 작업 기록'에 표시)
  (명령줄 인자 --user, --trace 로도 줄 수 있고, 인자가 우선한다)

직접 실행해 확인: (backend 폴더에서) python -m app.mcp_server
"""
import json
import os
import sys
import time

from . import memory
from .tools import ALL_TOOLS

TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}

PROTOCOL_VERSION = "2025-06-18"


def _tool_list() -> list[dict]:
    out = []
    for t in ALL_TOOLS:
        schema = t.tool_call_schema.model_json_schema()
        input_schema = {
            "type": "object",
            "properties": schema.get("properties", {}),
            "required": schema.get("required", []),
        }
        if "$defs" in schema:  # 중첩 스키마(suggest_actions 의 Action 등)가 $ref 로 가리키는 정의
            input_schema["$defs"] = schema["$defs"]
        out.append({"name": t.name, "description": t.description, "inputSchema": input_schema})
    return out


def _arg(name: str) -> str | None:
    """--user, --trace 명령줄 인자 (환경 변수가 전달되지 않는 환경 대비)."""
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


def _trace(entry: dict) -> None:
    path = _arg("--trace") or os.getenv("SETTLE_TRACE_FILE")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _call_tool(name: str, args: dict) -> tuple[str, bool]:
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return f"Error: 알 수 없는 도구 {name}", True
    started = time.perf_counter()
    try:
        result, is_error = tool.invoke(args or {}), False
    except Exception as e:  # noqa: BLE001  오류도 Claude에게 돌려줘 스스로 수습하게 한다
        result, is_error = f"Error: {type(e).__name__}: {e}", True
    ms = round((time.perf_counter() - started) * 1000)
    try:
        shown = json.loads(result)
    except (ValueError, TypeError):
        shown = result
    _trace({"tool": name, "args": args or {}, "result": shown, "ms": ms})
    return result, is_error


def handle(msg: dict) -> dict | None:
    """JSON-RPC 메시지 하나를 처리한다. 알림(id 없음)이면 None."""
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None
    if method == "initialize":
        client_ver = (msg.get("params") or {}).get("protocolVersion")
        result = {
            "protocolVersion": client_ver or PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "settle", "version": "1.0"},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": _tool_list()}
    elif method == "tools/call":
        p = msg.get("params") or {}
        text, is_error = _call_tool(p.get("name", ""), p.get("arguments") or {})
        result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"지원하지 않는 메서드: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> None:
    memory.current_user.set(_arg("--user") or os.getenv("SETTLE_USER_ID") or "default")
    stdin = open(sys.stdin.fileno(), "r", encoding="utf-8", closefd=False)
    stdout = open(sys.stdout.fileno(), "w", encoding="utf-8", closefd=False, newline="\n")
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        reply = handle(msg)
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()


if __name__ == "__main__":
    main()
