# 무료 개발 모드 안내

API 결제 없이 개발·테스트할 수 있도록 LLM 제공자를 고르는 스위치를 넣었습니다. `backend/.env`의 `LLM_PROVIDER` 한 줄만 바꾸면 됩니다.

| 모드 | 비용 | 준비물 | 용도 |
|---|---|---|---|
| `mock` | 무료 | 없음 | 매일 개발·화면 확인·테스트 (기본값) |
| `claude_agent` | 구독에 포함 | Claude Code CLI 로그인 | Claude Code가 도구를 직접 실행 (영상 방식) |
| `claude_cli` | 구독에 포함 | Claude Code CLI 로그인 | Claude는 판단만, 실행은 파이썬 |
| `gemini` | 무료 구간 | Google AI Studio 키 | 실제 LLM으로 E2E 확인, 시연 |
| `ollama` | 무료 | PC에 Ollama 설치, 성능 좋은 PC | 인터넷·키 없이 실제 LLM |
| `anthropic` | 유료 | Claude 크레딧 + 키 | 공개 서비스로 운영할 때 |

키가 비어 있거나 예시 값(`sk-ant-api03-...`)이면 500 오류 대신 자동으로 mock으로 내려갑니다. 서버를 켤 때 터미널에 `LLM 제공자: mock`처럼 현재 모드가 찍히고, `http://localhost:8000/api/health`에서도 확인할 수 있습니다.

## 추천 사용 순서

1. **개발 기간 내내 `mock`**으로 작업합니다. 비용 0원, 응답도 즉시 옵니다.
2. 기능이 모이면 **`claude_agent`(또는 `claude_cli`, `gemini`)로 하루 몇 번** 실제 대화를 돌려 프롬프트와 도구 설명을 다듬습니다.
3. **시연영상·발표**는 `claude_agent`(Claude)로 합니다. 이 프로젝트는 개발·시연·평가를 모두 이 모드로 했습니다.

## 1. mock 모드 (키 없음)

`.env`에 `LLM_PROVIDER=mock`만 두고 서버를 켜면 됩니다.

정해진 규칙으로 실제 에이전트처럼 움직입니다. 메시지에서 정보를 읽어 `save_profile`을 호출하고, 빠진 항목을 하나씩 되묻고(위험도 채점 항목까지), 다 모이면 `score_risk` → `build_roadmap` → 단계별 `search_programs`를 호출해 로드맵을 답합니다. "신청서 만들어 주세요" → 이름·연락처 확인 → docx 생성, 날짜를 말하면 D-day 저장, "은행 계좌 만들었어요"처럼 말하면 단계 완료 처리, 새로고침하면 능동 브리핑까지 됩니다. 한국어·영어·베트남어를 자동으로 알아봅니다.

도구는 진짜로 실행되므로 로드맵 패널, 작업 기록 패널, docx 다운로드를 모두 확인할 수 있습니다. 다만 판단은 키워드 매칭이라 자유로운 질문("날씨 어때?")은 이해하지 못합니다. **시연에는 쓰지 마세요.** 심사 기준인 "AI Agent다운 판단"이 아닙니다.

시나리오 전체를 자동으로 확인하는 테스트도 있습니다.
```bash
cd backend
python -m pytest -q tests/test_mock_agent.py
```

## 2. claude_agent 모드 (Claude Code가 직접 도구 실행)

Claude Code를 우리 도구(현재 9개)에 **MCP로 직접 연결**해서, Claude가 도구를 고르고 실행하고 결과를 보고 다음 행동을 정하는 과정을 스스로 반복한 뒤 최종 답만 돌려줍니다. 터미널에 데이터를 연결해 두고 Claude에게 명령하는 방식과 같은 구조예요.

1. 터미널에서 `claude`가 로그인돼 있는지 확인합니다.
2. `.env`에 `LLM_PROVIDER=claude_agent`를 넣고 uvicorn을 재시작합니다. 터미널에 `LLM 제공자: claude_agent`가 찍히면 준비 완료.

