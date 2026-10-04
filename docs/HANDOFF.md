# 인수인계 메모 (Chat / Cowork 에 붙여넣기용)

> 이 파일을 Claude Chat 또는 Cowork 에 첨부하거나 내용을 붙여넣고 "이 프로젝트 이어서 도와줘"라고 요청하세요.

## 상황
- 대회: 2026년 제4회 경남 AI·SW 경진대회, 분야 1. 사회문제 해결형 AI Agent, 대학부
- 팀: duo (창신대학교, 정태현·조환성 2인)
- 과제명: 경남 이주민 능동 케어 에이전트 (부제: 다국어 기반 정착 로드맵 안내)
- 개발기간 9/29 ~ 10/6, 서류심사 10/7~8, 발표심사 10/12, 시상식 10/14
- 이 메모 작성일: 2026-10-02 (4일차). 이후 바뀐 내용(도구 9개, 지원사업 DB 26건, 액션 카드 등)은 `docs/STATUS.md` 와 README 기준

## 대회 심사 핵심
- "기능 수"보다 "AI Agent다운 문제 해결 과정과 실제 동작 여부" 우선 평가
- 목표 수준 Level 3 MVP: 핵심기능 3~5개 + End-to-End Workflow 1개 이상
- 필수 제출물 5종: 개발완료보고서(A4 5p), AI Agent 기술설명서(1p: Goal, Workflow, AI, Tool/API/Data, Memory/Feedback, 신규개발분), 소스코드/저장소, 시연동영상(3분, 입력→판단→도구 실행→결과), 발표자료(10장)
- 별지2 출처·AI 활용 신고서 작성 필요 (AI 도구 사용 자체는 감점 아님)

## 정한 개발 방향
- 규칙 로직(로드맵, 채점, D-day, 신청서 채움)은 코드 도구로, Claude 는 대화·판단·도구 선택·다국어 담당
- 도구 7개: save_profile, build_roadmap, update_roadmap_step, search_programs, score_risk, set_dday_reminder, generate_application_doc
- 재방문 시 에이전트가 D-day와 남은 단계를 먼저 안내 ("능동 케어")
- 화면에 도구 호출 로그 패널을 두어 시연영상에서 에이전트 판단 과정을 보여줌
- 스택: Python FastAPI + langchain-anthropic (모델 claude-sonnet-5-5), React(Vite), JSON 파일 DB, python-docx
- 언어: 대화는 사용자가 쓴 언어로 답함(베트남어 포함). 화면 문구는 한국어 원본 + AI 자동 번역(English / 日本語 / 中文)
- 안전장치: 비자·법률 판단 금지, 공식 기관(출입국·외국인청 1345 등) 연결

## 시연 시나리오
1. 베트남 근로자 페르소나가 베트남어로 "김해에 왔고 아이가 있어요"
2. 에이전트가 빠진 정보를 되묻고 save_profile
3. score_risk → build_roadmap → search_programs 로 로드맵과 실제 지원사업 연결
4. 점수가 기준(50) 미만이면 멘토·상담 먼저 제안
5. 한국어교육 신청서 초안 docx 생성·다운로드
6. 재방문 시 에이전트가 먼저 안내

## 남은 일정
| 날짜 | 정태현 (에이전트 로직) | 조환성 (DB·UI·다국어) |
|---|---|---|
| 10/2 | 도구 6~7개 완성, 단위 테스트 | 지원사업 DB 20건(출처 URL 필수), 채팅 UI |
| 10/3 | 에이전트에 도구 연결, 시스템 프롬프트 | 로드맵·도구 로그 패널, API 연동 |
| 10/4 | 채점, 능동 브리핑, docx 생성 | 다국어, 통합 E2E 1회 성공 |
| 10/5 | 테스트 표, 정량 목표 측정, 버그 수정 | 시연영상 촬영, 번역 대조 |
| 10/6 | 완료보고서, 기술설명서, 별지2 | 발표자료, README, GitHub → 제출 |

## 현재 코드 상태 (2026-10-02, taehyeon 브랜치)
- 백엔드·프론트 동작 확인. 테스트 25개 통과 (Windows, 가짜 CLI 테스트 3개는 macOS/Linux 전용)
- LLM 제공자 선택: `.env` 의 `LLM_PROVIDER` (mock / claude_agent / claude_cli / gemini / ollama / anthropic). 자세한 내용은 FREE_MODE.md
- `claude_agent` 모드로 베트남어 E2E 확인: save_profile → score_risk(10/50) → build_roadmap → search_programs 6회, 한 턴 20.3초
- `anthropic` 모드(시연·정량 측정용)는 API 키가 없어 아직 미검증
- 화면: 태극기·경남 지도, 라이트/다크 모드, 화면 문구 AI 자동 번역(en/ja/zh, `backend/data/i18n/` 에 캐시)
- data/programs.json 은 예시 2건뿐 → 실제 조사 20건 이상으로 교체해야 함
- 신청서 템플릿(data/templates/*.docx) 없음 → 코드가 기본 양식 자동 생성 중
- 자세한 구조·실행법·TODO 는 README.md 참고

## 정량 목표
- 로드맵 생성 10초 이내 / 지원사업 DB 20건 이상 / 신청서 입력값 반영 정확도 100%

## 관련 링크
- 개발 방향 정리 페이지: https://claude.ai/artifact/AEQsCsLkRLnvj5ujtSBV4R
