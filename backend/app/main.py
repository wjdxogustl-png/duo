"""FastAPI 진입점.

실행: (backend 폴더에서) uvicorn app.main:app --reload --port 8000
"""
import logging

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("settle-agent")

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import agent, llm, memory  # noqa: E402
from .tools.programs import load_programs  # noqa: E402

app = FastAPI(title="경남 이주민 능동 케어 에이전트")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    user_id: str
    message: str
    language: str = "ko"


def _error(e: Exception) -> JSONResponse:
    """500 오류 때 화면에 원인이 보이도록 오류 종류와 메시지를 돌려준다."""
    log.exception("요청 처리 중 오류")
    return JSONResponse(status_code=500, content={"detail": f"{type(e).__name__}: {e}"})


@app.on_event("startup")
def show_provider():
    log.info("LLM 제공자: %s", llm.provider_name())


@app.get("/api/health")
def health():
    return {"ok": True, "provider": llm.provider_name()}


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        return agent.run(req.user_id, req.message, req.language)
    except Exception as e:  # noqa: BLE001
        return _error(e)


@app.get("/api/briefing/{user_id}")
def briefing(user_id: str, language: str = "ko"):
    """재방문 시 프론트가 가장 먼저 호출. 저장된 프로필이 없으면 briefing=None."""
    try:
        return {"briefing": agent.briefing(user_id, language)}
    except Exception as e:  # noqa: BLE001
        return _error(e)


@app.get("/api/state/{user_id}")
def state(user_id: str):
    s = memory.load(user_id)
    return {k: s[k] for k in ("profile", "roadmap", "dday", "history")}


@app.delete("/api/state/{user_id}")
def reset(user_id: str):
    memory.reset(user_id)
    return {"ok": True}


@app.get("/api/programs")
def programs():
    return load_programs()


@app.get("/api/files/{name}")
def download(name: str):
    path = (memory.OUTPUT_DIR / name).resolve()
    if path.parent != memory.OUTPUT_DIR.resolve() or not path.exists():
        raise HTTPException(404, "파일을 찾을 수 없습니다.")
    return FileResponse(path, filename=name)
