# 경남 이주민 능동 케어 에이전트

다국어 기반 정착 로드맵 안내 AI 에이전트 · 제4회 경남 AI·SW 경진대회 (사회문제 해결형 AI Agent, 대학부 duo)

## 구조

```
settle-agent/
├─ backend/                  Python · FastAPI · LangChain · Claude
│  ├─ app/
│  │  ├─ main.py             API (/api/chat, /api/briefing, /api/i18n, /api/files ...)
│  │  ├─ agent.py            도구 호출 루프 + 시스템 프롬프트 + 능동 브리핑(6시간 제한)
│  │  ├─ llm.py              LLM 제공자 선택 (.env 의 LLM_PROVIDER)
│  │  ├─ mock_llm.py         키 없이 개발할 때 쓰는 규칙 기반 가짜 에이전트 (ko/en/vi)
│  │  ├─ claude_cli_llm.py   Claude Code CLI 로 판단만 받는 모드 (개발용)
│  │  ├─ claude_agent_llm.py Claude Code 가 MCP 로 도구를 직접 실행하는 모드 (개발용)
│  │  ├─ mcp_server.py       claude_agent 모드용 MCP 서버 (도구 7개 노출)
│  │  ├─ translate.py        화면 문구 AI 자동 번역 + 캐시
│  │  ├─ memory.py           사용자별 상태(프로필·로드맵·D-day·대화) JSON 저장
│  │  └─ tools/
│  │     ├─ __init__.py      LangChain 도구 등록 (에이전트가 고르는 목록)
│  │     ├─ profile.py       save_profile          온보딩 정보 저장
│  │     ├─ roadmap.py       build_roadmap 등       규칙 기반 정착 로드맵
│  │     ├─ programs.py      search_programs       지원사업 DB 검색
│  │     ├─ risk.py          score_risk            정착 안정도 채점 기준
│  │     ├─ dday.py          set_dday_reminder     체류 종료일 D-day
│  │     └─ document.py      generate_application_doc  신청서 초안 docx
│  ├─ data/
│  │  ├─ programs.json       팀 조사 지원사업 DB (현재 예시 2건 → 20건 이상으로 교체)
│  │  └─ i18n/               AI 번역된 화면 문구 캐시 (en/ja/zh, 원본 해시별)
│  └─ tests/                 도구·mock·번역·CLI 테스트 (정량 목표 증빙용)
└─ frontend/                 React (Vite)
   └─ src/
      ├─ App.jsx             채팅 + 로드맵 패널 + 에이전트 작업 기록 패널, 라이트/다크 모드
      ├─ Emblems.jsx         태극기(국기법 비율) · 경상남도 강조 지도 SVG
      ├─ assets/koreaMap.js  대한민국 시·도 경계 단순화 경로 (자동 생성)
      ├─ i18n.js             화면 문구 원본(한국어). 영어·일본어·중국어는 AI 자동 번역
      └─ api.js
```

## 실행

### 백엔드

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
set PYTHONUTF8=1                # Windows: requirements.txt 의 한글 주석 때문에 필요 (macOS/Linux 는 생략)
pip install -r requirements.txt
copy .env.example .env          # LLM_PROVIDER 와 키 설정 (아래 표)
uvicorn app.main:app --reload --port 8000
```

`.env` 의 `LLM_PROVIDER` 로 LLM을 고릅니다. 자세한 내용은 [FREE_MODE.md](FREE_MODE.md).

| 모드 | 용도 |
|---|---|
| `anthropic` | **시연·정량 목표 측정용.** Claude API + LangChain tool calling (계획서 구조). `ANTHROPIC_API_KEY` 필요 |
| `mock` | 키 없이 화면·흐름 개발. 규칙 기반이라 자유 질문 불가, 화면 번역 안 됨 |
| `claude_agent` / `claude_cli` | 로그인한 Claude Code 구독으로 개발·테스트. 한 턴 10~20초 이상 걸려 응답 시간 측정에는 쓰지 않음 |
| `gemini` / `ollama` | 무료 LLM으로 실제 대화 확인 |

`.env` 를 바꾸면 uvicorn 을 재시작해야 합니다. 서버 터미널과 `http://localhost:8000/api/health` 에서 현재 모드를 확인할 수 있습니다.

### 프론트엔드

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

### 테스트

```bash
cd backend
python -m pytest -q             # Windows: 25 passed, 3 skipped (가짜 CLI 테스트는 macOS/Linux 전용)
```

## 에이전트 동작 방식

1. 사용자가 자기 언어로 상황을 말한다.
2. Claude가 정보를 `save_profile`로 저장하고, 빠진 항목을 되묻는다.
3. `score_risk` → 기준 미달이면 멘토·상담 연계를 먼저 제안한다.
4. `build_roadmap` → 단계별로 `search_programs`를 실행해 실제 지원사업을 연결한다.
5. 신청 의사가 있으면 `generate_application_doc`으로 초안 docx를 만든다.
6. 재방문 시 `/api/briefing`이 D-day와 남은 단계를 근거로 에이전트가 먼저 안내한다. 같은 사용자에게는 6시간에 한 번만 하고, 시연할 때는 `/api/briefing/{id}?force=true` 로 강제할 수 있다.

정확해야 하는 계산(로드맵 규칙, 점수, 날짜, 문서 채움)은 코드가 담당하고, LLM은 대화·판단·설명·다국어를 담당한다.

### 다국어

