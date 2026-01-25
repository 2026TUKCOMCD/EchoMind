"""
[스크립트 가이드]

이 스크립트는 JSON 프로필 데이터를 시각화된 HTML 리포트로 생성합니다.
서버 환경에서는 `generate_report_html` 함수를 임포트하여 사용할 수도 있습니다.

사용법:
    python visualize_profile.py [입력파일] [옵션]

예시:
    python visualize_profile.py
    # profile.json을 읽어서 profile_report.html 생성

    python visualize_profile.py data/user_123.json
    # data/user_123.json을 읽어서 data/user_123.html 생성

옵션:
    input_file          입력 JSON 파일 경로 (기본값: profile.json)
    -o, --out           출력 HTML 파일 경로 (기본값: [입력파일명].html)
                        입력이 profile.json일 경우 기본 출력은 profile_report.html 입니다.

함수 사용 (Python):
    from visualize_profile import generate_report_html
    html_output = generate_report_html(your_json_dict)
"""
import json
import os
import sys
import html
import random
from datetime import datetime

# -------------------------------------------------------------------------
# 설정 / 매핑 (Configuration / Mappings)
# -------------------------------------------------------------------------

SCORE_MAP = [
    (20, "매우 낮음", "bg-gray-200 text-gray-700"),
    (40, "낮음", "bg-blue-100 text-blue-700"),
    (60, "보통", "bg-green-100 text-green-700"),
    (80, "높음", "bg-yellow-100 text-yellow-800"),
    (101, "매우 높음", "bg-red-100 text-red-800"),
]

CONFIDENCE_MAP = [
    (0.4, "추정 (신뢰도 낮음)", "text-gray-500"),
    (0.7, "보통 (신뢰도 중간)", "text-gray-700"),
    (1.1, "확실 (신뢰도 높음)", "text-blue-700 font-bold"),
]

# (Limit, Label, Description) - COMMENTARY_DB로 대체되었지만 구조 유지
COMMENTARY_DB = {
    "openness": {
        "high": [ # 70+
            "혹시 외계인이세요? 상상력이 지구를 뚫고 나가셨네요!",
            "지루한 건 딱 질색! 늘 새로운 걸 찾아 다니는 모험가시군요.",
            "머릿속에 우주가 들어있는 것 같아요. 창의력 폭발!"
        ],
        "mid": [ # 40~69
            "현실과 이상의 균형을 기가 막히게 잡으시는군요.",
            "필요할 땐 열려있고, 답을 찾을 땐 실용적인 밸런스 마스터."
        ],
        "low": [ # ~39
            "안정이 최고죠! 익숙한 곳에서 오는 편안함을 선호하시네요.",
            "검증된 길만 걷는 당신, 위험한 모험보다는 확실한 성공이 좋죠."
        ]
    },
    "conscientiousness": {
        "high": [
            "계획표를 나노 단위로 짜시나요? 숨 쉬는 시간도 계획에 있나요?",
            "조별 과제의 유일한 희망, 버스 기사님이 여기 계셨군요.",
            "마감 기한은 당신에게 법보다 위에 있는 절대 규칙이군요."
        ],
        "mid": [
            "적당히 계획적이고 적당히 게으른, 아주 인간적인 밸런스네요.",
            "급할 땐 초인적인 집중력을 발휘하지만, 평소엔 평범하시군요."
        ],
        "low": [
            "계획? 그게 먹는 건가요? 인생은 흘러가는 대로~",
            "자유로운 영혼! 즉흥적인 결정이 대박을 터뜨리기도 하죠.",
            "내일 일은 내일의 나에게. 지금 이 순간을 즐기세요!"
        ]
    },
    "extraversion": {
        "high": [
            "전생에 확성기였나요? 에너지가 흘러넘치네요!",
            "침묵을 못 견디는 당신, 단톡방의 분위기 메이커!",
            "당신이 가는 곳이 곧 파티장입니다. 인싸력 MAX."
        ],
        "mid": [
            "상황에 따라 인싸와 아싸를 오가는 하이브리드.",
            "친한 친구랑 있으면 수다쟁이, 낯선 곳에선 관찰자."
        ],
        "low": [
            "사람 만나면 배터리가 광속으로 방전되시는군요.",
            "자발적 아싸? 아니죠, 고효율 솔로 플레이어입니다.",
            "꼭 필요한 말만 하시는군요. 단어당 요금 내시나요?"
        ]
    },
    "agreeableness": {
        "high": [
            "당신이 화내는 걸 본 사람은 유니콘을 본 사람뿐일 거예요.",
            "인간 골든 리트리버? 착하다는 말 듣기 지겨우시죠?",
            "진정한 평화주의자. 당신 덕분에 세상이 좀 더 따뜻하네요."
        ],
        "mid": [
            "평소엔 천사지만 건드리면 뭅니다. 선은 지키는 타입.",
            "호구 잡힐 일은 없겠네요. 내 사람에게만 따뜻한 차도남/차도녀."
        ],
        "low": [
            "팩트 폭격기. 맞는 말인데, 뼈 때려서 좀 아프네요.",
            "남 눈치 왜 봄? 마이웨이 장인이시군요.",
            "논리적이고 냉철합니다. 감정에 휘둘리지 않는 판사님."
        ]
    },
    "neuroticism": {
        "high": [
            "감수성 폭발. 예민 보스 등판!",
            "작은 일에도 잠 못 이루는 섬세한 영혼이시군요.",
            "걱정 인형이 친구하자고 하겠어요. 대비책은 완벽하겠죠?",
        ],
        "mid": [
            "적당한 긴장감은 삶의 원동력이죠. 아주 건강한 멘탈입니다.",
            "가끔 울컥하지만 금방 회복합니다. 회복탄력성 굿."
        ],
        "low": [
            "전쟁이 나도 꿀잠 잘 수 있는 다이아몬드 멘탈.",
            "스트레스가 뭐죠? 평온함의 제왕.",
            "어떤 상황에서도 평정을 잃지 않는 강철 멘탈."
        ]
    }
}

