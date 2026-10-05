"""개발용 가짜 에이전트 모델 (LLM_PROVIDER=mock). API 키 없이 무료로 동작한다.

실제 LLM처럼 '도구 호출 → 결과 확인 → 다음 행동'을 반복하지만, 판단은 정해진 규칙과
키워드 매칭으로 한다. 도구는 진짜로 실행되므로 로드맵·점수·지원사업 검색·D-day·신청서
docx 생성·능동 브리핑을 화면에서 모두 확인할 수 있다.

한계: 자유로운 질문은 이해하지 못한다. 시연영상·발표는 실제 LLM(gemini/ollama/anthropic)으로 한다.
"""
import json
import re
import uuid

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from . import memory
from .tools.profile import REQUIRED_FIELDS

# 위험도 채점에 필요한 선택 항목까지 물어본다 (모르면 0점 처리되는 문제 방지)
ASK_ORDER = REQUIRED_FIELDS + ["has_local_support", "workplace_issue", "knows_support_programs"]

REGIONS = {
    "창원": ["창원", "changwon"], "진주": ["진주", "jinju"], "통영": ["통영", "tongyeong"],
    "사천": ["사천", "sacheon"], "김해": ["김해", "gimhae"], "밀양": ["밀양", "miryang"],
    "거제": ["거제", "geoje"], "양산": ["양산", "yangsan"], "의령": ["의령", "uiryeong"],
    "함안": ["함안", "haman"], "창녕": ["창녕", "changnyeong"], "고성": ["고성", "goseong"],
    "남해": ["남해", "namhae"], "하동": ["하동", "hadong"], "산청": ["산청", "sancheong"],
    "함양": ["함양", "hamyang"], "거창": ["거창", "geochang"], "합천": ["합천", "hapcheon"],
}

VI_CHARS = re.compile(r"[ăâđêôơưàáạảãầấậẩẫằắặẳẵèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]", re.I)
LANG_BY_NAME = {"한국어": "ko", "English": "en", "Tiếng Việt": "vi"}

YES = re.compile(r"^\s*(네|예|응|있어요|있습니다|있어|맞아요|yes|yeah|yep|có|vâng|dạ có|ừ)(\s|$|[.!,~])", re.I)
NO = re.compile(r"^\s*(아니|아뇨|없어요|없습니다|없어|no|nope|không|chưa)(\s|$|[.!,~요])", re.I)

# ---------------------------------------------------------------- 화면 문구

QUESTIONS = {
    "region": {
        "ko": "어느 시·군에 사시나요? (예: 창원, 김해, 진주)",
        "en": "Which city or county in Gyeongnam do you live in? (e.g., Changwon, Gimhae, Jinju)",
        "vi": "Bạn sống ở thành phố/huyện nào của Gyeongnam? (ví dụ: Changwon, Gimhae, Jinju)",
    },
    "months_in_korea": {
        "ko": "한국에 오신 지 얼마나 되셨어요? (예: 3개월, 1년)",
        "en": "How long have you been in Korea? (e.g., 3 months, 1 year)",
        "vi": "Bạn đã ở Hàn Quốc bao lâu rồi? (ví dụ: 3 tháng, 1 năm)",
    },
    "korean_level": {
        "ko": "한국어는 어느 정도 하세요? 숫자로 답해 주셔도 돼요. 0 거의 못함 / 1 기초 / 2 일상대화 / 3 능숙",
        "en": "How is your Korean? You can answer with a number: 0 almost none / 1 basic / 2 daily conversation / 3 fluent",
        "vi": "Tiếng Hàn của bạn ở mức nào? Bạn có thể trả lời bằng số: 0 gần như không biết / 1 cơ bản / 2 giao tiếp hằng ngày / 3 thành thạo",
    },
    "has_children": {
        "ko": "자녀가 있으신가요? (네/아니요)",
        "en": "Do you have children? (yes/no)",
        "vi": "Bạn có con không? (có/không)",
    },
    "job_status": {
        "ko": "지금 일하고 계신가요, 일자리를 찾고 계신가요, 아니면 학생이신가요?",
        "en": "Are you working now, looking for a job, or a student?",
        "vi": "Hiện bạn đang đi làm, đang tìm việc hay là sinh viên?",
    },
    "has_local_support": {
        "ko": "주변에 어려울 때 도와줄 사람이 있나요? (네/아니요)",
        "en": "Is there someone nearby who can help you when things get hard? (yes/no)",
        "vi": "Gần bạn có ai có thể giúp khi bạn gặp khó khăn không? (có/không)",
    },
    "workplace_issue": {
        "ko": "직장에서 차별이나 임금 문제 같은 어려움이 있나요? (네/아니요)",
        "en": "Do you have problems at work, such as discrimination or unpaid wages? (yes/no)",
        "vi": "Ở nơi làm việc bạn có gặp khó khăn như bị phân biệt đối xử hoặc bị nợ lương không? (có/không)",
    },
    "knows_support_programs": {
        "ko": "시·군의 외국인 지원사업을 이용해 본 적이 있나요? (네/아니요)",
        "en": "Have you ever used a support program for foreign residents in your city or county? (yes/no)",
        "vi": "Bạn đã từng sử dụng chương trình hỗ trợ cư dân nước ngoài của thành phố/huyện chưa? (có/không)",
    },
}

