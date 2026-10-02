"""claude_agent 모드 통합 검증: 가짜 claude 명령이 --mcp-config 를 읽어 실제 MCP 서버를 띄우고
도구를 호출한다. 실제 Claude 대신 정해진 호출만 하므로 로그인이 필요 없다."""
import os
import sys

import pytest

from app import agent, memory

pytestmark = pytest.mark.skipif(os.name == "nt", reason="가짜 CLI 스크립트는 macOS/Linux 전용")

FAKE = r'''#!{python}
import json, os, subprocess, sys
args = sys.argv[1:]
assert args[args.index("--tools") + 1] == "", "내장 도구가 꺼져 있어야 한다"
assert args[args.index("--allowedTools") + 1] == "mcp__settle"
cfg = json.load(open(args[args.index("--mcp-config") + 1], encoding="utf-8"))["mcpServers"]["settle"]
sys.stdin.read()
srv = subprocess.Popen([cfg["command"], *cfg["args"]], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                       env={{**os.environ, **cfg["env"]}}, text=True, encoding="utf-8")
def rpc(i, method, params):
    srv.stdin.write(json.dumps({{"jsonrpc": "2.0", "id": i, "method": method, "params": params}}) + "\n")
    srv.stdin.flush()
    return json.loads(srv.stdout.readline())
rpc(1, "initialize", {{"protocolVersion": "2025-06-18", "capabilities": {{}}, "clientInfo": {{"name": "fake"}}}})
tools = [t["name"] for t in rpc(2, "tools/list", {{}})["result"]["tools"]]
assert "save_profile" in tools
rpc(3, "tools/call", {{"name": "save_profile", "arguments": {{"region": "김해", "months_in_korea": 2}}}})
srv.stdin.close(); srv.wait()
print(json.dumps({{"type": "result", "is_error": False, "result": "김해에 오신 지 2달이군요. 한국어는 어느 정도 하세요?"}}, ensure_ascii=False))
'''


@pytest.fixture
def fake_cli(tmp_path, monkeypatch):
    p = tmp_path / "claude"
    p.write_text(FAKE.format(python=sys.executable), encoding="utf-8")
    p.chmod(0o755)
    monkeypatch.setenv("LLM_PROVIDER", "claude_agent")
    monkeypatch.setenv("CLAUDE_CLI_PATH", str(p))
    uid = "pytest_claude_agent"
    yield uid
    f = memory.USERS_DIR / f"{uid}.json"  # MCP 서버는 별도 프로세스라 실제 데이터 폴더에 쓴다
    if f.exists():
        f.unlink()


def test_claude_agent_runs_tools_through_mcp(fake_cli):
    r = agent.run(fake_cli, "김해에 2달 살았어요")
    assert r["provider"] == "claude_agent"
    assert [c["tool"] for c in r["trace"]] == ["save_profile"]
    assert r["trace"][0]["result"]["profile"]["region"] == "김해"
    assert r["state"]["profile"]["months_in_korea"] == 2   # MCP 서버가 쓴 데이터를 백엔드가 읽는다
    assert "한국어" in r["reply"]