# (Limit, Label, Description)
TRAIT_LEVEL_DESCRIPTIONS = {
    "openness": [
        (20, "매우 낮음", "익숙함과 안정을 최우선으로 하며, 검증된 방식을 선호합니다."),
        (40, "낮음", "현실적이고 실용적인 접근 방식을 중요시합니다."),
        (60, "보통", "현실 감각과 새로운 시도 사이에서 균형을 유지합니다."),
        (80, "높음", "새로운 경험과 지적 탐구를 즐기는 모험가입니다."),
        (101, "매우 높음", "끊임없는 호기심과 풍부한 상상력을 가진 혁신가입니다.")
    ],
    "conscientiousness": [
        (20, "매우 낮음", "즉흥적이고 자유분방하며, 구속받는 것을 싫어합니다."),
        (40, "낮음", "유연함을 선호하며 계획보다는 흐름을 따릅니다."),
        (60, "보통", "필요할 때는 집중하며, 일과 여유의 균형을 찾습니다."),
        (80, "높음", "목표 지향적이며 체계적인 계획을 세워 실행합니다."),
        (101, "매우 높음", "철저한 자기관리와 완벽함을 추구하는 전략가입니다.")
    ],
    "extraversion": [
        (20, "매우 낮음", "혼자만의 시간에서 에너지를 얻는 신중한 관찰자입니다."),
        (40, "낮음", "조용한 환경과 깊이 있는 대화를 선호합니다."),
        (60, "보통", "상황에 따라 사교성과 혼자만의 시간을 조절합니다."),
        (80, "높음", "사람들과 어울리며 에너지를 얻는 분위기 메이커입니다."),
        (101, "매우 높음", "어디서나 활력을 불어넣는 열정적인 사교가입니다.")
    ],
    "agreeableness": [
        (20, "매우 낮음", "논리와 이성을 중시하며, 직설적으로 의견을 표현합니다."),
        (40, "낮음", "타인의 시선보다는 자신의 원칙과 주관을 따릅니다."),
        (60, "보통", "자신의 이익을 지키면서도 타인을 배려할 줄 압니다."),
        (80, "높음", "타인의 감정에 깊이 공감하며, 협력을 중요시합니다."),
        (101, "매우 높음", "따뜻한 마음으로 주변을 챙기는 이타적인 평화주의자입니다.")
    ],
    "neuroticism": [
        (20, "매우 낮음", "어떤 상황에서도 흔들리지 않는 강철 멘탈의 소유자입니다."),
        (40, "낮음", "스트레스를 잘 관리하며 침착함을 유지합니다."),
        (60, "보통", "적당한 긴장감을 느끼지만 일상생활을 잘 영위합니다."),
        (80, "높음", "풍부한 감수성을 지녔으며, 변화에 민감하게 반응합니다."),
        (101, "매우 높음", "작은 일에도 깊이 고민하고 완벽을 기하려 노력합니다.")
    ]
}

SOCIONICS_GENERAL_EXPLANATION = """
소시오닉스(Socionics)는 정보 대사(Information Metabolism) 이론을 기반으로 
사람들이 정보를 어떻게 인식하고 처리하는지 분석하는 심리 유형 이론입니다. 
MBTI와 유사해 보이지만, 대인 관계의 역학(상성)과 심리적 거리를 
훨씬 더 정밀하게 설명하는 데 특화되어 있습니다.
"""

