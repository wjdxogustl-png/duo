# 경남 정착 도우미

> 경남 이주민 능동 케어 에이전트 — 다국어 기반 정착 로드맵 안내 AI Agent

## 팀 정보

- **팀명**: Duo (창신대학교)
- **과제명**: 경남 이주민 능동 케어 에이전트
- **팀장**: 정태현
- **팀원**: 조환성
- **참가 분야**: 2026 제4회 경남 AI·SW 경진대회 · 사회문제 해결형 AI Agent · 대학부
- **수행기간**: 2026년 9월 29일 ~ 2026년 10월 6일

## 주요 기능

핵심기능 4가지로 묶었습니다.

**1. 숨은 필요를 읽는 다국어 상담**
- 한국어·영어·베트남어·일본어·중국어로 말하면 필요한 정보를 저장하고 빠진 것만 되묻습니다
- "이번 달 고향에 못 보냈어요"처럼 돌려 말해도 숨은 필요를 근거 문장과 함께 기억합니다 (`note_situation`)
- 폭력·임금체불·생명 위험처럼 급한 상황이면 지원사업보다 공식 상담 창구(112·119·1366·1350 등)를 먼저 내밉니다

**2. 맞춤 정착 로드맵**
- 정착 안정도를 진단하고, 기준에 못 미치면 멘토·상담 연결을 먼저 제안합니다
- 체류 기간, 자녀, 직업 등에 맞춰 해야 할 일을 순서대로 만들고 완료를 기록합니다
- 정보가 바뀌면 안정도·로드맵·지원사업을 코드가 다시 계산하고 검증합니다

**3. 지원사업·상담 창구 연결과 실행 지원**
- 로드맵 단계마다 경남 시·군 지원사업(26건)을 출처와 함께 찾아 줍니다
- 액션 카드: 에이전트가 판단한 다음 행동(신청서 만들기, 상담 창구 연락, 출처 열기)을 답장 아래 버튼으로 먼저 내밉니다. 상담 창구 카드는 번호를 보여 주고, 누르면 연락 전 준비할 것·통화할 때 할 말·다음 단계를 안내하며, 고른 창구는 다시 내밀지 않습니다
- 신청서 초안: 에이전트가 아는 정보로 미리 채우고, 사용자가 화면에서 고친 뒤 Word로 내려받거나 복사해 직접 제출합니다. 칸 이름·도움말·지운 항목 안내는 화면 언어로 보여 주고(다른 언어일 때는 한국어 칸 이름을 함께 표시), 칸 안의 값은 기관 제출용이라 한국어로 둡니다. 희망 시간 칸에는 지원사업의 운영 일정을 힌트로 보여 줍니다

**4. 먼저 챙기는 능동 케어**
- 체류 종료일을 D-day로 등록하고 알림 시점을 안내합니다
- 다시 방문하면 D-day와 남은 단계를 에이전트가 먼저 브리핑합니다

화면 오른쪽 **에이전트 작업 기록**과 **에이전트가 이해한 상황** 패널에서 에이전트가 무엇을 이해했고 어떤 도구를 왜 호출했는지 그대로 볼 수 있습니다. 고유식별정보는 신청서 초안에서 자동으로 지우고, 입력창 아래에 저장 위치·삭제 방법을 안내합니다.

## 동작 방식

```
사용자 입력 → save_profile (정보 저장·되묻기) → score_risk (안정도 진단)
          → build_roadmap (로드맵) → search_programs (지원사업 연결)
          → draft_application (신청서 초안) · set_dday_reminder (D-day)
```

정확해야 하는 계산(로드맵 규칙, 점수, 날짜, 문서 채움)은 코드 도구가 맡고, LLM은 대화·판단·도구 선택·다국어 설명을 맡습니다.

## 프로젝트 구조

