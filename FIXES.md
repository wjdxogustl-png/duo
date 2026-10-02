# settle-agent 수정 작업 목록 (Claude Code용)

> 사용법: 이 파일을 `settle-agent/` 폴더 최상단에 넣고, VS Code의 Claude Code에 이렇게 요청하세요.
>
> `FIXES.md를 읽고 0번부터 순서대로 진행해 줘. 항목 하나 끝날 때마다 검증 방법대로 확인하고 결과를 알려 줘.`
>
> 급할 때는 번호를 지정해도 됩니다. 예: `FIXES.md의 0번만 해 줘`

## 작업 규칙

- 항목 하나씩 진행하고, 끝날 때마다 `backend` 폴더에서 `python -m pytest -q`를 실행해 기존 테스트가 깨지지 않았는지 확인한다.
- `backend/.env`는 읽거나 수정하지 않는다.
- 채점 기준(점수 배분, `THRESHOLD = 50`)과 로드맵 규칙 내용은 바꾸지 않는다. 바꿔야 하면 먼저 물어본다.
- 시스템 프롬프트의 안전장치(비자·법률 판단 금지, 1345 연결)는 유지한다.
- 수정한 파일과 이유를 항목별로 짧게 보고한다.

---

## 0. [긴급] 프론트 하얀 화면: `destroy is not a function`

**파일**: `frontend/src/App.jsx`

**원인**: 자동 스크롤 `useEffect`가 중괄호 없는 화살표 함수라서 `scrollIntoView()`의 반환값(최신 브라우저에서는 Promise)이 clean-up 함수로 취급된다. 다음 렌더링 때 React가 이를 실행하려다 오류가 나고 화면 전체가 내려간다.

**현재 코드**
```jsx
useEffect(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, busy]);
```

**수정**
```jsx
useEffect(() => {
  bottomRef.current?.scrollIntoView({ behavior: "smooth" });
}, [messages, busy]);
```

다른 `useEffect`도 모두 확인해서 함수 외의 값을 반환하는 곳이 없게 한다.

**검증**: `npm run dev` 후 `http://localhost:5173`에서 환영 메시지가 보이고, F12 콘솔에 `destroy is not a function`이 없어야 한다. (`favicon.ico 404`는 무시해도 됨)

---

## 1. 위험도 점수가 거의 항상 기준 미달로 나옴

**파일**: `backend/app/tools/risk.py`, `backend/app/agent.py`

**원인**: `REQUIRED_FIELDS`에 없는 `has_local_support`, `workplace_issue`, `knows_support_programs`(합계 55점)가 비어 있으면 0점 처리된다. 필수 항목만 채운 프로필로 계산하면 10점 정도가 나와 누구에게나 멘토링을 먼저 권하게 된다.

**수정 방향**
- `compute_score`가 `missing`이 비어 있지 않으면 판정하지 않도록 한다.
  - `"complete": False`, `"recommend_mentoring_first": None`, 그리고 되물을 항목 목록을 돌려준다.
  - `missing`이 비어 있을 때만 지금처럼 점수와 `recommend_mentoring_first`를 판정한다.
- `score_risk` 도구 설명과 시스템 프롬프트 2번에 "결과의 `missing`이 있으면 그 항목을 먼저 쉽게 되묻고, 저장한 뒤 다시 `score_risk`를 호출한다"를 추가한다.

**테스트 추가**: 일부 항목이 빠진 프로필에서 `complete`가 False이고 `recommend_mentoring_first`가 None인지 확인하는 테스트.

---

## 2. "김해시"로 검색하면 지원사업이 0건

**파일**: `backend/app/tools/programs.py`, `backend/app/tools/__init__.py`

**원인**: 지역명을 완전 일치로 비교한다. Claude가 프로필에 "김해시"나 "창원특례시"로 저장하면 DB의 "김해", "창원"과 맞지 않는다.

**수정**
```python
import re

def normalize_region(r: str | None) -> str | None:
    if not r:
        return r
    r = r.strip().replace("경상남도", "경남")
    return re.sub(r"(특례시|시|군)$", "", r)
```
- `search_programs`에서 검색어와 DB 값을 모두 `normalize_region`으로 정규화한 뒤 비교한다.
- `search_programs` 도구의 `category` 인자를 `Literal["한국어교육", "법률상담", "노동상담", "자녀교육", "취업", "멘토링", "생활", "행정"] | None`으로 제한한다.

**테스트 추가**: `region="김해시"`, `region="창원특례시"`, `region="경상남도"`로 검색했을 때 결과가 나오는지.

---

## 3. 빈 응답이 대화 기록에 저장되면 다음 턴부터 API 오류

**파일**: `backend/app/agent.py`

**원인**: 모델이 텍스트 없이 끝나면 `reply = ""`가 history에 저장되는데, Anthropic API는 빈 assistant 메시지를 거부한다.

**수정**
- 루프가 끝난 뒤 `reply.strip()`이 비어 있으면 사용자 언어에 맞는 짧은 기본 문장으로 대체한다(ko/en/vi).
- history에 저장할 때도 내용이 빈 메시지는 저장하지 않는다.

