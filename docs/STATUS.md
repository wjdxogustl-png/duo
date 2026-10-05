# 개발 현황

> 기준: 2026-10-05 (개발 7일차 / 9.29 ~ 10.6), GitHub `taehyeon` 브랜치
> `main` 의 내용은 모두 `taehyeon` 에 포함되어 있다. 그 위에 여러 턴 결합 개선, 변경 파이프라인, holdout 평가, 액션 카드, 지원사업 DB 26건을 더했다.

## 한눈에 보기

| 항목 | 상태 |
|---|---|
| 백엔드 (FastAPI) | 동작 |
| 프론트엔드 (React/Vite) | 동작, 빌드 정상 |
| 자동 테스트 | 61 통과 · 5 건너뜀 (macOS/Linux 전용 가짜 CLI 테스트) |
| 에이전트 도구 | 9개 (액션 카드 `suggest_actions` 추가) |
| 화면 언어 | 5개 (한국어 · English · Tiếng Việt · 日本語 · 中文) |
| 간접 표현 평가 | 키워드 59% → 에이전트 98% (`claude_agent`, 100문항). **처음 보는 999문항(holdout)은 아직 측정 전** |
| 지원사업 DB | 26건 (웹 확인, 전화 확인 전) |
| 신청서 초안 | 모든 지원사업 대상, 화면에서 고침 → Word·복사, 고유식별정보 자동 삭제 |
| `anthropic` 모드 (시연·정량 측정용) | **API 키 없어 미검증** |

## 브랜치 이력

```
350eb31  병합 후 수정 (베트남어 복구, 패널 다국어, 채팅 스크롤, 이 문서)  ← 현재
e7be94a  Merge origin/taehyeon
├─ main     : claude_agent 안정화, README 정리, 문서 docs/ 이동
└─ taehyeon : 디자인 개편(태극기·지도), 라이트/다크, 화면 AI 번역, 영어 화면,
              맥락 추론 에이전트(note_situation), 간접 표현 평가 세트·결과
```

- 원격: https://github.com/wjdxogustl-png/duo — `main`, `taehyeon`, `CHS`(병합 전 `main` 사본)
- 병합 충돌 2건 해결
  - `backend/app/agent.py`: 양쪽 프롬프트 규칙을 모두 유지 (질문 최대 2개·도구 실제 호출·마크다운 금지 + DB에 없으면 공식 상담 창구 안내·`{context}` 상황 기억)
  - `README.md`: main 의 소개·기술 스택 + taehyeon 의 상세 구조·LLM 모드·평가·TODO·출처 통합

## 구현된 기능

### 에이전트 도구 (8개)
| 도구 | 역할 |
|---|---|
| `save_profile` | 온보딩 정보 저장, 빠진 항목 되묻기 |
| `score_risk` | 정착 안정도 채점 (기준 미달 시 멘토·상담 먼저) |
| `build_roadmap` / `update_roadmap_step` | 규칙 기반 정착 로드맵 생성·단계 완료 처리 |
| `search_programs` | 지원사업 DB 검색 (출처 포함) |
| `set_dday_reminder` | 체류 종료일 D-day |
| `draft_application` | 지원사업 신청서 초안 (화면에서 고침, 고유식별정보 차단, docx 내려받기) |
| `note_situation` | 맥락으로 판단한 숨은 필요를 근거 문장과 함께 기억 (taehyeon 신규) |

### API
`/api/chat`, `/api/briefing/{id}` (재방문 능동 브리핑, 6시간 제한, `?force=true`), `/api/state/{id}` (조회·초기화), `/api/programs`, `/api/files/{name}`, `/api/i18n`, `/api/health`

### LLM 제공자 (`backend/.env` 의 `LLM_PROVIDER`)
`mock` · `claude_agent` · `claude_cli` · `gemini` · `ollama` · `anthropic` — 현재 로컬 설정은 `claude_agent`

### 화면
- 채팅 + 오른쪽 패널 4개: 경남 지도, 에이전트가 이해한 상황, 나의 정착 로드맵(D-day), 에이전트 작업 기록
- 태극기·대한민국 지도(경남 강조), 라이트/다크 모드

## 병합 후 수정 (`350eb31`)