```
Duo/
├─ backend/                  Python · FastAPI · LangChain · Claude
│  ├─ app/
│  │  ├─ main.py             API (/api/chat, /api/briefing, /api/i18n, /api/files, /api/hotlines ...)
│  │  ├─ agent.py            도구 호출 루프 + 시스템 프롬프트 + 능동 브리핑(6시간 제한)
│  │  ├─ llm.py              LLM 제공자 선택 (.env 의 LLM_PROVIDER)
│  │  ├─ mock_llm.py         키 없이 개발할 때 쓰는 규칙 기반 가짜 에이전트 (ko/en/vi)
│  │  ├─ claude_cli_llm.py   Claude Code CLI 로 판단만 받는 모드 (참고용)
│  │  ├─ claude_agent_llm.py Claude Code 가 MCP 로 도구를 직접 실행하는 모드 (개발·시연·평가)
│  │  ├─ mcp_server.py       claude_agent 모드용 MCP 서버 (도구 9개 노출)
│  │  ├─ translate.py        화면 문구 AI 자동 번역 + 캐시
│  │  ├─ memory.py           사용자별 상태(프로필·로드맵·D-day·대화) JSON 저장
│  │  └─ tools/
│  │     ├─ __init__.py      LangChain 도구 등록 (에이전트가 고르는 목록)
│  │     ├─ profile.py       save_profile          온보딩 정보 저장
│  │     ├─ roadmap.py       build_roadmap 등       규칙 기반 정착 로드맵
│  │     ├─ programs.py      search_programs       지원사업 DB 검색
│  │     ├─ risk.py          score_risk            정착 안정도 채점 기준
│  │     ├─ dday.py          set_dday_reminder     체류 종료일 D-day
│  │     ├─ draft.py         draft_application     신청서 초안 (화면에서 고침, 고유식별정보 차단, docx)
│  │     ├─ situation.py     note_situation        맥락으로 판단한 숨은 필요 기억
│  │     ├─ actions.py       suggest_actions       다음 행동 카드 (번호·주소는 DB·공식 창구만 허용, 방금 고른 창구는 다시 내밀지 않음)
│  │     └─ hotlines.py      공식 상담 창구 목록 읽기 (카드 검증·시스템 프롬프트가 함께 사용)
│  ├─ data/
│  │  ├─ programs.json       경남 지원사업 DB 26건 (공식 페이지·기사로 확인, 출처·확인일 포함)
│  │  ├─ hotlines.json       공식 상담 창구 8곳 (번호·지원 언어·운영 시간·연결할 상황·출처·확인일)
│  │  └─ i18n/               AI 번역된 화면 문구 캐시 (en/ja/zh, 원본 해시별)
│  ├─ eval/                  간접 표현 평가 세트 100개 + 처음 보는 holdout 999개 + 키워드 방식 비교 실행기
│  └─ tests/                 도구·mock·번역·CLI 테스트 (정량 목표 증빙용)
├─ frontend/                 React (Vite)
│  └─ src/
│     ├─ App.jsx             채팅, 액션 카드, 신청서 초안 편집, 상황·로드맵·작업 기록 패널, 라이트/다크 모드
│     ├─ Emblems.jsx         태극기(국기법 비율) · 경상남도 강조 지도 SVG
│     ├─ assets/koreaMap.js  대한민국 시·도 경계 단순화 경로 (자동 생성)
│     ├─ i18n.js             화면 문구 5개 언어 (한국어 원본 + en/vi/ja/zh 번역, 빠진 키만 AI 번역)
│     └─ api.js
└─ docs/                     개발 방향, 팀 작업 메모, 무료 개발 모드 안내
```

## 기술 스택

| 구분 | 기술 |
|---|---|
| 백엔드 | Python, FastAPI, Uvicorn, Pydantic |
| AI 에이전트 | Anthropic Claude (Claude Code + MCP, `claude_agent` 모드), LangChain (도구 호출) |
| 데이터 | JSON 파일 DB (사용자 상태, 지원사업) |
| 문서 생성 | python-docx |
| 프론트엔드 | React 18, Vite 5 |
| 테스트 | pytest |

## 구현 현황

