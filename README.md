# 경남 이주민 능동 케어 에이전트

다국어 기반 정착 로드맵 안내 AI 에이전트 · 제4회 경남 AI·SW 경진대회 (사회문제 해결형 AI Agent, 대학부 duo)

## 구조

```
settle-agent/
├─ backend/                  Python · FastAPI · LangChain · Claude
│  ├─ app/
│  │  ├─ main.py             API (/api/chat, /api/briefing, /api/files ...)
│  │  ├─ agent.py            Claude 도구 호출 루프 + 시스템 프롬프트 + 능동 브리핑
│  │  ├─ memory.py           사용자별 상태(프로필·로드맵·D-day·대화) JSON 저장
│  │  └─ tools/
│  │     ├─ __init__.py      LangChain 도구 등록 (에이전트가 고르는 목록)
│  │     ├─ profile.py       save_profile          온보딩 정보 저장
│  │     ├─ roadmap.py       build_roadmap 등       규칙 기반 정착 로드맵
│  │     ├─ programs.py      search_programs       지원사업 DB 검색
│  │     ├─ risk.py          score_risk            정착 안정도 채점 기준
│  │     ├─ dday.py          set_dday_reminder     체류 종료일 D-day
│  │     └─ document.py      generate_application_doc  신청서 초안 docx
│  ├─ data/programs.json     팀 조사 지원사업 DB (현재 예시 2건 → 20건 이상으로 교체)
│  └─ tests/test_tools.py    규칙 기반 도구 테스트 (정량 목표 증빙용)
└─ frontend/                 React (Vite)
   └─ src/
      ├─ App.jsx             채팅 + 로드맵 패널 + 에이전트 작업 기록 패널
      ├─ i18n.js             화면 문구 (ko / en / vi)
      └─ api.js
```

## 실행

### 백엔드

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # .env 에 ANTHROPIC_API_KEY 입력
uvicorn app.main:app --reload --port 8000
```

### 프론트엔드

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

### 테스트

```bash
cd backend
python -m pytest -q
```

## 에이전트 동작 방식

1. 사용자가 자기 언어로 상황을 말한다.
2. Claude가 정보를 `save_profile`로 저장하고, 빠진 항목을 되묻는다.
3. `score_risk` → 기준 미달이면 멘토·상담 연계를 먼저 제안한다.
4. `build_roadmap` → 단계별로 `search_programs`를 실행해 실제 지원사업을 연결한다.
5. 신청 의사가 있으면 `generate_application_doc`으로 초안 docx를 만든다.
6. 재방문 시 `/api/briefing`이 D-day와 남은 단계를 근거로 에이전트가 먼저 안내한다.

정확해야 하는 계산(로드맵 규칙, 점수, 날짜, 문서 채움)은 코드가 담당하고, LLM은 대화·판단·설명·다국어를 담당한다.

## 팀 작업 TODO

- [ ] (조환성) `data/programs.json` 예시 2건 삭제, 실제 조사 사업 20건 이상 입력 (`source_url`, `checked_at` 필수)
- [ ] (정태현) `tools/roadmap.py` 규칙·문구를 조사 결과에 맞게 수정
- [ ] (정태현) `tools/risk.py` 채점 기준 확정 → 발표자료에 표로 공개
- [ ] (조환성) `data/templates/korean_class_application.docx` 팀 템플릿으로 교체 (`{{name}}` 등 자리표시자 유지)
- [ ] (조환성) `i18n.js` 번역 대조 확인
- [ ] 테스트 케이스 추가 후 결과를 완료보고서에 표로 첨부
- [x] FIXES.md 0~9번 코드 수정 (하얀 화면, 채점 미완료 판정, 지역명 정규화, 빈 응답·기록 순서 정리, 파일명 정리, D-day 라벨, 로드맵 다국어, 브리핑 6시간 제한·기록 복원, 도구 동시 호출 프롬프트) — 테스트 19개 통과
- [ ] (FIXES 4번) API 키로 "대화 → 새로고침(브리핑) → 다시 대화" 오류 없는지 확인 (`/api/briefing/{id}?force=true`로 브리핑 강제 가능)
- [ ] (FIXES 9번) 시연 시나리오 3회 실행해 `elapsed_ms` 표 정리
- [ ] (FIXES 9번 검토, 팀 결정 필요) `build_roadmap`이 단계별 지원사업을 함께 붙여 반환하도록 할지
- [ ] (조환성) `i18n.js`의 로드맵 단계·카테고리 영어·베트남어 번역 대조
- [ ] 시연 시나리오 1~6단계를 베트남어로 끝까지 한 번 성공

## 출처 및 AI 활용 (별지2 작성용 메모)

| 항목 | 내용 |
|---|---|
| LLM | Anthropic Claude (API) |
| 프레임워크 | LangChain (langchain-core, langchain-anthropic), FastAPI, React, Vite, python-docx |
| AI 코딩 도구 | 프로젝트 뼈대 생성에 Claude Code 사용 |
| 데이터 | 팀이 경남 시·군 홈페이지에서 직접 조사 (각 항목 source_url 참조) |

## 유의사항

본 서비스는 법률·체류 자격에 대한 판단을 하지 않으며, 공식 기관 안내로 연결합니다. 신청서는 초안이며 실제 제출은 사용자가 직접 합니다.