---

## 4. 대화 기록 순서가 API 규칙과 어긋날 수 있음

**파일**: `backend/app/agent.py`

**원인**: 능동 브리핑은 사용자 메시지 없이 assistant 응답만 저장하므로 assistant 메시지가 연속될 수 있고, `MAX_HISTORY`로 잘리면 기록이 assistant 메시지로 시작할 수 있다.

**수정**: `run()`에서 history를 메시지로 바꾸기 전에 정리한다.
- 앞쪽의 assistant 메시지는 user 메시지가 나올 때까지 버린다.
- 같은 역할이 연속되면 내용을 줄바꿈 두 개로 이어 하나로 합친다.
- 빈 내용은 건너뛴다.

**검증**: 실제 API 키로 "대화 → 새로고침(브리핑) → 다시 대화"를 해서 오류가 없는지 확인.

---

## 5. 사용자 ID가 정리되지 않은 채 파일명에 들어감

**파일**: `backend/app/tools/document.py`

**원인**: 상태 파일은 `memory._safe_id()`로 정리하지만, 신청서 파일명은 원본 `current_user` 값을 그대로 쓴다. `../` 같은 값이 들어오면 출력 폴더 밖에 파일이 써질 수 있다.

**수정**
```python
fname = f"{memory._safe_id(memory.current_user.get())}_{datetime.now():%Y%m%d%H%M%S}.docx"
```

---

## 6. 로드맵 패널의 D-day 배지에 날짜가 그대로 표시됨

**파일**: `backend/app/agent.py`, `frontend/src/App.jsx`

**원인**: `state.dday`에는 종료일("2027-01-01")만 있어서 "D-91" 대신 날짜가 보인다.

**수정**
- `run()`의 반환 `state`에 `dday_label`을 추가한다. `state["dday"]`가 있으면 `compute_dday(state["dday"])["label"]`, 없으면 None.
- 프론트 `applyResult`에서 `setDday(res.state.dday_label)`로 바꾼다.

---

## 7. 베트남어 화면에서도 로드맵이 한국어로만 보임

**파일**: `frontend/src/i18n.js`, `frontend/src/App.jsx`

**원인**: 로드맵 단계 제목과 카테고리가 백엔드에 한국어로 고정되어 있고 `i18n.js`에 번역이 없다.

**수정**
- `i18n.js`의 ko/en/vi 각각에 `steps`(단계 id → 제목)와 `categories`(카테고리 → 표시 이름)를 추가한다. 단계 id는 `backend/app/tools/roadmap.py`의 `RULES`를 기준으로 한다.
- `App.jsx`에서 `t.steps?.[s.id] ?? s.title`, `t.categories?.[s.category] ?? s.category`로 표시한다.
- 하드코딩된 "(도구 호출 없음)"도 `t.noToolCall`로 옮긴다.
- 영어·베트남어 번역은 초안이므로 `// TODO(조환성): 번역 대조 확인` 주석을 남긴다.

---

## 8. 새로고침할 때마다 브리핑이 Claude를 호출함

**파일**: `backend/app/agent.py`, `backend/app/main.py`, `frontend/src/App.jsx`

**원인**: 페이지를 열 때마다 `/api/briefing`이 LLM을 호출하고 history에 assistant 메시지가 쌓인다. 시연 녹화 중 새로고침하면 기록이 지저분해진다.

**수정**
- 상태에 `last_briefing_at`(ISO 시각)을 저장하고, 마지막 브리핑 후 6시간이 지나지 않았으면 브리핑을 건너뛴다.
- 프론트는 처음 열 때 `/api/state`로 기존 대화 기록을 불러와 화면에 복원하고, 브리핑이 있으면 그 뒤에 덧붙인다.
- 시연용으로 `/api/briefing/{user_id}?force=true`면 시간 제한 없이 브리핑하게 한다.

---

## 9. 로드맵 생성 10초 목표 대비 응답 속도

**파일**: `backend/app/agent.py`

**원인**: save_profile → score_risk → build_roadmap → 단계별 search_programs가 순차 호출되면 LLM 왕복이 4~6회가 된다.

**수정**
- 시스템 프롬프트에 "서로 의존하지 않는 도구(예: 여러 단계의 search_programs)는 한 번에 함께 호출한다"를 추가한다.
- 검토: `build_roadmap`이 각 단계에 해당 지역·카테고리의 지원사업을 함께 붙여 반환하도록 하면 왕복이 크게 줄어든다. 적용 전에 팀에 먼저 물어본다.

**검증**: 시연 시나리오로 3회 실행해 `elapsed_ms`를 표로 정리한다(완료보고서 정량 목표 증빙용).

---

## 마지막 확인

- [ ] `python -m pytest -q` 전체 통과
- [ ] 프론트 콘솔에 빨간 오류 없음
- [ ] 시연 시나리오 1~6단계를 베트남어로 끝까지 한 번 성공
- [ ] 변경 내용을 README의 TODO 체크리스트에 반영
