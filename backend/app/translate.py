"""화면 고정 문구 자동 번역.

프론트는 한국어 문구(원본)만 관리하고, 다른 언어는 여기서 LLM으로 번역해 파일에 저장해 둔다.
원본이 바뀌면 해시가 달라져 새로 번역한다. mock 모드처럼 번역할 수 없으면 원본(한국어)을 돌려준다.
"""
import hashlib
import json
import logging
import threading

from . import llm
from .claude_cli_llm import _extract_json
from .memory import DATA_DIR

log = logging.getLogger("settle-agent")

I18N_DIR = DATA_DIR / "i18n"
TARGETS = {"ja": "일본어", "zh": "중국어 간체(简体中文)"}
_locks = {lang: threading.Lock() for lang in TARGETS}

SYSTEM = """너는 경상남도 이주민 정착 도우미 웹앱의 화면 문구를 번역하는 전문 번역가다.
규칙
- 입력 JSON의 키와 구조는 그대로 두고, 문자열 값만 {target}로 번역한다.
- 한국어가 서툰 이주민이 읽는다. 짧고 쉬운 표현을 쓴다. 버튼 문구는 짧게.
- 지명은 해당 언어의 관용 표기를 쓴다 (예: 경상남도 → 일본어 慶尚南道, 중국어 庆尚南道).
- 기관명, 전화번호, 숫자, 기호(·, …, ( ))는 의미에 맞게 유지한다.
- JSON 객체 하나만 출력한다. 설명이나 코드블록 표시(```)를 붙이지 않는다."""


def _same_shape(src, out) -> bool:
    if isinstance(src, dict):
        return isinstance(out, dict) and src.keys() == out.keys() and all(_same_shape(src[k], out[k]) for k in src)
    return isinstance(out, str) and bool(out.strip())


def _cache_path(lang: str, source: dict):
    digest = hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
    return I18N_DIR / f"{lang}-{digest}.json"


def translate_ui(lang: str, source: dict) -> dict:
    """{"strings": 번역된 문구, "translated": 번역 여부}"""
    if lang not in TARGETS:
        return {"strings": source, "translated": False}
    path = _cache_path(lang, source)
    with _locks[lang]:  # 같은 언어를 동시에 두 번 번역하지 않는다
        if path.exists():
            return {"strings": json.loads(path.read_text(encoding="utf-8")), "translated": True}
        text = llm.complete_text(
            SYSTEM.format(target=TARGETS[lang]),
            json.dumps(source, ensure_ascii=False, indent=1),
        )
        out = _extract_json(text) if text else None
        if not _same_shape(source, out):
            log.warning("화면 문구 %s 번역 실패: 형식이 원본과 다름 (원본을 그대로 사용)", lang)
            return {"strings": source, "translated": False}
        I18N_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        log.info("화면 문구 %s 번역 완료: %s", lang, path.name)
        return {"strings": out, "translated": True}