STEP_TITLES = {  # 영어·베트남어 단계 이름 (한국어는 roadmap.py 의 title 사용)
    "registration_check": {"en": "Check alien registration and report of residence (see the immigration office's official guide)",
                           "vi": "Kiểm tra đăng ký người nước ngoài và khai báo nơi cư trú (xem hướng dẫn chính thức của Cục Xuất nhập cảnh)"},
    "bank_phone": {"en": "Open a bank account and a mobile phone line", "vi": "Mở tài khoản ngân hàng và đăng ký điện thoại di động"},
    "health_insurance": {"en": "Check your health insurance enrollment", "vi": "Kiểm tra việc tham gia bảo hiểm y tế"},
    "community": {"en": "Connect with a local migrant community or mentor", "vi": "Kết nối với cộng đồng người nhập cư hoặc người hướng dẫn tại địa phương"},
    "korean_class": {"en": "Apply for a Korean language class", "vi": "Đăng ký lớp học tiếng Hàn"},
    "children_school": {"en": "Check childcare and school information", "vi": "Tìm hiểu thông tin nhà trẻ và trường học cho con"},
    "workplace_counsel": {"en": "Get counseling about workplace problems", "vi": "Nhận tư vấn về khó khăn ở nơi làm việc"},
    "job_support": {"en": "Check job support programs", "vi": "Tìm hiểu chương trình hỗ trợ việc làm"},
    "law_counsel": {"en": "Know where to get everyday legal counseling", "vi": "Biết nơi nhận tư vấn pháp luật đời sống"},
}