SOCIONICS_DESC_MAP = {
    "ILE": "직관-논리 외향 (발명가) - 새로운 가능성을 탐구하는 혁신가",
    "SEI": "감각-윤리 내향 (중재자) - 편안함과 조화를 추구하는 예술가",
    "ESE": "윤리-감각 외향 (열성가) - 분위기를 주도하는 열정적인 호스트",
    "LII": "논리-직관 내향 (분석가) - 구조와 본질을 꿰뚫는 분석가",
    "EIE": "윤리-직관 외향 (멘토) - 감정을 이끄는 드라마틱한 연설가",
    "LSI": "논리-감각 내향 (감독관) - 체계와 규율을 중시하는 관리자",
    "SLE": "감각-논리 외향 (장군) - 목표를 향해 돌진하는 승부사",
    "IEI": "직관-윤리 내향 (서정가) - 시대의 흐름을 읽는 몽상가",
    "SEE": "감각-윤리 외향 (정치가) - 사람의 마음을 얻는 외교관",
    "ILI": "직관-논리 내향 (비평가) - 흐름을 예측하는 현명한 관찰자",
    "LIE": "논리-직관 외향 (사업가) - 효율과 미래를 보는 개척자",
    "ESI": "윤리-감각 내향 (수호자) - 신의와 원칙을 지키는 가디언",
    "LSE": "논리-감각 외향 (관리자) - 품질과 생산성을 책임지는 전문가",
    "EII": "윤리-직관 내향 (인문주의자) - 내면의 성장을 돕는 치유자",
    "IEE": "직관-윤리 외향 (심리학자) - 잠재력을 발견하는 스카우터",
    "SLI": "감각-논리 내향 (장인) - 감각적 만족과 기술을 즐기는 마에스트로"
}

MBTI_DESC_MAP = {
    "ISTJ": "청렴결백한 논리주의자 (현실주의자)",
    "ISFJ": "용감한 수호자 (실용적인 조력가)",
    "INFJ": "통찰력 있는 선지자 (예언자형)",
    "INTJ": "용의주도한 전략가 (과학자형)",
    "ISTP": "만능 재주꾼 (백과사전형)",
    "ISFP": "호기심 많은 예술가 (성인군자형)",
    "INFP": "열정적인 중재자 (잔다르크형)",
    "INTP": "논리적인 사색가 (아이디어 뱅크)",
    "ESTP": "모험을 즐기는 사업가 (활동가형)",
    "ESFP": "자유로운 영혼의 연예인 (사교적인 유형)",
    "ENFP": "재기발랄한 활동가 (스파크형)",
    "ENTP": "뜨거운 논쟁을 즐기는 변론가 (발명가형)",
    "ESTJ": "엄격한 관리자 (사업가형)",
    "ESFJ": "사교적인 외교관 (친선도모형)",
    "ENFJ": "정의로운 사회운동가 (언변능숙형)",
    "ENTJ": "대담한 통솔자 (지도자형)"
}

def get_trait_content(trait_key, score):
    """
    점수에 따른 트레잇의 모든 텍스트 컴포넌트 반환
    반환값: (Label, Description, WittyComment, CSS)
    """
    if trait_key not in TRAIT_LEVEL_DESCRIPTIONS or trait_key not in COMMENTARY_DB:
        return "N/A", "", "", "text-gray-500"
    
    # 1. 레벨/CSS/라벨 결정 (공통 로직)
    if score is None: score = 0
    if score >= 70:
        level = "high"
    elif score >= 40:
        level = "mid"
    else:
        level = "low"
    
    # 2. 라벨, 설명 가져오기 (TRAIT_LEVEL_DESCRIPTIONS - 정보성)
    label = ""
    description = ""
    start_css = "bg-gray-100 text-gray-800"
    
    # Fallback to SCORE_MAP for CSS
    for limit, l, c in SCORE_MAP:
        if score <= limit:
            start_css = c
            break
            
    for limit, l, desc in TRAIT_LEVEL_DESCRIPTIONS[trait_key]:
        if score <= limit:
            label = l
            description = desc
            break
            
    # 3. 위트 있는 코멘트 가져오기 (COMMENTARY_DB - 재미)
    candidates = COMMENTARY_DB[trait_key][level]
    comment = random.choice(candidates)
    
    return label, description, comment, start_css

