"""FastAPI 진입점.

실행: (backend 폴더에서) uvicorn app.main:app --reload --port 8000
"""
import json
import logging

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("settle-agent")

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import agent, llm, memory, translate  # noqa: E402
from .tools.dday import compute_dday  # noqa: E402
from .tools import draft  # noqa: E402
from .tools.hotlines import load_hotlines  # noqa: E402
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


class I18nRequest(BaseModel):
    language: str
    source: dict  # 프론트의 한국어 화면 문구 (원본)


@app.post("/api/i18n")
def i18n(req: I18nRequest):
    """화면 문구를 AI로 번역한다. 한 번 번역한 결과는 data/i18n 에 저장해 다시 쓴다."""
    if len(json.dumps(req.source, ensure_ascii=False)) > 20000:
        raise HTTPException(413, "화면 문구가 너무 깁니다.")
    try:
        return translate.translate_ui(req.language, req.source)
    except Exception as e:  # noqa: BLE001
        return _error(e)


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        return agent.run(req.user_id, req.message, req.language)
    except Exception as e:  # noqa: BLE001
        return _error(e)


@app.get("/api/briefing/{user_id}")
def briefing(user_id: str, language: str = "ko", force: bool = False):
    """재방문 시 프론트가 기록 복원 뒤 호출. 프로필이 없거나 최근 6시간 안에 브리핑했으면 briefing=None.
    시연용: ?force=true 면 시간 제한 없이 브리핑."""
    try:
        return {"briefing": agent.briefing(user_id, language, force)}
    except Exception as e:  # noqa: BLE001
        return _error(e)


@app.get("/api/state/{user_id}")
def state(user_id: str):
    s = memory.load(user_id)
    return {
        **{k: s[k] for k in ("profile", "roadmap", "dday", "history", "situations", "drafts")},
        "dday_label": compute_dday(s["dday"])["label"] if s["dday"] else None,
    }


@app.delete("/api/state/{user_id}")
def reset(user_id: str):
    memory.reset(user_id)
    return {"ok": True}


class DraftUpdate(BaseModel):
    values: dict[str, str]  # 칸 key → 사용자가 고친 값


@app.put("/api/drafts/{user_id}/{draft_id}")
def save_draft(user_id: str, draft_id: str, req: DraftUpdate):
    """화면에서 고친 신청서 초안을 저장한다. 고유식별정보는 지우고 removed_sensitive 로 알려 준다."""
    memory.current_user.set(user_id)
    try:
        return draft.update_draft(draft_id, req.values)
    except KeyError:
        raise HTTPException(404, "초안을 찾을 수 없습니다.")


@app.post("/api/drafts/{user_id}/{draft_id}/docx")
def draft_docx(user_id: str, draft_id: str):
    """저장된 초안을 Word 파일로 만든다. 제출은 사용자가 직접 한다."""
    memory.current_user.set(user_id)
    try:
        return draft.draft_docx(draft_id)
    except KeyError:
        raise HTTPException(404, "초안을 찾을 수 없습니다.")


@app.get("/api/programs")
def programs():
    return load_programs()


@app.get("/api/hotlines")
def hotlines():
    return load_hotlines()


@app.get("/api/files/{name}")
def download(name: str):
    path = (memory.OUTPUT_DIR / name).resolve()
    if path.parent != memory.OUTPUT_DIR.resolve() or not path.exists():
        raise HTTPException(404, "파일을 찾을 수 없습니다.")
    return FileResponse(path, filename=name)