T = {
    "ko": {
        "score": "정착 안정도 점수는 {score}점이에요 (기준 {threshold}점).",
        "mentor_first": "지금은 혼자 해결하기보다 멘토·상담을 먼저 연결해 드릴게요.",
        "recommend_first": "먼저 추천하는 곳:",
        "roadmap": "할 일을 순서대로 정리했어요.",
        "program": "   - {name} · {schedule} · {contact}",
        "source": "     출처: {url}",
        "apply_hint": "한국어 교실 신청서가 필요하면 \"신청서 만들어 주세요\"라고 말씀해 주세요.",
        "official": "체류·비자 관련 내용은 출입국·외국인청(1345)에서 꼭 확인하세요.",
        "doc_none": "신청할 한국어 교실을 아직 찾지 못했어요. 사는 시·군을 먼저 알려 주세요.",
        "doc_done": "신청서 초안을 아래에 만들었어요. 연락처 같은 빈칸은 직접 채우고, 틀린 곳은 고쳐 주세요. 다 되면 내려받거나 복사해서 기관에 직접 제출하시면 돼요.",
        "dday": "체류 종료일까지 {label}이에요. 다음 알림은 {next} 시점이에요.",
        "dday_no_next": "체류 종료일까지 {label}이에요.",
        "step_done": "좋아요! \"{title}\"을(를) 완료로 표시했어요.",
        "next_step": "다음 할 일은 \"{title}\"이에요.",
        "all_done": "로드맵의 할 일을 모두 마쳤어요. 정말 잘하셨어요!",
        "unknown": "(개발용 mock 모드라 자유로운 질문에는 답하지 못해요.)",
        "brief_hello": "다시 오셨네요! 반가워요.",
        "brief_next": "이어서 \"{title}\"부터 해 볼까요?",
    },
    "en": {
        "score": "Your settlement stability score is {score} (threshold {threshold}).",
        "mentor_first": "Rather than handling everything alone, let's connect you with a mentor or counselor first.",
        "recommend_first": "Recommended first:",
        "roadmap": "Here are your next steps in order.",
        "program": "   - {name} · {schedule} · {contact}",
        "source": "     Source: {url}",
        "apply_hint": "If you need a Korean class application, just say \"make an application\".",
        "official": "For stay or visa matters, please check with the Immigration Office (1345).",
        "doc_none": "I couldn't find a Korean class to apply for yet. Please tell me which city or county you live in first.",
        "doc_done": "I made a draft application below. Fill in blanks like your phone number yourself and fix anything wrong. Then download or copy it and submit it to the institution yourself.",
        "dday": "Your stay ends in {label}. The next reminder is at {next}.",
        "dday_no_next": "Your stay ends in {label}.",
        "step_done": "Great! I marked \"{title}\" as done.",
        "next_step": "Your next step is \"{title}\".",
        "all_done": "You've finished every step on your roadmap. Well done!",
        "unknown": "(Mock development mode can't answer free-form questions.)",
        "brief_hello": "Welcome back!",
        "brief_next": "Shall we continue with \"{title}\"?",
    },
    "vi": {
        "score": "Điểm ổn định định cư của bạn là {score} điểm (mức chuẩn {threshold} điểm).",
        "mentor_first": "Thay vì tự mình giải quyết, trước tiên mình sẽ kết nối bạn với người hướng dẫn hoặc tư vấn.",
        "recommend_first": "Nên liên hệ trước:",
        "roadmap": "Mình đã sắp xếp các việc cần làm theo thứ tự.",
        "program": "   - {name} · {schedule} · {contact}",
        "source": "     Nguồn: {url}",
        "apply_hint": "Nếu cần đơn đăng ký lớp tiếng Hàn, hãy nói \"làm đơn đăng ký giúp tôi\".",
        "official": "Các vấn đề về cư trú, thị thực, hãy kiểm tra tại Cục Xuất nhập cảnh (1345).",
        "doc_none": "Mình chưa tìm thấy lớp tiếng Hàn để đăng ký. Bạn cho mình biết bạn sống ở thành phố/huyện nào trước nhé.",
        "doc_done": "Mình đã tạo bản nháp đơn ở bên dưới. Bạn tự điền chỗ trống như số điện thoại và sửa chỗ sai nhé. Xong thì tải xuống hoặc sao chép rồi tự nộp cho cơ quan.",
        "dday": "Còn {label} đến ngày hết hạn cư trú. Lần nhắc tiếp theo là {next}.",
        "dday_no_next": "Còn {label} đến ngày hết hạn cư trú.",
        "step_done": "Tốt lắm! Mình đã đánh dấu \"{title}\" là hoàn thành.",
        "next_step": "Việc tiếp theo là \"{title}\".",
        "all_done": "Bạn đã hoàn thành tất cả các bước trong lộ trình. Giỏi lắm!",
        "unknown": "(Chế độ mock dùng để phát triển nên không trả lời được câu hỏi tự do.)",
        "brief_hello": "Chào mừng bạn quay lại!",
        "brief_next": "Mình tiếp tục với \"{title}\" nhé?",
    },
}
# TODO(조환성): 영어·베트남어 문구 대조 확인

# ---------------------------------------------------------------- 입력 해석


def detect_lang(text: str) -> str | None:
    if re.search(r"[가-힣]", text):
        return "ko"
    if VI_CHARS.search(text):
        return "vi"
    if len(re.findall(r"[A-Za-z]+", text)) >= 3:
        return "en"
    return None


