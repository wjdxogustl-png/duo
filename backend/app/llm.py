"""LLM 제공자 선택.

.env 의 LLM_PROVIDER 로 고른다.
  mock      : 키 없이 무료. 정해진 규칙으로 도구를 호출하는 개발용 가짜 에이전트
  gemini    : Google AI Studio 무료 구간 (GOOGLE_API_KEY 필요, pip install langchain-google-genai)
  ollama    : 내 PC에서 오픈소스 모델 실행 (Ollama 설치 필요, pip install langchain-ollama)
  anthropic : Claude (ANTHROPIC_API_KEY 필요, 유료 크레딧)
  claude_cli: 로그인한 Claude Code CLI(claude -p)로 실행. Claude는 판단만, 도구 실행은 파이썬 (개인 테스트용)
  claude_agent: Claude Code가 MCP로 도구에 직접 연결되어 스스로 실행하며 한 턴을 끝냄 (개인 테스트용)

LLM_PROVIDER 를 비워 두면 Claude 키가 있으면 anthropic, 없으면 mock 으로 동작한다.
키가 비어 있거나 예시 값(sk-ant-api03-... 같은)이면 오류 대신 mock 으로 내려간다.
"""
import logging
import os

log = logging.getLogger("settle-agent")


def _real_key(name: str) -> str | None:
    v = (os.getenv(name) or "").strip().strip('"').strip("'")
    if not v or "..." in v or len(v) < 20:
        return None
    return v


def provider_name() -> str:
    p = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if not p:
        p = "anthropic" if _real_key("ANTHROPIC_API_KEY") else "mock"
    if p == "anthropic" and not _real_key("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY 가 비어 있거나 예시 값이라 mock 모드로 실행합니다.")
        return "mock"
    if p == "gemini" and not (_real_key("GOOGLE_API_KEY") or _real_key("GEMINI_API_KEY")):
        log.warning("GOOGLE_API_KEY 가 없어 mock 모드로 실행합니다.")
        return "mock"
    return p


def _chat_model(p: str):
    """도구를 붙이기 전의 LangChain 채팅 모델 (anthropic / gemini / ollama)."""
    if p == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
            max_tokens=1500,
            temperature=0.2,
        )

    if p == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as e:
            raise RuntimeError("pip install langchain-google-genai 를 먼저 실행하세요.") from e
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
            temperature=0.2,
            google_api_key=_real_key("GOOGLE_API_KEY") or _real_key("GEMINI_API_KEY"),
        )

    if p == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as e:
            raise RuntimeError("pip install langchain-ollama 를 먼저 실행하세요.") from e
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
            temperature=0.2,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

    raise ValueError(f"알 수 없는 LLM_PROVIDER: {p} (mock / claude_agent / claude_cli / gemini / ollama / anthropic 중 하나)")


def get_model(tools):
    """(도구가 연결된 모델, 제공자 이름)을 돌려준다."""
    p = provider_name()

    if p == "mock":
        from .mock_llm import MockAgentModel
        return MockAgentModel(), p

    if p == "claude_agent":
        from .claude_agent_llm import ClaudeAgentRunner
        return ClaudeAgentRunner(tools), p

    if p == "claude_cli":
        from .claude_cli_llm import ClaudeCLIModel
        return ClaudeCLIModel(tools), p

    return _chat_model(p).bind_tools(tools), p


def complete_text(system: str, prompt: str, max_tokens: int = 4000) -> str | None:
    """도구 없이 글만 생성한다(화면 문구 번역 등). mock 모드면 None."""
    p = provider_name()
    if p == "mock":
        return None
    if p in ("claude_cli", "claude_agent"):
        from .claude_cli_llm import run_cli_text
        return run_cli_text(system, prompt)

    from langchain_core.messages import HumanMessage, SystemMessage
    model = _chat_model(p)
    if p == "anthropic":
        model.max_tokens = max_tokens
    content = model.invoke([SystemMessage(system), HumanMessage(prompt)]).content
    if isinstance(content, list):
        content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content