**완료**
- [x] 도구 9개와 API (채팅, 능동 브리핑, 상태 조회·초기화, 지원사업, 신청서 다운로드)
- [x] 다국어 채팅 화면, 로드맵·작업 기록 패널, 라이트·다크 모드
- [x] 사용자별 메모리와 재방문 브리핑 (6시간 간격)
- [x] LLM 제공자 전환, Claude Code를 MCP로 연결해 실제 도구 호출 확인
- [x] 규칙 기반 도구 자동 테스트
- [x] 액션 카드 (에이전트가 다음 행동을 버튼으로 제안)
- [x] 지원사업 DB 26건 (창원·김해·양산·진주·거제·경남 전체)
- [x] 위기 상황 상담 창구 8곳 (`data/hotlines.json`), 급한 상황엔 창구 카드를 지원사업보다 먼저
- [x] 상담 창구 카드: 번호 표시, 누르면 준비물·할 말·다음 단계 안내 (같은 카드는 다시 내밀지 않음)
- [x] 개인정보 안내 문구 (5개 언어)
- [x] 신청서 초안의 칸 이름·도움말·지운 항목 안내를 화면 언어로 표시, 운영 일정 힌트

**진행 중**
- [ ] 지원사업 DB 전화 확인 (번호가 출처마다 다른 2건은 `note` 참고), 통영·사천·밀양 등 나머지 시·군 추가
- [ ] 영어·베트남어 번역 대조
- [ ] 상담 창구 전화 확인 (1644-0644 이름·운영 시간, 1350 운영 시간·외국어 ARS)
- [ ] 베트남어 시연 시나리오 전체 확인, 응답 시간 측정 (목표 10초 이내)

## 실행 방법

**백엔드**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
set PYTHONUTF8=1                # Windows: requirements.txt 의 한글 주석 때문에 필요 (macOS/Linux 는 생략)
pip install -r requirements.txt
copy .env.example .env          # LLM_PROVIDER 와 키 설정 (아래 표)
uvicorn app.main:app --port 8000
```

Windows 에서 `--reload` 를 쓰면 코드 변경 후 재시작이 멈춰 예전 코드로 계속 도는 일이 있었습니다. 백엔드 코드를 고친 뒤에는 서버를 직접 다시 켜세요.

`.env` 의 `LLM_PROVIDER` 로 LLM을 고릅니다. 자세한 내용은 [FREE_MODE.md](docs/FREE_MODE.md).

| 모드 | 용도 |
|---|---|
| `claude_agent` | **개발·시연·평가에 사용.** 로그인한 Claude Code 구독으로 Claude 가 MCP 를 통해 도구를 직접 호출. 한 턴 12~20초 |
| `mock` | 키 없이 화면·흐름 개발. 규칙 기반이라 자유 질문 불가, 화면 번역 안 됨 |
| `claude_cli` | Claude 는 판단만 하고 도구 실행은 파이썬이 하는 방식. 느려서 참고용 |
| `anthropic` | 공개 서비스로 운영할 때 전환할 방식. Claude API + LangChain tool calling, `ANTHROPIC_API_KEY` 필요 (대회 기간에는 미사용) |
| `gemini` / `ollama` | 무료 LLM으로 실제 대화 확인 |

`.env` 를 바꾸면 uvicorn 을 재시작해야 합니다. 서버 터미널과 `http://localhost:8000/api/health` 에서 현재 모드를 확인할 수 있습니다.