def get_combo_comment(scores):
    """복합 로직: 점수 조합에 따른 특수 코멘트 생성"""
    combos = []
    
    # 점수 유효성 검사 (None이면 0 처리)
    o = scores.get('openness') or 0
    c = scores.get('conscientiousness') or 0
    e = scores.get('extraversion') or 0
    a = scores.get('agreeableness') or 0
    n = scores.get('neuroticism') or 0

    # 1. 창의적 전략가 (O High + C High)
    if o >= 70 and c >= 70:
        combos.append({
            "title": "🚀 창의적 전략가 (Creative Strategist)",
            "desc": "아이디어가 넘치는데 실행력까지 미쳤습니다. 혼자서 기획, 개발, 런칭까지 다 해버리는 '1인 유니콘' 기업이시군요!"
        })

    # 2. 몽상가 (O High + C Low)
    if o >= 70 and c <= 40:
        combos.append({
            "title": "☁️ 몽상가 (The Dreamer)",
            "desc": "머릿속엔 테슬라급 혁신이 가득한데 마감일은... 죄송합니다. 당신의 아이디어 금고를 열어줄 꼼꼼한 매니저가 필요해요!"
        })

    # 3. 인간 골든 리트리버 (E High + A High)
    if e >= 70 and a >= 70:
        combos.append({
            "title": "🐶 인간 골든 리트리버",
            "desc": "어딜 가나 사랑받는 인싸! 당신 주변엔 웃음꽃이 핍니다. 꼬리만 없을 뿐, 사람 좋아하는 건 강아지급이네요."
        })

    # 4. 불도저 (E High + A Low)
    if e >= 70 and a <= 40:
        combos.append({
            "title": "🚜 불도저 리더",
            "desc": "'나를 따르라!' 카리스마가 철철 넘칩니다. 목표를 위해 직진하는 상남자/걸크러쉬. 팩트 폭격은 덤입니다."
        })

    # 5. 불안한 완벽주의자 (N High + C High)
    if n >= 70 and c >= 70:
        combos.append({
            "title": "⚡ 불안한 완벽주의자",
            "desc": "99점은 용납 못 해. 100점을 위해 밤새 수정하고 또 수정합니다. 결과물은 완벽하지만, 수면 상태는 괜찮으신가요?"
        })

    # 6. 감정 스펀지 (N High + A High)
    if n >= 70 and a >= 70:
        combos.append({
            "title": "💧 감정 스펀지 (Empath)",
            "desc": "남의 슬픔이 곧 나의 슬픔. 영화 보고 오열하고, 친구 고민 들어주다 밤샙니다. 진정한 공감요정."
        })

    # 7. 해탈한 신선 (N Low + C Low)
    if n <= 40 and c <= 40:
        combos.append({
            "title": "🧘 해탈한 신선 (Zen Master)",
            "desc": "세상이 무너져도 '아 그래?' 하고 잡니다. 스트레스가 피해 가는 무의 경지에 도달하셨군요."
        })
        
    # 8. 고독한 늑대 (E Low + C High)
    if e <= 40 and c >= 70:
        combos.append({
             "title": "🐺 고독한 늑대",
             "desc": "혼자일 때 효율이 200% 상승합니다. 팀플보다 솔플, 애매한 협력보다 확실한 성과. '고효율 솔로 플레이어' 등극!"
        })

    if not combos:
        return ""
    
    # 콤보 HTML 생성
    html_parts = []
    html_parts.append('<section class="glass-panel rounded-2xl p-8 border-2 border-indigo-100 relative overflow-hidden">')
    html_parts.append('<div class="absolute top-0 right-0 p-4 opacity-5 text-8xl">🌟</div>')
    html_parts.append('<h2 class="text-xl font-bold text-indigo-900 mb-6 flex items-center">✨ 특수 조합 분석 <span class="ml-2 text-xs font-normal text-indigo-500 bg-indigo-50 px-2 py-1 rounded-full">Hidden Achievement!</span></h2>')
    html_parts.append('<div class="grid grid-cols-1 gap-4">')
    
    for c in combos:
        html_parts.append(f'''
        <div class="bg-gradient-to-r from-indigo-50 to-purple-50 p-5 rounded-xl border border-indigo-100 hover:shadow-md transition-shadow">
            <h3 class="font-bold text-indigo-700 text-lg mb-2">{c['title']}</h3>
            <p class="text-slate-700 text-sm leading-relaxed">{c['desc']}</p>
        </div>
        ''')
    
    html_parts.append('</div></section>')
    
    return "\n".join(html_parts)

def get_score_text(score):
    """0-100 점수를 텍스트 뱃지로 변환"""
    if score is None: return "N/A", ""
    for limit, label, css in SCORE_MAP:
        if score <= limit:
            return label, css
    return "매우 높음", "bg-red-100 text-red-800"

def get_confidence_text(conf):
    """0.0-1.0 신뢰도를 텍스트로 변환"""
    if conf is None: return "알 수 없음", ""
    for limit, label, css in CONFIDENCE_MAP:
        if conf <= limit:
            return label, css
    return "확실", "text-blue-700 font-bold"

# -------------------------------------------------------------------------
# 템플릿 (Templates)
# -------------------------------------------------------------------------

HTML_HEAD_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EchoMind 프로필 리포트</title>
    <!-- Tailwind CSS (CDN) -->
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
        body {{ font-family: 'Noto Sans KR', sans-serif; }}
        .glass-panel {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }}
    </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen p-6 md:p-12">