def _months(t: str) -> int | None:
    words = {"한 달": 1, "한달": 1, "두 달": 2, "두달": 2, "세 달": 3, "세달": 3, "반년": 6, "일 년": 12}
    for w, v in words.items():
        if w in t:
            return v
    if re.search(r"(?<!\d)\d{1,2}\s*(주|일|weeks?|days?|tuần|ngày)(?!\w)", t) and not re.search(r"개월|달|month|tháng|년|year|năm", t):
        return 0
    y = re.search(r"(?<!\d)(\d{1,2})\s*(년|years?|năm)", t)
    m = re.search(r"(?<!\d)(\d{1,3})\s*(개월|달|months?|tháng)", t)
    if not y and not m:
        return None
    return (int(y.group(1)) * 12 if y else 0) + (int(m.group(1)) if m else 0)


def parse_profile(text: str, asked: str | None) -> dict:
    t = text.lower()
    upd: dict = {}

    for name, keys in REGIONS.items():
        if any(k in t for k in keys):
            upd["region"] = name
            break

    months = _months(t)
    if months is None and asked == "months_in_korea" and re.fullmatch(r"\s*\d{1,3}\s*", t):
        months = int(t)
    if months is not None:
        upd["months_in_korea"] = months

    if re.search(r"(아이|자녀|애기|아기)\s*(는|가|도)?\s*없|no (kids|children|child)|don'?t have (any )?(kids|children)|không có con|chưa có con", t):
        upd["has_children"] = False
    elif re.search(r"아이|자녀|아들|딸|애가|아기|\bkids?\b|\bchild(ren)?\b|\bsons?\b|\bdaughters?\b|có con|con trai|con gái|con tôi", t):
        upd["has_children"] = True

    if re.search(r"구직|일자리\s*(를)?\s*찾|일\s*(을|를)?\s*찾|일하고\s*싶|취업\s*준비|looking for (a )?(job|work)|job ?seek|unemployed|tìm việc|thất nghiệp", t):
        upd["job_status"] = "seeking"
    elif re.search(r"학생|유학|\bstudent\b|sinh viên|du học", t):
        upd["job_status"] = "student"
    elif re.search(r"회사|공장|일하|일해|근무|직장|\bemployed\b|\bworking\b|\bi work\b|factory|company|làm việc|đi làm|công ty|nhà máy|công nhân", t):
        upd["job_status"] = "employed"

    levels = [
        (0, r"한국어\s*(를|는)?\s*(거의\s*)?(못|모르)|한국말\s*(을|은)?\s*(거의\s*)?(못|모르)|no korean|can'?t speak korean|don'?t speak korean|không biết tiếng hàn|không nói được tiếng hàn"),
        (1, r"한국어\s*(는|를)?\s*(조금|기초|서툴|잘\s*못)|한국말\s*(은|을)?\s*(조금|서툴|잘\s*못)|a little korean|basic korean|bit of korean|một chút tiếng hàn|tiếng hàn (một chút|cơ bản|ít)|chút tiếng hàn"),
        (2, r"일상\s*(대화|회화)|대화\s*(는|정도)?\s*(가능|할\s*수)|conversational|daily conversation|giao tiếp (được|hằng ngày)|nói chuyện được"),
        (3, r"한국어\s*(를|는)?\s*잘\s*(해|합|함)|능숙|유창|fluent|thành thạo|giỏi tiếng hàn|tiếng hàn (tốt|giỏi)"),
    ]
    for lv, pat in levels:
        if re.search(pat, t):
            upd["korean_level"] = lv
            break
    else:
        if asked == "korean_level" and re.fullmatch(r"\s*[0-3]\s*", t):
            upd["korean_level"] = int(t)

    if re.search(r"(도와줄|도와 줄|도움\s*받을|아는)\s*사람\s*(이|은|도)?\s*없|혼자|외로|no one|nobody|alone|don'?t know anyone|no friends|không có ai|một mình|không quen ai", t):
        upd["has_local_support"] = False
    elif re.search(r"(도와줄|도와 줄|도움\s*받을|아는)\s*사람\s*(이|은)?\s*있|친구\s*(가|들이|도)?\s*있|가족\s*(이|과|이랑|하고)|someone (to help|who helps|nearby)|have friends|my family|có bạn|có người (quen|thân|giúp)|gia đình ở đây", t):
        upd["has_local_support"] = True

    if re.search(r"차별|월급\s*(을|이)?\s*(안|못)|임금\s*체불|체불|괴롭힘|폭언|부당|discriminat|unpaid|not paid|harass|phân biệt|nợ lương|không trả lương|quấy rối|bị chửi", t):
        upd["workplace_issue"] = True
    elif re.search(r"(직장|회사|일)\s*(에서|은|는)?\s*(문제|어려움)\s*(는|은)?\s*없|no (problems?|issues?) at work|work is fine|không có vấn đề", t):
        upd["workplace_issue"] = False

    if re.search(r"(지원\s*사업|프로그램|센터)\s*(은|는|을|를)?\s*(잘\s*)?(몰라|모르|처음)|이용해\s*본\s*적\s*(이)?\s*없|never used|don'?t know (any|about)|not aware|chưa (từng )?(dùng|sử dụng)|không biết (về )?(chương trình|hỗ trợ)", t):
        upd["knows_support_programs"] = False
    elif re.search(r"이용해\s*(본\s*적\s*(이)?\s*있|봤)|(지원\s*사업|센터)\s*(을|를|은|는)?\s*알고|have used|used (a |the )?(support|program|center)|đã (từng )?(dùng|sử dụng|tham gia)", t):
        upd["knows_support_programs"] = True

    # 직전에 예/아니요 질문을 했다면 짧은 대답을 그 항목의 값으로 쓴다
    if asked in ("has_children", "has_local_support", "workplace_issue", "knows_support_programs") and asked not in upd:
        if YES.search(t):
            upd[asked] = True
        elif NO.search(t):
            upd[asked] = False
        elif asked == "knows_support_programs" and re.search(r"몰라|모르|처음|don'?t know|không biết", t):
            upd[asked] = False

    m = re.search(r"이름은\s*(.+?)\s*(?:입니다|이에요|예요|이야|$|[,.\n])", text) \
        or re.search(r"my name is\s+([A-Za-z][A-Za-z ]{0,40}?)\s*(?:[,.\n]|$)", text, re.I) \
        or re.search(r"tên (?:tôi|em|của tôi) là\s+(.+?)\s*(?:[,.\n]|$)", text, re.I)
    if m:
        upd["name"] = m.group(1).strip()
    return upd


