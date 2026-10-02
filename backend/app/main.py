"""FastAPI 진입점.

실행: (backend 폴더에서) uvicorn app.main:app --reload --port 8000
"""
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import agent, memory  # noqa: E402
from .tools.dday import compute_dday  # noqa: E402
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


@app.post("/api/chat")
def chat(req: ChatRequest):
    return agent.run(req.user_id, req.message, req.language)


@app.get("/api/briefing/{user_id}")
def briefing(user_id: str, language: str = "ko", force: bool = False):
    """재방문 시 프론트가 기록 복원 뒤 호출. 프로필이 없거나 최근 6시간 안에 브리핑했으면 briefing=None.
    시연용: ?force=true 면 시간 제한 없이 브리핑."""
    return {"briefing": agent.briefing(user_id, language, force)}


@app.get("/api/state/{user_id}")
def state(user_id: str):
    s = memory.load(user_id)
    return {
        **{k: s[k] for k in ("profile", "roadmap", "dday", "history")},
        "dday_label": compute_dday(s["dday"])["label"] if s["dday"] else None,
    }


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