- **대화**: 에이전트가 사용자가 쓴 언어로 답한다 (베트남어 등 화면 선택지에 없는 언어도 가능).
- **화면 문구**: 한국어 / English / 日本語 / 中文(简体). `i18n.js` 의 한국어 원본만 관리하고, 다른 언어는 `/api/i18n` 이 현재 LLM으로 번역해 `backend/data/i18n/` 에 저장한다. 원본을 고치면 다음에 자동으로 다시 번역된다. 번역에 실패하거나 mock 모드면 한국어로 보인다.

### 맥락 추론과 평가

에이전트는 키워드가 아니라 말의 맥락으로 숨은 필요를 판단하고(`note_situation`), 그 판단을 근거 문장과 함께 기억해 다음 대화·재방문 때 다시 쓴다. 화면의 "에이전트가 이해한 상황" 패널에 판단과 근거가 보인다.

`backend/eval/` 에 간접 표현 평가 세트 100개(간접 표현 40, 여러 턴 결합 20, 함정·부정 20, 다국어 10, 필요 없음 10)와 키워드 방식 비교 실행기가 있다.

```bash
cd backend
python -m eval.run_eval --mode keyword   # 키워드 방식만 (즉시)
python -m eval.run_eval --mode both      # 키워드 vs 에이전트 (.env 의 LLM_PROVIDER 사용)
```

결과는 `eval/results/` 에 Markdown 표(완료보고서용)와 JSON(사례별 판단·답장 전체)으로 저장된다.

## 팀 작업 TODO

- [ ] (조환성) `data/programs.json` 예시 2건 삭제, 실제 조사 사업 20건 이상 입력 (`source_url`, `checked_at` 필수)
- [ ] (정태현) `tools/roadmap.py` 규칙·문구를 조사 결과에 맞게 수정
- [ ] (정태현) `tools/risk.py` 채점 기준 확정 → 발표자료에 표로 공개
- [ ] (조환성) `data/templates/korean_class_application.docx` 팀 템플릿으로 교체 (`{{name}}` 등 자리표시자 유지). 지금은 없어서 코드가 기본 양식을 자동 생성함
- [ ] (조환성) AI 번역된 화면 문구(`backend/data/i18n/*.json`) 대조 확인. 고칠 곳은 한국어 원본을 다듬거나 캐시 파일을 직접 수정
- [ ] 테스트 케이스 추가 후 결과를 완료보고서에 표로 첨부
- [x] FIXES.md 0~9번 코드 수정 (하얀 화면, 채점 미완료 판정, 지역명 정규화, 빈 응답·기록 순서 정리, 파일명 정리, D-day 라벨, 로드맵 다국어, 브리핑 6시간 제한·기록 복원, 도구 동시 호출 프롬프트)
- [x] LLM 제공자 선택 기능 병합 시 되돌아간 FIXES 3·4·6·8·9번 다시 반영 (빈 응답 대체, 기록 병합, D-day 라벨, 브리핑 6시간 제한·force, 프롬프트 규칙)
- [x] Windows 에서 claude CLI 시스템 프롬프트가 첫 줄만 전달되던 문제 수정 (`--system-prompt-file`)
- [ ] (FIXES 4번) `anthropic` 모드로 "대화 → 새로고침(브리핑) → 다시 대화" 오류 없는지 확인
- [ ] (FIXES 9번) `anthropic` 모드로 시연 시나리오 3회 실행해 `elapsed_ms` 표 정리 (참고: `claude_agent` 모드에서 로드맵 생성 한 턴 20.3초, 도구 9회)
- [ ] (FIXES 9번 검토, 팀 결정 필요) `build_roadmap`이 단계별 지원사업을 함께 붙여 반환하도록 할지
- [ ] 시연 시나리오 1~6단계를 베트남어로 끝까지 한 번 성공 (`anthropic` 모드)

## 출처 및 AI 활용 (별지2 작성용 메모)

| 항목 | 내용 |
|---|---|
| LLM | Anthropic Claude (API, 시연용). 개발 중에는 Claude Code CLI(구독)로도 실행 |
| 프레임워크 | LangChain (langchain-core, langchain-anthropic), FastAPI, React, Vite, python-docx, MCP(claude_agent 개발 모드) |
| AI 코딩 도구 | 프로젝트 뼈대 생성, 기능 추가·버그 수정(LLM 제공자 선택, 화면 디자인, 라이트/다크 모드, 자동 번역 등)에 Claude Code 사용 |
| AI 생성 콘텐츠 | 화면 문구 영어·일본어·중국어 번역을 Claude로 자동 생성 (`backend/data/i18n/`). 간접 표현 평가 세트 100문장 초안을 Claude Code로 작성 (`backend/eval/cases.jsonl`, 팀 검토 필요) |
| 데이터 | 지원사업: 팀이 경남 시·군 홈페이지에서 직접 조사 (각 항목 source_url 참조) |
| 지도 | 대한민국 시·도 경계: [southkorea/southkorea-maps](https://github.com/southkorea/southkorea-maps) (KOSTAT 2013 행정구역, 단순화). 독도 위치는 좌표로 직접 표시 |
| 태극기 | 「대한민국국기법」 시행령의 비율에 따라 SVG로 직접 작도 |

## 유의사항

본 서비스는 법률·체류 자격에 대한 판단을 하지 않으며, 공식 기관 안내로 연결합니다. 신청서는 초안이며 실제 제출은 사용자가 직접 합니다.
