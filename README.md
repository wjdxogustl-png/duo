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

1. 다국어 대화 온보딩 — 한국어·영어·베트남어·일본어·중국어로 말하면 필요한 정보를 저장하고 빠진 것만 되묻습니다
2. 정착 안정도 진단 — 점수가 기준에 못 미치면 멘토·상담 연결을 먼저 제안합니다
3. 맞춤 정착 로드맵 — 체류 기간, 자녀, 직업 등에 맞춰 해야 할 일을 순서대로 만듭니다
4. 경남 지원사업 연결 — 로드맵 단계마다 시·군 지원사업을 출처와 함께 찾아 줍니다
5. 신청서 초안 작성 — 한국어 교실 신청서를 docx로 만들어 내려받을 수 있습니다
6. 능동 케어 — 다시 방문하면 체류 종료 D-day와 남은 단계를 에이전트가 먼저 안내합니다

화면 오른쪽 **에이전트 작업 기록**에서 에이전트가 어떤 도구를 왜 호출했는지 그대로 볼 수 있습니다.

## 동작 방식

```
사용자 입력 → save_profile (정보 저장·되묻기) → score_risk (안정도 진단)
          → build_roadmap (로드맵) → search_programs (지원사업 연결)
          → generate_application_doc (신청서) · set_dday_reminder (D-day)
```

정확해야 하는 계산(로드맵 규칙, 점수, 날짜, 문서 채움)은 코드 도구가 맡고, LLM은 대화·판단·도구 선택·다국어 설명을 맡습니다.

## 프로젝트 구조

```
Duo/
├── backend/          ← 백엔드 (Python / FastAPI / LangChain)
│   ├── app/          ← API, 에이전트, 도구 7개, MCP 서버, LLM 제공자 전환
│   ├── data/         ← 지원사업 DB (programs.json)
│   └── tests/        ← 자동 테스트 (pytest)
├── frontend/         ← 프론트엔드 (React / Vite)
└── docs/             ← 개발 방향, 팀 작업 메모, 무료 개발 모드 안내
```

## 기술 스택

| 구분 | 기술 |
|---|---|
| 백엔드 | Python, FastAPI, Uvicorn, Pydantic |
| AI 에이전트 | LangChain (도구 호출), Anthropic Claude, Claude Code + MCP |
| 데이터 | JSON 파일 DB (사용자 상태, 지원사업) |
| 문서 생성 | python-docx |
| 프론트엔드 | React 18, Vite 5 |
| 테스트 | pytest |

## 구현 현황

**완료**
- [x] 도구 7개와 API (채팅, 능동 브리핑, 상태 조회·초기화, 지원사업, 신청서 다운로드)
- [x] 다국어 채팅 화면, 로드맵·작업 기록 패널, 라이트·다크 모드
- [x] 사용자별 메모리와 재방문 브리핑 (6시간 간격)
- [x] LLM 제공자 전환, Claude Code를 MCP로 연결해 실제 도구 호출 확인
- [x] 규칙 기반 도구 자동 테스트

**진행 중**
- [ ] 지원사업 DB 20건 이상 (현재 형식 예시 2건)
- [ ] 신청서 docx 팀 템플릿 적용
- [ ] 영어·베트남어 번역 대조
- [ ] 베트남어 시연 시나리오 전체 확인, 응답 시간 측정 (목표 10초 이내)

## 실행 방법

**백엔드**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # LLM_PROVIDER 설정
uvicorn app.main:app --reload --port 8000
```

**프론트엔드**
```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

**테스트**
```bash
cd backend
python -m pytest -q
```