"""

HTML_BODY_TEMPLATE = """
    <div class="max-w-4xl mx-auto space-y-8">
        
        <!-- 헤더 -->
        <header class="text-center py-10">
            <h1 class="text-4xl font-extrabold text-slate-900 tracking-tight mb-2">EchoMind Insight</h1>
            <div class="text-slate-500 text-sm">
                분석 대상: <span class="font-medium text-slate-900">{speaker_name}</span> | 
                생성일: {date_str}
            </div>
        </header>

        <!-- 요약 (Executive Summary) -->
        <section class="glass-panel rounded-2xl p-8">
            <h2 class="text-xl font-bold text-slate-900 mb-4 border-b pb-2 border-slate-100">💡 핵심 요약</h2>
            <p class="text-lg leading-relaxed text-slate-700">
                {summary_text}
            </p>
            <div class="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                {comm_bullets}
            </div>
        </section>

        <!-- 메인 성격 유형 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- MBTI -->
            <section class="glass-panel rounded-2xl p-6 relative overflow-hidden group hover:shadow-lg transition-all duration-300">
                <div class="absolute top-0 right-0 p-4 opacity-10 text-6xl font-black text-indigo-900 select-none group-hover:scale-110 transition-transform">MBTI</div>
                <h3 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-1">성격 유형 (MBTI)</h3>
                <div class="flex flex-col mb-4">
                    <span class="text-4xl font-bold text-indigo-600">{mbti_type}</span>
                    <span class="text-sm text-indigo-800 bg-indigo-50 px-2 py-1 rounded mt-1 inline-block self-start font-medium">{mbti_desc_str}</span>
                </div>
                 <div class="text-xs {mbti_conf_css} mb-2">신뢰도: {mbti_conf_text}</div>
                <ul class="space-y-2">
                    {mbti_reasons}
                </ul>
            </section>

            <!-- 소시오닉스 -->
            <section class="glass-panel rounded-2xl p-6 relative overflow-hidden group hover:shadow-lg transition-all duration-300">
                <div class="absolute top-0 right-0 p-4 opacity-10 text-6xl font-black text-rose-900 select-none group-hover:scale-110 transition-transform">SOC</div>
                <h3 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-1">소시오닉스 유형</h3>
                <div class="flex flex-col mb-4">
                     <span class="text-4xl font-bold text-rose-600">{soc_type}</span>
                     <span class="text-sm text-rose-800 bg-rose-50 px-2 py-1 rounded mt-1 inline-block self-start font-medium">{soc_desc_str}</span>
                </div>
                 <div class="text-xs {soc_conf_css} mb-2">신뢰도: {soc_conf_text}</div>
                <ul class="space-y-2">
                    {soc_reasons}
                </ul>
            </section>
        </div>

        <!-- Big 5 특성 -->
        <section class="glass-panel rounded-2xl p-8">
            <h2 class="text-xl font-bold text-slate-900 mb-6 border-b pb-2 border-slate-100">🌊 Big 5 성격 요인</h2>
            <div class="space-y-6">
                {big5_rows}
            </div>
             <div class="mt-4 text-right text-xs text-slate-400">
                * 전체 신뢰도: <span class="{big5_conf_css}">{big5_conf_text}</span>
            </div>
        </section>

        <!-- 특수 분석 (Combo) -->
        {special_analysis_section}

        <!-- 주의사항 -->
        <section class="rounded-xl border border-slate-200 bg-slate-50 p-6 text-slate-500 text-sm">
            <h3 class="font-semibold text-slate-700 mb-2">⚠️ 주의사항 및 한계</h3>
            <ul class="list-disc pl-5 space-y-1">
                {caveats}
            </ul>
        </section>

    </div>
"""

HTML_FOOTER_TEMPLATE = """
</body>
</html>
"""

BIG5_ROW_TEMPLATE = """
<div class="grid grid-cols-1 md:grid-cols-12 gap-4 items-start py-4 border-b border-slate-50 last:border-0 hover:bg-slate-50/50 transition-colors rounded-lg px-2">
    <div class="md:col-span-3">
        <h4 class="font-medium text-slate-900">{trait_name}</h4>
        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {badge_css}">
            {badge_text}
        </span>
    </div>
    <div class="md:col-span-9 text-slate-600 text-sm leading-relaxed">
        {trait_desc}
    </div>
