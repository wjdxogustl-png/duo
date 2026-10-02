"""claude_cli 모드의 JSON 주고받기를 가짜 claude 명령으로 검증한다 (실제 로그인 불필요)."""
import json
import os
import sys

import pytest

from app import agent, memory

pytestmark = pytest.mark.skipif(os.name == "nt", reason="가짜 CLI 스크립트는 macOS/Linux 전용")

FAKE = r'''#!{python}
import sys, json
prompt = sys.stdin.read()
last = prompt.split("## 지금까지의 대화")[1].strip().split("\n\n[")[-1]
if "사용자]" in last[:6]:
    res = "```json\n" + json.dumps({{"tool_calls": [
        {{"name": "save_profile", "args": {{"region": "김해", "months_in_korea": 2}}}},
        {{"name": "없는도구", "args": {{}}}}]}}, ensure_ascii=False) + "\n```"
else:
    res = json.dumps({{"reply": "저장했어요. 한국어는 어느 정도 하세요?"}}, ensure_ascii=False)
print(json.dumps({{"type": "result", "is_error": False, "result": res}}, ensure_ascii=False))
'''

NOT_LOGGED_IN = r'''#!{python}
import json, sys
sys.stdin.read()
print(json.dumps({{"type": "result", "is_error": True, "result": "Not logged in · Please run /login"}}))
sys.exit(1)
'''


def _script(tmp_path, body):
    p = tmp_path / "claude"
    p.write_text(body.format(python=sys.executable), encoding="utf-8")
    p.chmod(0o755)
    return str(p)


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "claude_cli")
    monkeypatch.setattr(memory, "USERS_DIR", tmp_path / "users")


def test_tool_call_then_reply(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CLI_PATH", _script(tmp_path, FAKE))
    r = agent.run("u", "김해에 2달 살았어요")
    assert r["provider"] == "claude_cli"
    assert [c["tool"] for c in r["trace"]] == ["save_profile"]  # 없는 도구는 걸러진다
    assert r["state"]["profile"]["region"] == "김해"
    assert "한국어" in r["reply"]


def test_not_logged_in_message(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CLI_PATH", _script(tmp_path, NOT_LOGGED_IN))
    with pytest.raises(RuntimeError, match="로그인"):
        agent.run("u", "안녕하세요")