| 문제 | 수정 | 파일 |
|---|---|---|
| 병합 후 언어 선택에서 베트남어가 사라짐 | 언어 5개로 복구, 백엔드 AI 번역 대상에도 `vi` 추가 | `frontend/src/i18n.js`, `backend/app/translate.py` |
| 언어를 바꿔도 패널이 한국어로 남음 (mock 모드에서는 AI 번역이 안 돼 화면 전체가 한국어) | 5개 언어 번역을 코드에 직접 넣고, 빠진 키만 AI 번역으로 채움. 로드맵 단계·분류, 상황 분류·급함, 작업 기록 도구 이름·시각까지 언어 따라 바뀜 | `frontend/src/i18n.js`, `frontend/src/App.jsx` |
| 채팅이 많으면 스크롤 없이 말풍선이 겹침 | 말풍선 축소 방지, 대화창 높이 고정, 긴 단어 줄바꿈 | `frontend/src/styles.css` |

언어를 바꿔도 그대로인 것: 이미 주고받은 대화, 상황 패널의 설명·근거 문장(에이전트가 쓴 글), 작업 기록의 입력·결과 데이터.

## 평가 결과 (`backend/eval/results/20261004_133119.md`)

| 유형 | 키워드 방식 | 에이전트 (`claude_agent`) |
|---|---|---|
| 간접표현 | 22/40 (55%) | 39/40 (98%) |
| 여러턴결합 | 14/20 (70%) | 20/20 (100%) |
| 함정·부정 | 8/20 (40%) | 19/20 (95%) |
| 다국어 | 6/10 (60%) | 10/10 (100%) |
| 필요없음 | 9/10 (90%) | 10/10 (100%) |
| **전체** | **59%** | **98%** |

- 에이전트 평균 응답 10.9초, 오류 0건. 처음 결과(`20261002_164437.md`)는 93%였고, 여러 턴 결합(75%)을 고쳐 98%가 됐다
- 주의: 98%는 이 100문항을 보고 프롬프트를 고친 뒤의 점수다. 그 뒤로 액션 카드 규칙도 프롬프트에 더해졌다. 발표에 쓸 점수는 현재 프롬프트로 holdout 999문항을 처음부터 다시 재서 정한다

## 정량 목표 대비

| 목표 | 현재 | 상태 |
|---|---|---|
| 로드맵 생성 10초 이내 | `claude_agent` 한 턴 20.3초 (도구 9회). `anthropic` 모드 측정 안 함 | 미측정 |
| 지원사업 DB 20건 이상 | 26건 | 달성 (전화 확인 남음) |
| 신청서 입력값 반영 정확도 100% | 화면에서 고친 값이 Word 파일에 그대로 들어가는지 자동 테스트(`test_draft.py`) | 달성 |

## 남은 일

**마감 전 필수 (10/5 ~ 10/6)**
- [x] 병합 후 수정분 커밋, GitHub `main` 반영
- [x] `backend/data/programs.json` 실제 운영 사업 26건 (`source_url`, `checked_at`, `verification`)
- [ ] (조환성) DB 사업 전화 확인, 번호가 다른 2건(`note`) 정리
- [ ] `anthropic` 모드로 시연 시나리오 3회 실행, `elapsed_ms` 표 정리 (10초 목표)
- [ ] 현재 프롬프트로 holdout 999문항 처음부터 다시 측정 (`eval/results/_progress_cases_holdout_claude_agent.jsonl` 은 옛 프롬프트 기준이라 지우고 시작)
- [ ] 시연 시나리오 1~6단계 베트남어로 끝까지 1회 성공
- [ ] 시연영상(3분), 개발완료보고서, AI Agent 기술설명서, 발표자료(10장), 별지2

**품질**
- [ ] 화면 번역 대조 (en/vi/ja/zh). 병합 후 새로 넣은 문구(상황 패널, 도구 이름 등)는 검토 필요
- [ ] (정태현) `tools/roadmap.py` 규칙·문구를 조사 결과에 맞게 수정
- [ ] (정태현) `tools/risk.py` 채점 기준 확정 → 발표자료에 표로 공개
- [ ] `anthropic` 모드로 "대화 → 새로고침(브리핑) → 다시 대화" 오류 확인 (FIXES 4번)
- [ ] (팀 결정) `build_roadmap` 이 단계별 지원사업을 함께 반환하도록 할지 (FIXES 9번)
- [ ] 평가 세트 100문장 팀 검토 (`backend/eval/cases.jsonl`)

## 실행

```bash
# 백엔드
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000   # .env 를 바꾸면 재시작

# 프론트엔드
cd frontend
npm run dev                                 # http://localhost:5173

# 테스트
cd backend
python -m pytest -q
```