</div>
"""

# -------------------------------------------------------------------------
# 핵심 로직 (Core Logic)
# -------------------------------------------------------------------------

def generate_report_html(data: dict, return_body_only=False) -> str:
    """
    JSON Dict 데이터를 입력받아 렌더링된 HTML 문자열을 반환합니다.
    return_body_only=True: <html> 태그 없이 body 내용만 반환합니다 (웹 앱 내장용).
    """
    
    # [Robustness] 데이터 구조 유연성 처리
    # 1. 표준 구조: top-level에 'llm_profile' 키가 있는 경우
    if 'llm_profile' in data:
        meta = data.get("meta", {})
        profile = data.get("llm_profile", {})
    # 2. 레거시/플랫 구조: top-level 자체가 profile인 경우
    else:
        profile = data
        meta = data.get("meta", {})
        # 만약 meta가 profile 내부에 없다면 기본값 사용

    # 1. 헤더
    speaker_name = html.escape(meta.get("speaker_name", "Unknown"))
    gen_time = meta.get("generated_at_utc", "")
    try:
        date_obj = datetime.fromisoformat(gen_time.replace("Z", "+00:00"))
        date_str = date_obj.strftime("%Y-%m-%d")
    except:
        date_str = gen_time

    # 2. 요약
    summary = profile.get("summary", {})
    summary_text = html.escape(summary.get("one_paragraph", ""))
    comm_list = summary.get("communication_style_bullets", [])
    comm_bullets = "\n".join([f'<div class="flex items-start"><span class="text-indigo-500 mr-2">▪</span><span>{html.escape(c)}</span></div>' for c in comm_list])

    # 3. MBTI
    mbti = profile.get("mbti", {})
    mbti_type = html.escape(mbti.get("type", "Unknown"))
    
    # MBTI 설명 매핑
    mbti_desc_str = MBTI_DESC_MAP.get(mbti_type.upper(), "")

    mConf, mCss = get_confidence_text(mbti.get("confidence"))
    mbti_reasons = "\n".join([f'<li class="text-sm text-slate-600 list-disc list-inside">{html.escape(r)}</li>' for r in mbti.get("reasons", [])])

    # 4. 소시오닉스
    soc = profile.get("socionics", {})
    soc_type = html.escape(soc.get("type", "Unknown"))
    
    # 소시오닉스 설명 로직
    soc_key = soc_type.split()[0].upper() if soc_type else ""
    # 알파벳만 남기기
    import re
    soc_key = re.sub(r'[^A-Z]', '', soc_key)
    
    soc_desc_str = SOCIONICS_DESC_MAP.get(soc_key, "Unknown Type")
    
    sConf, sCss = get_confidence_text(soc.get("confidence"))
    soc_reasons = "\n".join([f'<li class="text-sm text-slate-600 list-disc list-inside">{html.escape(r)}</li>' for r in soc.get("reasons", [])])

    # 소시오닉스 전체 유형 리스트 생성 (정렬)
    socionics_all_types_html = ""
    sorted_soc_keys = sorted(SOCIONICS_DESC_MAP.keys())
    for k in sorted_soc_keys:
         desc = SOCIONICS_DESC_MAP[k]
         # 현재 유형 강조
         bg_class = "bg-rose-100 font-bold text-rose-800" if k == soc_key else ""
         socionics_all_types_html += f'<div class="p-1 {bg_class}"><span class="font-bold">{k}</span>: {desc}</div>'

    # 소시오닉스 일반 설명 추가 (접기/펼치기)
    soc_reasons += f"""
    <div class="mt-4 pt-4 border-t border-slate-100">
        <details class="group">
            <summary class="list-none cursor-pointer text-xs font-semibold text-rose-500 hover:text-rose-700 flex items-center transition-colors select-none">
                <span class="mr-1">❓ 소시오닉스란?</span>
                <span class="group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <div class="text-xs text-slate-500 mt-2 bg-rose-50 p-4 rounded leading-relaxed">
                <p class="mb-3">{SOCIONICS_GENERAL_EXPLANATION.strip()}</p>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3 border-t border-rose-200 pt-3">
                    {socionics_all_types_html}
                </div>
            </div>
        </details>
    </div>
    """

    # 5. Big 5
    big5 = profile.get("big5", {})
    scores = big5.get("scores_0_100", {})
    reasons = big5.get("reasons", [])
    
    trait_keys = {
        "openness": ["Openness", "openness", "개방성"],
        "conscientiousness": ["Conscientiousness", "conscientiousness", "성실성"],
        "extraversion": ["Extraversion", "extraversion", "외향성"],
        "agreeableness": ["Agreeableness", "agreeableness", "우호성", "친화성"],
        "neuroticism": ["Neuroticism", "neuroticism", "신경성", "민감성"]
    }
    
    display_names = {
        "openness": "개방성 (Openness)",
        "conscientiousness": "성실성 (Conscientiousness)",
        "extraversion": "외향성 (Extraversion)",
        "agreeableness": "우호성 (Agreeableness)",
        "neuroticism": "신경성 (Neuroticism)"
    }
    
    # 이유 매핑 로직 정규화
    reason_map = {}
    for r in reasons:
        # LLM output might be "Openness: Blah"
        lower_r = r.lower()
        matched_key = None
        cleaned_val = r

        # 콜론으로 분리 시도
        parts = r.split(":", 1)
        if len(parts) == 2:
            key_part = parts[0].strip().lower()
            val_part = parts[1].strip()
            
            # 키 부분에 트레잇 키워드가 있는지 확인
            for t_key, keywords in trait_keys.items():
                if any(k in key_part for k in keywords):
                    matched_key = t_key
                    cleaned_val = val_part
                    break
        
        # 콜론이 없거나 매칭 실패 시 전체 문자열 검색
        if not matched_key:
            for t_key, keywords in trait_keys.items():
                if any(k in lower_r for k in keywords):
                    matched_key = t_key
                    # 키워드로 찾은 경우 전체 문장을 이유로 사용
                    break
        
        if matched_key:
            reason_map[matched_key] = cleaned_val

    big5_rows_html = []
    for key, display_name in display_names.items():
        score = scores.get(key)
        
        # 통합 로직 호출
        label, description, witty_comment, badge_css = get_trait_content(key, score)
        
        # LLM 이유 (AI Note)
        raw_reason = reason_map.get(key, "")
        
        # HTML 설명 블록 구성
        # 1. 정보성 설명 (Bold or Primary)
        desc_html = f"<div class='font-medium text-slate-800 mb-2'>{description}</div>"
        
        # 2. 위트 코멘트 (강조 박스)
        desc_html += f"<div class='text-sm text-indigo-600 bg-indigo-50/30 px-3 py-2 rounded-lg border border-indigo-50 mb-2'>💬 \"{witty_comment}\"</div>"

        # 3. AI Note (접기/펼치기)
        if raw_reason:
            desc_html += f"""
            <details class="group">
                <summary class="list-none cursor-pointer text-xs text-slate-400 hover:text-slate-600 flex items-center transition-colors select-none">
                    <span class="mr-1">🤖 AI 분석 노트</span>
                    <span class="group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <div class="text-xs text-slate-500 mt-2 pl-2 border-l-2 border-slate-200 bg-slate-50/50 p-2 rounded">
                    {html.escape(raw_reason)}
                </div>
            </details>
            """

        big5_rows_html.append(BIG5_ROW_TEMPLATE.format(
            trait_name=display_name,
            badge_text=label,
            badge_css=badge_css,
            trait_desc=desc_html
        ))
    
    bConf, bCss = get_confidence_text(big5.get("confidence"))

    # 특수 분석
    special_analysis_html = get_combo_comment(scores)

    # 6. 주의사항
    caveats = profile.get("caveats", [])
    caveats_html = "\n".join([f'<li>{html.escape(c)}</li>' for c in caveats])

    # 바디 렌더링
    body_content = HTML_BODY_TEMPLATE.format(
        speaker_name=speaker_name,
        date_str=date_str,
        summary_text=summary_text,
        comm_bullets=comm_bullets,
        mbti_type=mbti_type,
        mbti_desc_str=mbti_desc_str,
        mbti_conf_text=mConf,
        mbti_conf_css=mCss,
        mbti_reasons=mbti_reasons,
        soc_type=soc_type,
        soc_desc_str=soc_desc_str,
        soc_conf_text=sConf,
        soc_conf_css=sCss,
        soc_reasons=soc_reasons,
        big5_rows="\n".join(big5_rows_html),
        big5_conf_text=bConf,
        big5_conf_css=bCss,
        special_analysis_section=special_analysis_html,
        caveats=caveats_html
    )

    if return_body_only:
        return body_content
    
    return HTML_HEAD_TEMPLATE + body_content + HTML_FOOTER_TEMPLATE

# -------------------------------------------------------------------------
# CLI 헬퍼 (CLI Helper)
# -------------------------------------------------------------------------

import argparse

# -------------------------------------------------------------------------
# 대시보드 통계 (Dashboard Stats)
# -------------------------------------------------------------------------

def generate_dashboard_stats():
    """
    [Admin] 대시보드용 통계 데이터 생성
    DB에서 모든 성향 분석 결과(최신/대표)를 집계하여 반환합니다.
    """
    from extensions import db, PersonalityResult, User
    from sqlalchemy import func
    from collections import Counter

    try:
        # 1. 대표 성향 결과 모두 조회 (탈퇴자 제외 등은 비즈니스 로직에 따름)
        #    더미 사용자 포함
        results = db.session.query(PersonalityResult).filter_by(is_representative=True).all()
        
        if not results:
            return {
                'mbti': {'full': {'labels': [], 'data': []}, 'ei': {}, 'sn': {}, 'tf': {}, 'pj': {}},
                'socionics': {'full': {'labels': [], 'data': []}, 'ei': {}, 'sn': {}, 'tf': {}, 'pj': {}},
                'big5': {'labels': ['개방성', '성실성', '외향성', '우호성', '신경성'], 'data': [0, 0, 0, 0, 0]}
            }

        # 2. MBTI 집계
        mbti_types = [r.mbti_prediction for r in results if r.mbti_prediction]
        mbti_counts = Counter(mbti_types)
        
        # 지표별 분해 (E/I, S/N, T/F, P/J)
        mbti_ei = {'E': 0, 'I': 0}
        mbti_sn = {'S': 0, 'N': 0}
        mbti_tf = {'T': 0, 'F': 0}
        mbti_pj = {'P': 0, 'J': 0}
        
        for m in mbti_types:
            if len(m) != 4: continue
            mbti_ei[m[0]] += 1
            mbti_sn[m[1]] += 1
            mbti_tf[m[2]] += 1
            mbti_pj[m[3]] += 1
            
        # 3. Socionics 집계
        soc_types = [r.socionics_prediction for r in results if r.socionics_prediction]
        soc_counts = Counter(soc_types)
        
        # 지표별 (Socionics는 마지막 글자가 소문자 p/j일 수 있음, 혹은 3글자 코드)
        # 여기서는 단순 4글자 기준(MBTI 매핑)이 아니므로 Full Type 위주로 하되,
        # 편의상 앞글자(E/I), 두번째(N/S), 세번째(T/F), 네번째(j/p) 로직이 복잡하므로 Full Count만 주로 사용.
        # 기존 코드가 ei/sn/tf/pj를 요구하므로 더미 데이터를 채우거나 약식 로직 사용.
        # 소시오닉스 코드는 보통 ILE, SEI 등 3글자임.
        # 따라서 E/I 등 상세 지표는 3글자 코드 특성에 맞춰 변환해야 함.
        # 여기서는 Full Chart만 중요하므로 나머지는 빈 값 처리하거나 단순 집계.
        
        # 4. Big5 평균
        b_count = len(results)
        avg_o = sum([r.openness for r in results]) / b_count
        avg_c = sum([r.conscientiousness for r in results]) / b_count
        avg_e = sum([r.extraversion for r in results]) / b_count
        avg_a = sum([r.agreeableness for r in results]) / b_count
        avg_n = sum([r.neuroticism for r in results]) / b_count
        
        # 5. 결과 구조화
        mbti_dist = mbti_counts.most_common()
        soc_dist = soc_counts.most_common()
        
        return {
            'mbti': {
                'full': {'labels': [x[0] for x in mbti_dist], 'data': [x[1] for x in mbti_dist]},
                'ei': {'labels': list(mbti_ei.keys()), 'data': list(mbti_ei.values())},
                'sn': {'labels': list(mbti_sn.keys()), 'data': list(mbti_sn.values())},
                'tf': {'labels': list(mbti_tf.keys()), 'data': list(mbti_tf.values())},
                'pj': {'labels': list(mbti_pj.keys()), 'data': list(mbti_pj.values())}
            },
            'socionics': {
                'full': {'labels': [x[0] for x in soc_dist], 'data': [x[1] for x in soc_dist]},
                'ei': {'labels': ['Extro', 'Intro'], 'data': [0, 0]}, # TODO: Implement if needed
                'sn': {'labels': ['Sensing', 'Intuition'], 'data': [0, 0]},
                'tf': {'labels': ['Thinking', 'Feeling'], 'data': [0, 0]},
                'pj': {'labels': ['Judging', 'Perceiving'], 'data': [0, 0]}
            },
            'big5': {
                'labels': ['개방성', '성실성', '외향성', '우호성', '신경성'],
                'data': [round(avg_o, 1), round(avg_c, 1), round(avg_e, 1), round(avg_a, 1), round(avg_n, 1)]
            }
        }
        
    except Exception as e:
        print(f"Stats Generation Error: {e}")
        return {}


def main():
    parser = argparse.ArgumentParser(description="JSON 프로필을 HTML 리포트로 변환")
    parser.add_argument("input_file", nargs="?", default="profile.json", help="입력 JSON 파일 경로 (기본값: profile.json)")
    parser.add_argument("--out", "-o", help="출력 HTML 파일 경로 (기본값: [입력파일명].html)")

    args = parser.parse_args()

    json_path = args.input_file
    
    # 출력 경로 결정
    if args.out:
        html_path = args.out
    else:
        # e.g., data/my_profile.json -> data/my_profile.html
        base, _ = os.path.splitext(json_path)
        html_path = base + ".html"
        
        if json_path == "profile.json" and not args.out:
            html_path = "profile_report.html"

    if not os.path.exists(json_path):
        print(f"오류: '{json_path}' 파일을 찾을 수 없습니다.")
        sys.exit(1)

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"JSON 파일 읽기 오류: {e}")
        sys.exit(1)

    try:
        html_content = generate_report_html(data)
    except Exception as e:
        print(f"HTML 생성 오류: {e}")
        sys.exit(1)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"성공적으로 생성되었습니다: {html_path} (from {json_path})")

if __name__ == "__main__":
    main()