def parse_time(text: str) -> str | None:
    m = re.search(r"평일\s*(저녁|오전|오후|낮)|주말\s*(오전|오후)?|저녁|weekday (evening|morning)s?|weekends?|evenings?|buổi tối( ngày thường)?|cuối tuần|buổi sáng", text, re.I)
    return m.group(0).strip() if m else None


def parse_date(text: str) -> str | None:
    m = re.search(r"(20\d{2})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})", text)
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    return f"{y:04d}-{mo:02d}-{d:02d}"


APPLY = re.compile(r"신청서|신청하고|신청할래|신청해|apply|application|sign up|đăng ký|làm đơn|\bđơn\b", re.I)
DONE = re.compile(r"했어요|했습니다|만들었|끝났|끝냈|완료|다 했|\bdone\b|finished|completed|\bxong\b|đã làm|đã mở|đã đăng ký", re.I)
STEP_KEYWORDS = {
    "registration_check": r"외국인\s*등록|등록증|체류지|alien registration|residence report|đăng ký người nước ngoài|thẻ cư trú",
    "bank_phone": r"은행|계좌|휴대폰|핸드폰|bank|phone|ngân hàng|điện thoại",
    "health_insurance": r"건강\s*보험|insurance|bảo hiểm",
    "korean_class": r"한국어\s*(교실|교육|수업)|korean class|lớp (học )?tiếng hàn",
    "children_school": r"어린이집|학교|school|nhà trẻ|trường",
}