동작 방식:
- 백엔드가 메시지마다 `claude -p`를 실행하면서 MCP 설정 파일을 넘깁니다. Claude Code가 `app/mcp_server.py`를 띄워 도구 목록을 받고, 필요한 도구를 직접 호출합니다.
- MCP 서버는 같은 가상환경의 파이썬으로 실행되고 같은 `data/` 폴더를 쓰므로, 화면의 로드맵·D-day가 그대로 반영됩니다. 도구 호출 기록도 작업 기록 패널에 표시됩니다.
- **Claude Code의 내장 도구(Bash, 파일 읽기·쓰기)는 모두 꺼져 있고**, settle 서버의 도구만 허용됩니다. 그 밖의 권한 요청은 자동 거부되므로 채팅 내용 때문에 PC에서 명령이 실행되지 않습니다.

MCP 서버만 따로 확인하고 싶으면 VS Code의 Claude Code에 붙여 볼 수도 있어요. `backend` 폴더에서 `claude mcp add settle -- python -m app.mcp_server`를 실행하면 Claude Code 대화창에서 우리 도구를 직접 불러 볼 수 있습니다. (이때는 `SETTLE_USER_ID`를 지정하지 않으면 `default` 사용자 데이터에 저장됩니다.)

## 3. claude_cli 모드 (Claude는 판단만)

VS Code·터미널에서 쓰는 Claude Code에 로그인돼 있으면 그 구독으로 실제 Claude를 씁니다. 개인 개발·테스트용이에요.

1. 터미널에서 `claude --version`이 되는지 확인하고, 처음이면 `claude`를 실행해 로그인합니다. (PATH 문제로 명령을 못 찾아도, Windows 기본 설치 위치 `%USERPROFILE%\.local\bin\claude.exe`는 자동으로 찾습니다.)
2. `.env`에 `LLM_PROVIDER=claude_cli`를 넣고 uvicorn을 재시작합니다. 터미널에 `LLM 제공자: claude_cli`가 찍히면 준비 완료입니다.

동작 방식: 백엔드가 `claude -p`를 실행할 때 **Claude Code의 내장 도구(Bash, 파일 편집 등)를 모두 끄고**(`--tools ""`), 우리 도구의 설명과 대화 내용을 넘깁니다. Claude는 JSON으로 "어떤 도구를 어떤 값으로 부를지" 또는 "답장"만 돌려주고, 도구 실행은 지금처럼 파이썬 코드가 합니다. 그래서 채팅 내용 때문에 PC에서 명령이 실행될 위험이 없습니다.

알아 둘 점:
- **느립니다.** 호출할 때마다 CLI를 새로 띄우므로 한 번에 몇 초씩 걸리고, 메시지 하나에 3~5번 부르면 답이 오기까지 수십 초가 걸릴 수 있어요. 응답 시간 측정(10초 목표)은 이 모드로 하지 마세요.
- 구독 플랜의 `claude -p` 사용량은 대화형 사용 한도와 별도인 **월간 Agent SDK 크레딧**에서 차감됩니다. 남은 양은 claude.ai 설정에서 확인하세요.
- 모델은 `CLAUDE_CLI_MODEL`로 바꿀 수 있습니다(`sonnet`, `opus` 같은 별칭 또는 전체 모델 이름).
- "Not logged in" 오류가 화면에 뜨면 터미널에서 `claude`를 실행해 다시 로그인하세요. uvicorn은 로그인한 같은 Windows 계정으로 실행해야 합니다.
- 이 방식은 본인이 직접 테스트하는 용도입니다. 다른 사람이 쓰는 서비스로 공개할 때는 API 키 방식(`anthropic`)으로 바꿔야 합니다.

## 4. gemini 모드 (무료 구간)

1. https://aistudio.google.com 에 Google 계정으로 로그인 → **Get API key**로 키를 만듭니다. 카드 등록 없이 무료 구간을 쓸 수 있습니다.
2. 가상환경을 켠 상태로 `pip install langchain-google-genai`
3. `.env`를 이렇게 바꾸고 서버를 재시작합니다.
   ```
   LLM_PROVIDER=gemini
   GOOGLE_API_KEY=발급받은_키
   GEMINI_MODEL=gemini-flash-latest
   ```

