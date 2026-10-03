"""화면 문구 자동 번역: 캐시, 형식 검사, 번역 불가 시 원본 사용."""
import json

import pytest

from app import llm, translate

SOURCE = {"title": "경남 정착 도우미", "steps": {"bank_phone": "은행 계좌·휴대전화 개통"}}


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(translate, "I18N_DIR", tmp_path / "i18n")


def test_translates_once_then_uses_cache(monkeypatch):
    calls = []
    out = {"title": "慶南定住サポーター", "steps": {"bank_phone": "銀行口座の開設"}}
    monkeypatch.setattr(llm, "complete_text", lambda *a, **kw: calls.append(1) or "```json\n" + json.dumps(out) + "\n```")

    first = translate.translate_ui("ja", SOURCE)
    second = translate.translate_ui("ja", SOURCE)
    assert first == second == {"strings": out, "translated": True}
    assert len(calls) == 1


def test_wrong_shape_falls_back_to_source(monkeypatch):
    monkeypatch.setattr(llm, "complete_text", lambda *a, **kw: json.dumps({"title": "庆南定居助手"}))  # steps 빠짐
    assert translate.translate_ui("zh", SOURCE) == {"strings": SOURCE, "translated": False}
    assert not (translate.I18N_DIR).exists()  # 잘못된 번역은 저장하지 않는다


def test_mock_and_unknown_language_return_source(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    assert translate.translate_ui("ja", SOURCE) == {"strings": SOURCE, "translated": False}
    assert translate.translate_ui("fr", SOURCE) == {"strings": SOURCE, "translated": False}