# ---------------------------------------------------------------- 모델


class MockAgentModel:
    """ChatModel.bind_tools(...) 결과와 같은 방식으로 invoke(messages) -> AIMessage 를 제공한다."""

    def invoke(self, messages):
        human_idx = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        human = messages[human_idx].content
        turn = messages[human_idx + 1:]
        names = {}
        for m in turn:
            if isinstance(m, AIMessage):
                for c in m.tool_calls:
                    names[c["id"]] = c["name"]
        results: dict[str, list] = {}
        for m in turn:
            if isinstance(m, ToolMessage):
                try:
                    data = json.loads(m.content)
                except (ValueError, TypeError):
                    data = m.content
                results.setdefault(names.get(m.tool_call_id, "?"), []).append(data)

        state = memory.load()
        lang = self._lang(messages, human, state)
        if human.startswith("[시스템 알림"):
            return AIMessage(self._briefing(state, lang))
        if not results:
            return self._first_step(human, state, lang)
        return self._after_tools(results, state, lang)

    # -- 언어
    @staticmethod
    def _lang(messages, human, state):
        detected = detect_lang(human) if not human.startswith("[시스템") else None
        if detected:
            return detected
        if state["profile"].get("language"):
            return state["profile"]["language"]
        sys = next((m.content for m in messages if isinstance(m, SystemMessage)), "")
        m = re.search(r"응답 언어: ([^\s(]+(?: [^\s(]+)?)", sys)
        return LANG_BY_NAME.get(m.group(1).strip(), "ko") if m else "ko"

    # -- 사용자 메시지를 받은 직후
    def _first_step(self, human, state, lang):
        profile = state["profile"]
        upd = parse_profile(human, state.get("mock_asked"))
        detected = detect_lang(human)
        if detected and detected != profile.get("language"):
            upd["language"] = detected
        calls = []

        date = parse_date(human)
        if date:
            calls.append(_call("set_dday_reminder", {"end_date": date}))

        # 로드맵 단계 완료 보고
        if state["roadmap"] and DONE.search(human) and not APPLY.search(human):
            for sid, pat in STEP_KEYWORDS.items():
                if re.search(pat, human, re.I) and any(s["id"] == sid for s in state["roadmap"]):
                    calls.append(_call("update_roadmap_step", {"step_id": sid, "done": True}))
                    break

        # 신청서 초안: 이름·연락처를 채팅으로 모으지 않고, 화면에 초안을 띄워 사용자가 직접 채운다
        if APPLY.search(human):
            program_id = _korean_class_program(upd.get("region") or profile.get("region"))
            if program_id:
                calls.append(_call("draft_application", {"program_id": program_id, "preferred_time": parse_time(human) or ""}))
            if upd:
                calls.insert(0, _call("save_profile", upd))
            if calls:
                return AIMessage("", tool_calls=calls)
            return AIMessage(T[lang]["doc_none"])

        if upd:
            calls.insert(0, _call("save_profile", upd))
        if calls:
            return AIMessage("", tool_calls=calls)
        return self._next_move(set(), {}, state, lang, understood=False)

    # -- 도구 결과를 받은 뒤
    def _after_tools(self, results, state, lang):
        called = set(results)
        t = T[lang]

        if "draft_application" in called:
            return AIMessage(t["doc_done"])

        if "search_programs" in called:
            return AIMessage(self._roadmap_reply(results, state, lang))

        if "build_roadmap" in called:
            region = state["profile"].get("region")
            cats = []
            risk = (results.get("score_risk") or [{}])[0]
            if risk.get("recommend_mentoring_first"):
                cats.append("멘토링")
                if state["profile"].get("workplace_issue"):
                    cats.append("노동상담")
            for s in results["build_roadmap"][0]["steps"]:
                if not s["done"] and s["category"] not in cats:
                    cats.append(s["category"])
            return AIMessage("", tool_calls=[_call("search_programs", {"region": region, "category": c}) for c in cats])

        return self._next_move(called, results, state, lang, understood=True)

    def _next_move(self, called, results, state, lang, understood):
        t = T[lang]
        prefix = []
        for r in results.get("set_dday_reminder", []):
            prefix.append(_dday_text(r, lang))
        for r in results.get("update_roadmap_step", []):
            if r.get("ok"):
                prefix.append(t["step_done"].format(title=_title(r["step"], lang)))

        missing = [f for f in ASK_ORDER if f not in state["profile"]]
        if missing:
            _set_state(mock_asked=missing[0])
            return AIMessage("\n".join(prefix + [QUESTIONS[missing[0]][lang]]))
        _set_state(mock_asked=None)

        if not state["roadmap"] or "save_profile" in called:
            return AIMessage("", tool_calls=[_call("score_risk", {}), _call("build_roadmap", {})])

        nxt = next((s for s in state["roadmap"] if not s["done"]), None)
        prefix.append(t["next_step"].format(title=_title(nxt, lang)) if nxt else t["all_done"])
        if not understood:
            prefix.append(t["unknown"])
        return AIMessage("\n".join(prefix))

    def _roadmap_reply(self, results, state, lang):
        t = T[lang]
        lines = []
        risk = (results.get("score_risk") or [None])[0]
        if risk:
            lines.append(t["score"].format(score=risk["score"], threshold=risk["threshold"]))
        by_cat: dict[str, list] = {}
        for r in results.get("search_programs", []):
            for p in r.get("programs", []):
                by_cat.setdefault(p["category"], [])
                if p not in by_cat[p["category"]]:
                    by_cat[p["category"]].append(p)

        if risk and risk.get("recommend_mentoring_first"):
            lines.append(t["mentor_first"])
            first = by_cat.get("멘토링", []) + by_cat.get("노동상담", [])
            if first:
                lines.append(t["recommend_first"])
                for p in first:
                    lines += _program_lines(p, t)
        lines.append("")
        lines.append(t["roadmap"])
        steps = (results.get("build_roadmap") or [{"steps": state["roadmap"]}])[0]["steps"]
        for s in steps:
            if s["done"]:
                continue
            lines.append(f"{s['order']}. {_title(s, lang)}")
            for p in by_cat.get(s["category"], []):
                lines += _program_lines(p, t)
        lines.append("")
        lines.append(t["apply_hint"])
        lines.append(t["official"])
        return "\n".join(lines)

    def _briefing(self, state, lang):
        t = T[lang]
        lines = [t["brief_hello"]]
        if state["dday"]:
            from .tools.dday import compute_dday
            lines.append(_dday_text(compute_dday(state["dday"]), lang))
        missing = [f for f in ASK_ORDER if f not in state["profile"]]
        if not state["roadmap"] and missing:
            _set_state(mock_asked=missing[0])
            lines.append(QUESTIONS[missing[0]][lang])
            return "\n".join(lines)
        nxt = next((s for s in state["roadmap"] if not s["done"]), None)
        lines.append(t["brief_next"].format(title=_title(nxt, lang)) if nxt else t["all_done"])
        return "\n".join(lines)



# ---------------------------------------------------------------- 도우미


def _call(name, args):
    return {"name": name, "args": args, "id": f"mock_{uuid.uuid4().hex[:8]}", "type": "tool_call"}


def _set_state(**kw):
    state = memory.load()
    state.update(kw)
    memory.save(state)


def _title(step, lang):
    if lang == "ko":
        return step["title"]
    return STEP_TITLES.get(step["id"], {}).get(lang, step["title"])


def _program_lines(p, t):
    lines = [t["program"].format(name=p["name"], schedule=p.get("schedule", ""), contact=p.get("contact", ""))]
    if p.get("source_url"):
        lines.append(t["source"].format(url=p["source_url"]))
    return lines


def _dday_text(r, lang):
    t = T[lang]
    if r.get("next_reminder_at"):
        return t["dday"].format(label=r["label"], next=r["next_reminder_at"])
    return t["dday_no_next"].format(label=r["label"])


def _korean_class_program(region):
    from .tools.programs import search_programs
    if not region:
        return None
    found = search_programs(region=region, category="한국어교육")["programs"]
    return found[0]["id"] if found else None