주의할 점:
- 무료 구간은 **분당 요청 수가 10회 안팎으로 작습니다.** 이 에이전트는 메시지 하나에 LLM을 3~5번 부르므로, 빠르게 연달아 보내면 `429` 오류가 날 수 있어요. 잠시 기다렸다 다시 보내면 됩니다. 한도와 사용 가능한 모델은 수시로 바뀌니 AI Studio에서 확인하세요. 모델 이름 오류가 나면 AI Studio 모델 목록에 있는 Flash 계열 이름으로 `GEMINI_MODEL`을 바꾸면 됩니다.
- 무료 구간에서는 **입력 내용이 Google 제품 개선에 쓰일 수 있습니다.** 실제 개인정보 대신 가상 페르소나로만 테스트하세요(공고문 권장 사항과도 같습니다).

## 5. ollama 모드 (내 PC)

1. https://ollama.com 에서 설치 → 터미널에서 `ollama pull qwen3:8b`
2. `pip install langchain-ollama`
3. `.env`에 `LLM_PROVIDER=ollama`, `OLLAMA_MODEL=qwen3:8b`

완전 무료지만 GPU 메모리가 넉넉한 PC가 필요하고, 작은 모델은 도구 호출과 베트남어 품질이 떨어질 수 있습니다. 실습실 PC는 설치가 막히거나 재부팅 때 지워질 수 있어 권장하지 않습니다.

## 6. anthropic 모드 (Claude API)

`.env`에 `LLM_PROVIDER=anthropic`과 실제 `ANTHROPIC_API_KEY`를 넣습니다. 결제 화면의 자동 충전(Auto-reload)은 꺼 두세요.

## 이번에 바뀐 파일

| 파일 | 내용 |
|---|---|
| `backend/app/llm.py` (새 파일) | 제공자 스위치, 키 없으면 mock 자동 전환 |
| `backend/app/mock_llm.py` (새 파일) | 개발용 가짜 에이전트 |
| `backend/app/claude_cli_llm.py` (새 파일) | Claude Code CLI(`claude -p`) 연결 |
| `backend/app/claude_agent_llm.py` (새 파일) | Claude Code가 MCP로 도구를 직접 실행하는 모드 |
| `backend/app/mcp_server.py` (새 파일) | 도구를 MCP로 내보내는 서버 (추가 패키지 없음) |
| `backend/tests/test_claude_agent.py` (새 파일) | 가짜 CLI가 실제 MCP 서버를 띄워 도구를 호출하는 통합 검증 |
| `backend/tests/test_claude_cli.py` (새 파일) | 가짜 CLI로 JSON 주고받기 검증 |
| `backend/app/agent.py` | 모델 생성을 `llm.get_model()`로 교체, 대화 기록 정리(FIXES 4번), 빈 응답 방지(FIXES 3번), 응답에 `provider` 추가 |
| `backend/app/main.py` | 500 오류 때 원인을 화면에 표시, 시작 시 제공자 로그, `/api/health` |
| `backend/app/tools/document.py` | 신청서 파일명에 `_safe_id` 적용(FIXES 5번) |
| `backend/tests/test_mock_agent.py` (새 파일) | mock으로 시연 시나리오 전체 검증 |
| `backend/.env.example`, `backend/requirements.txt` | 제공자 설정 항목 추가 |

프론트엔드는 바뀐 것이 없습니다.

## 별지2(출처·AI 활용 신고서)에 적을 것

실제로 쓴 제공자만 적습니다. 이 프로젝트는 개발·시연·평가를 모두 Anthropic Claude 를 Claude Code(구독) + MCP 로 연결한 `claude_agent` 모드로 했고, mock(팀 자체 규칙 기반, AI 아님)은 화면 개발에만 썼습니다. 공개 서비스로 운영할 때는 Claude API(`anthropic` 모드)로 전환하도록 설계했다고 함께 적습니다.