**프론트엔드**
```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

**테스트**
```bash
cd backend
python -m pytest -q             # 89 passed (Windows 에서는 84 passed, 5 skipped: 가짜 CLI 테스트는 macOS/Linux 전용)
```

## 에이전트 동작 방식

1. 사용자가 자기 언어로 상황을 말한다.
2. Claude가 정보를 `save_profile`로 저장하고, 빠진 항목을 되묻는다.
3. `score_risk` → 기준 미달이면 멘토·상담 연계를 먼저 제안한다.
4. `build_roadmap` → 단계별로 `search_programs`를 실행해 실제 지원사업을 연결한다.
5. 신청 의사가 있으면 `draft_application`으로 신청서 초안을 만든다. 사용자는 화면에서 빈칸(연락처 등)을 채우고 고친 뒤 Word로 내려받거나 복사해 직접 제출한다.
6. 재방문 시 `/api/briefing`이 D-day와 남은 단계를 근거로 에이전트가 먼저 안내한다. 같은 사용자에게는 6시간에 한 번만 하고, 시연할 때는 `/api/briefing/{id}?force=true` 로 강제할 수 있다.

정확해야 하는 계산(로드맵 규칙, 점수, 날짜, 문서 채움)은 코드가 담당하고, LLM은 대화·판단·설명·다국어를 담당한다.

### 다국어

- **대화**: 에이전트가 사용자가 쓴 언어로 답한다 (화면 선택지에 없는 언어도 가능).
- **화면 문구**: 한국어 / English / Tiếng Việt / 日本語 / 中文(简体). 로드맵·상황·작업 기록 패널까지 `i18n.js` 의 `TRANSLATIONS` 에 직접 번역해 두어 mock 모드에서도 바뀐다. 한국어 원본(`KO`)에 새 키를 넣고 번역을 빠뜨리면 `/api/i18n` 이 현재 LLM으로 그 부분을 채워 `backend/data/i18n/` 에 저장하고, 그것도 안 되면 한국어로 보인다.

### 맥락 추론과 평가

에이전트는 키워드가 아니라 말의 맥락으로 숨은 필요를 판단하고(`note_situation`), 그 판단을 근거 문장과 함께 기억해 다음 대화·재방문 때 다시 쓴다. 화면의 "에이전트가 이해한 상황" 패널에 판단과 근거가 보인다.

`backend/eval/` 에 간접 표현 평가 세트 100개(간접 표현 40, 여러 턴 결합 20, 함정·부정 20, 다국어 10, 필요 없음 10)와 키워드 방식 비교 실행기가 있다.

```bash
cd backend
python -m eval.run_eval --mode keyword   # 키워드 방식만 (즉시)
python -m eval.run_eval --mode both      # 키워드 vs 에이전트 (.env 의 LLM_PROVIDER 사용)
```

결과는 `eval/results/` 에 Markdown 표(완료보고서용)와 JSON(사례별 판단·답장 전체)으로 저장된다.

100문항에 맞춰 프롬프트를 고쳤기 때문에, 그 효과가 진짜인지는 처음 보는 사례로 따로 잰다. `eval/cases_holdout.jsonl`(999개)은 에이전트 프롬프트와 기존 사례를 보지 않는 모델이 만들고 블라인드로 다시 채점한 세트다 (`eval/generate_cases.py`). 사용량 한도에 걸리면 채점하지 않고 멈추며, 같은 명령을 다시 실행하면 이어서 한다.

```bash
python -m eval.run_eval --mode agent --cases cases_holdout.jsonl
```

## 팀 작업 TODO

- [x] `data/programs.json` 실제 운영 사업 26건 입력 (`source_url`, `checked_at`, `verification` 포함)
- [ ] (조환성) DB 사업 전화 확인 후 `verification` 갱신, 비어 있는 비용·반별 시간 보충
- [ ] (정태현) `tools/roadmap.py` 규칙·문구를 조사 결과에 맞게 수정
- [ ] (정태현) `tools/risk.py` 채점 기준 확정 → 발표자료에 표로 공개
- [ ] (조환성) AI 번역된 화면 문구(`backend/data/i18n/*.json`) 대조 확인. 고칠 곳은 한국어 원본을 다듬거나 캐시 파일을 직접 수정
- [ ] 테스트 케이스 추가 후 결과를 완료보고서에 표로 첨부
- [x] FIXES.md 0~9번 코드 수정 (하얀 화면, 채점 미완료 판정, 지역명 정규화, 빈 응답·기록 순서 정리, 파일명 정리, D-day 라벨, 로드맵 다국어, 브리핑 6시간 제한·기록 복원, 도구 동시 호출 프롬프트)
- [x] LLM 제공자 선택 기능 병합 시 되돌아간 FIXES 3·4·6·8·9번 다시 반영 (빈 응답 대체, 기록 병합, D-day 라벨, 브리핑 6시간 제한·force, 프롬프트 규칙)
- [x] Windows 에서 claude CLI 시스템 프롬프트가 첫 줄만 전달되던 문제 수정 (`--system-prompt-file`)
- [ ] (FIXES 4번) `claude_agent` 모드로 "대화 → 새로고침(브리핑) → 다시 대화" 오류 없는지 확인
- [ ] (FIXES 9번) `claude_agent` 모드로 시연 시나리오 3회 실행해 `elapsed_ms` 표 정리 (참고: 로드맵 생성 한 턴 20.3초, 도구 9회. 10초를 넘으면 원인과 개선 방향을 보고서에 기재)
- [ ] (FIXES 9번 검토, 팀 결정 필요) `build_roadmap`이 단계별 지원사업을 함께 붙여 반환하도록 할지
- [ ] 시연 시나리오 1~6단계를 베트남어로 끝까지 한 번 성공 (`claude_agent` 모드)

## 출처 및 AI 활용 (출처·AI 활용 신고서 작성용 메모)

| 항목 | 내용 |
|---|---|
| LLM | Anthropic Claude. 개발·시연·평가 모두 Claude Code(구독)를 MCP 로 연결한 `claude_agent` 모드로 수행. 공개 서비스로 운영할 때는 Claude API(`anthropic` 모드)로 전환하도록 설계 |
| 프레임워크 | LangChain (langchain-core, langchain-anthropic), FastAPI, React, Vite, python-docx, MCP(`claude_agent` 모드의 도구 연결) |
| AI 코딩 도구 | 프로젝트 뼈대 생성, 기능 추가·버그 수정(LLM 제공자 선택, 화면 디자인, 라이트/다크 모드, 자동 번역 등)에 Claude Code 사용 |
| AI 생성 콘텐츠 | 화면 문구 영어·일본어·중국어 번역을 Claude로 자동 생성 (`backend/data/i18n/`). 간접 표현 평가 세트 100문장 초안을 Claude Code로 작성 (`backend/eval/cases.jsonl`, 팀 검토 필요) |
| 데이터 | 지원사업: 팀이 경남 시·군 홈페이지에서 직접 조사 (각 항목 source_url 참조). 상담 창구: 기관 공식 페이지에서 확인 (`data/hotlines.json` 의 source_url·checked_at) |
| 지도 | 대한민국 시·도 경계: [southkorea/southkorea-maps](https://github.com/southkorea/southkorea-maps) (KOSTAT 2013 행정구역, 단순화). 독도 위치는 좌표로 직접 표시 |
| 태극기 | 「대한민국국기법」 시행령의 비율에 따라 SVG로 직접 작도 |

## 신청서 초안의 개인정보·법적 안전장치

학생 프로젝트로서 지킬 수 있는 범위를 코드로 강제한다 (`backend/app/tools/draft.py`).

| 원칙 | 구현 |
|---|---|
| 대신 제출하지 않음 | 초안을 화면에 보여 주기만 한다. 제출은 사용자가 기관에 직접 한다 |
| 고유식별정보를 받지 않음 (개인정보 보호법 제24조) | 외국인등록번호·주민등록번호·여권번호·계좌번호로 보이는 값은 저장 전에 지우고 사용자에게 알린다 |
| 최소 수집 | 연락처는 채팅으로 묻지 않고 사용자가 초안에 직접 적는다 |
| 지어내지 않음 | 프로필에 없는 칸은 비워 둔다. 신청 동기는 사용자가 말한 사실로만 쓴다 |
| 알리고 지울 수 있음 | AI가 만든 초안이며 내용이 AI(Claude)에 전달된다는 안내를 화면과 파일에 표시. '처음부터'로 초안과 파일까지 삭제 |
| 공식 서식을 베끼지 않음 | 기관 서식 대신 공통 항목만 담은 표 한 장으로 내려받는다 |

## 유의사항

본 서비스는 법률·체류 자격에 대한 판단을 하지 않으며, 공식 기관 안내로 연결합니다. 신청서는 초안이며 실제 제출은 사용자가 직접 합니다.
