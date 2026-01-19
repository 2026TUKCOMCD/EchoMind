"""
[스크립트 사용 가이드]

이 스크립트는 JSON 형식의 프로필 데이터를 읽어 시각화된 HTML 보고서를 생성합니다.
서버 환경에서는 `generate_report_html` 함수를 import하여 직접 사용할 수도 있습니다.

사용 방법:
    python visualize_profile.py [입력_파일_경로] [옵션]

기본 사용 예시:
    python visualize_profile.py
    # 현재 디렉토리의 profile.json을 읽어 profile_report.html 생성

    python visualize_profile.py data/user_123.json
    # data/user_123.json을 읽어 data/user_123.html 생성

옵션:
    input_file          입력할 JSON 파일 경로 (기본값: profile.json)
    -o, --out           출력할 HTML 파일 경로 지정 (기본값: 입력 파일명과 동일하되 확장자만 .html)
                        입력 파일이 profile.json일 경우 기본 출력은 profile_report.html입니다.

함수 사용 (Python 내부):
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
# Configuration / Mappings
# -------------------------------------------------------------------------

SCORE_MAP = [
    (20, "매우 낮음", "bg-gray-200 text-gray-700"),
    (40, "낮음", "bg-blue-100 text-blue-700"),
    (60, "보통", "bg-green-100 text-green-700"),
    (80, "높음", "bg-yellow-100 text-yellow-800"),
    (101, "매우 높음", "bg-red-100 text-red-800"),
]

CONFIDENCE_MAP = [
    (0.4, "추정 (낮은 신뢰도)", "text-gray-500"),
    (0.7, "보통 (일반적 신뢰도)", "text-gray-700"),
    (1.1, "확실 (높은 신뢰도)", "text-blue-700 font-bold"),
]

# (Limit, Label, Description) - DEPRECATED in favor of COMMENTARY_DB
# But kept structure if needed, or we just replace it fully.
# Replacing fully with Dictionary-based approach as requested.

COMMENTARY_DB = {
    "openness": {
        "high": [ # 70+
            "혹시 외계인이세요? 상상력의 차원이 다르시네요!",
            "지루한 건 딱 질색! 늘 새로움을 찾아 떠나는 모험가.",
            "당신의 머릿속엔 우주가 들어있군요. 창의력이 폭발합니다."
        ],
        "mid": [ # 40~69
            "현실과 이상의 줄타기 장인. 균형 잡힌 시각을 가지셨네요.",
            "필요할 땐 열려있고, 아닐 땐 답을 찾는 실용주의자."
        ],
        "low": [ # ~39
            "변화보다는 익숙한 국밥 한 그릇이 최고죠. 안정이 제일!",
            "검증된 길만 걷습니다. 모험보다는 확실한 성공을 선호해요."
        ]
    },
    "conscientiousness": {
        "high": [
            "당신의 계획표는 나노 단위입니다. 숨 쉬는 시간도 계획하셨나요?",
            "조별과제의 유일한 희망, 버스 기사님이시군요.",
            "마감 기한은 당신에게 법보다 위에 있는 절대 규칙입니다."
        ],
        "mid": [
            "적당히 계획적이고 적당히 게으른, 아주 인간적인 밸런스입니다.",
            "급할 때는 초인적인 집중력을 발휘하지만, 평소엔 평범하시네요."
        ],
        "low": [
            "계획? 그게 뭐죠? 먹는 건가요? 인생은 흘러가는 대로~",
            "자유로운 영혼! 즉흥적인 결정이 때론 로또가 되기도 하죠.",
            "내일의 일은 내일의 나에게 맡긴다. 현재를 즐기는 당신!"
        ]
    },
    "extraversion": {
        "high": [
            "혹시 전생에 확성기였나요? 에너지가 넘치십니다!",
            "침묵을 못 견디는 타입. 단톡방의 분위기 메이커!",
            "당신이 가는 곳이 곧 파티장입니다. 인싸력 만랩."
        ],
        "mid": [
            "상황에 따라 인싸와 아싸를 오가는 하이브리드.",
            "친한 사람들에겐 수다쟁이, 낯선 자리에선 관찰자."
        ],
        "low": [
            "당신의 배터리는 사람을 만나면 광속으로 방전됩니다.",
            "자발적 아싸? 아니요, 고효율 솔로 플레이어입니다.",
            "필요한 말만 하는 당신, 혹시 1타당 과금되나요?"
        ]
    },
    "agreeableness": {
        "high": [
            "당신이 화내는 걸 본 사람은 전설 속 유니콘뿐일 겁니다.",
            "인간 골든 리트리버? 성격 좋다는 말 지겹게 들으시죠?",
            "평화주의자 그 자체. 당신 덕분에 세상이 좀 더 따뜻합니다."
        ],
        "mid": [
            "착할 땐 천사, 건드리면... 아시죠? 적당한 선을 지킵니다.",
            "무조건 져주진 않습니다. 내 사람에게만 따뜻한 타입."
        ],
        "low": [
            "팩트 폭력배. 당신 말은 맞는데, 뼈가 좀 아프네요.",
            "남 눈치 안 보고 내 갈 길 간다. 마이웨이 장인.",
            "논리적이고 냉철합니다. 감정에 휩쓸리지 않는 판사님."
        ]
    },
    "neuroticism": {
        "high": [
            "감수성이 풍부하다 못해 넘쳐흐릅니다. 예민보스 등장!",
            "작은 일에도 밤잠 설치는 섬세한 영혼.",
            "걱정인형이 친구하자고 하겠어요. 대비책은 완벽하겠네요."
        ],
        "mid": [
            "적당한 긴장감은 삶의 원동력. 아주 건강한 멘탈입니다.",
            "가끔 울컥하지만 금방 털어냅니다. 회복탄력성 굿."
        ],
        "low": [
            "멘탈이 다이아몬드급입니다. 전쟁이 나도 꿀잠 잘 기세.",
            "스트레스가 뭐죠? 무던함의 끝판왕.",
            "어떤 상황에서도 평정심을 잃지 않는 강철 멘탈."
        ]
    }
}

# (Limit, Label, Description)
TRAIT_LEVEL_DESCRIPTIONS = {
    "openness": [
        (20, "매우 낮음", "익숙함과 안정을 최우선하며 검증된 방식을 선호합니다."),
        (40, "낮음", "현실적이고 실용적인 접근을 중시합니다."),
        (60, "보통", "현실 감각과 새로운 시도 사이의 균형을 유지합니다."),
        (80, "높음", "새로운 경험과 지적 탐구를 즐기는 모험가입니다."),
        (101, "매우 높음", "끊임없는 호기심과 풍부한 상상력을 가진 혁신가입니다.")
    ],
    "conscientiousness": [
        (20, "매우 낮음", "즉흥적이고 자유로운 영혼의 소유자입니다."),
        (40, "낮음", "유연함을 선호하며 계획보다는 흐름을 따르는 편입니다."),
        (60, "보통", "필요할 때 집중하며 일과 여유의 균형을 찾습니다."),
        (80, "높음", "목표 지향적이며 체계적인 계획을 세웁니다."),
        (101, "매우 높음", "철저한 자기관리와 완벽을 추구하는 전략가입니다.")
    ],
    "extraversion": [
        (20, "매우 낮음", "혼자만의 시간에서 에너지를 얻는 신중한 관찰자입니다."),
        (40, "낮음", "조용한 환경과 깊이 있는 대화를 선호합니다."),
        (60, "보통", "상황에 따라 사교성과 혼자만의 시간을 조절합니다."),
        (80, "높음", "사람들과 어울리며 에너지를 얻는 분위기 메이커입니다."),
        (101, "매우 높음", "언제 어디서나 활력을 불어넣는 열정적인 사교가입니다.")
    ],
    "agreeableness": [
        (20, "매우 낮음", "논리와 이성을 중시하며 직설적으로 의견을 표현합니다."),
        (40, "낮음", "타인의 시선보다는 자신의 원칙과 주관을 따릅니다."),
        (60, "보통", "자신의 이익을 지키면서도 타인을 배려할 줄 압니다."),
        (80, "높음", "타인의 감정에 공감하며 협력과 조화를 중시합니다."),
        (101, "매우 높음", "따뜻한 마음으로 주변을 돌보는 이타적인 평화주의자입니다.")
    ],
    "neuroticism": [
        (20, "매우 낮음", "어떤 상황에서도 흔들리지 않는 강철 멘탈의 소유자입니다."),
        (40, "낮음", "스트레스를 잘 관리하며 평정심을 유지합니다."),
        (60, "보통", "적당한 긴장감을 느끼지만 일상생활을 잘 영위합니다."),
        (80, "높음", "감수성이 풍부하고 주변 변화에 민감하게 반응합니다."),
        (101, "매우 높음", "작은 일에도 깊이 고민하며 완벽을 기하려 노력합니다.")
    ]
}

SOCIONICS_GENERAL_EXPLANATION = """
소시오닉스(Socionics)는 정보 대사 과정에 기반한 심리 유형 이론으로, 
사람이 정보를 어떻게 받아들이고 처리하는지를 분석합니다. 
MBTI와 유사해 보이지만, 특히 대인 관계와 심리적 거리를 
더욱 정교하게 설명하는 데 강점이 있습니다.
"""

SOCIONICS_DESC_MAP = {
    "ILE": "직관-논리 외향 (발명가형) - 새로운 가능성을 탐구하는 혁신가",
    "SEI": "감각-윤리 내향 (중재자형) - 편안함과 조화를 추구하는 예술가",
    "ESE": "윤리-감각 외향 (사교가형) - 분위기를 주도하는 열정적인, 호스트",
    "LII": "논리-직관 내향 (분석가형) - 구조와 본질을 꿰뚫는 분석가",
    "EIE": "윤리-직관 외향 (멘토형) - 감정을 이끄는 드라마틱한 연설가",
    "LSI": "논리-감각 내향 (감독관형) - 체계와 규율을 중시하는 관리자",
    "SLE": "감각-논리 외향 (사령관형) - 목표를 향해 돌진하는 승부사",
    "IEI": "직관-윤리 내향 (서정가형) - 시간의 흐름을 읽는 몽상가",
    "SEE": "감각-윤리 외향 (정치가형) - 사람의 마음을 얻는 외교관",
    "ILI": "직관-논리 내향 (비평가형) - 흐름을 예측하는 현명한 관찰자",
    "LIE": "논리-직관 외향 (사업가형) - 효율과 미래를 보는 개척자",
    "ESI": "윤리-감각 내향 (보호자형) - 신의와 원칙을 지키는 수호자",
    "LSE": "논리-감각 외향 (관리자형) - 품질과 생산성을 책임지는 전문가",
    "EII": "윤리-직관 내향 (인문학자형) - 내면의 성장을 돕는 치유자",
    "IEE": "직관-윤리 외향 (상담가형) - 사람의 잠재력을 발견하는 스카우터",
    "SLI": "감각-논리 내향 (장인형) - 감각적 만족과 기술을 즐기는 마에스트로"
}

MBTI_DESC_MAP = {
    "ISTJ": "청렴결백한 논리주의자 (Logistician)",
    "ISFJ": "용감한 수호자 (Defender)",
    "INFJ": "선의의 옹호자 (Advocate)",
    "INTJ": "용의주도한 전략가 (Architect)",
    "ISTP": "만능 재주꾼 (Virtuoso)",
    "ISFP": "호기심 많은 예술가 (Adventurer)",
    "INFP": "열정적인 중재자 (Mediator)",
    "INTP": "논리적인 사색가 (Logician)",
    "ESTP": "모험을 즐기는 사업가 (Entrepreneur)",
    "ESFP": "자유로운 영혼의 연예인 (Entertainer)",
    "ENFP": "재기발랄한 활동가 (Campaigner)",
    "ENTP": "뜨거운 논쟁을 즐기는 변론가 (Debater)",
    "ESTJ": "엄격한 관리자 (Executive)",
    "ESFJ": "사교적인 외교관 (Consul)",
    "ENFJ": "정의로운 사회운동가 (Protagonist)",
    "ENTJ": "대담한 통솔자 (Commander)"
}

def get_trait_content(trait_key, score):
    """
    Return all text components for a trait based on score.
    Returns: (Label, Description, WittyComment, CSS)
    """
    if trait_key not in TRAIT_LEVEL_DESCRIPTIONS or trait_key not in COMMENTARY_DB:
        return "N/A", "", "", "text-gray-500"
    
    # 1. Determine Level/CSS/Label (Shared logic)
    if score >= 70:
        level = "high"
        # Label is usually consistent with SCORE_MAP but we can just use the one from TRAIT_LEVEL_DESCRIPTIONS
    elif score >= 40:
        level = "mid"
    else:
        level = "low"
    
    # 2. Get Label, Description from TRAIT_LEVEL_DESCRIPTIONS (Informative)
    # We iterate to find the matching tuple
    label = ""
    description = ""
    start_css = "bg-gray-100 text-gray-800"
    
    # Fallback to SCORE_MAP for CSS if needed
    for limit, l, c in SCORE_MAP:
        if score <= limit:
            start_css = c
            break
            
    for limit, l, desc in TRAIT_LEVEL_DESCRIPTIONS[trait_key]:
        if score <= limit:
            label = l
            description = desc
            break
            
    # 3. Get Witty Comment from COMMENTARY_DB (Fun)
    candidates = COMMENTARY_DB[trait_key][level]
    comment = random.choice(candidates)
    
    return label, description, comment, start_css

def get_combo_comment(scores):
    """복합 로직: 두 가지 이상의 점수를 조합하여 특수 멘트 생성"""
    combos = []
    
    o = scores.get('openness', 0)
    c = scores.get('conscientiousness', 0)
    e = scores.get('extraversion', 0)
    a = scores.get('agreeableness', 0)
    n = scores.get('neuroticism', 0)

    # 1. Creative Strategist (O High + C High)
    if o >= 70 and c >= 70:
        combos.append({
            "title": "🚀 창의적 전략가 (Creative Strategist)",
            "desc": "아이디어도 넘치는데 실행력까지 미쳤습니다. 당신은 혼자서 기획하고 개발하고 런칭까지 할 수 있는 '1인 유니콘 기업' 그 자체군요!"
        })

    # 2. Dreamer (O High + C Low)
    if o >= 70 and c <= 40:
        combos.append({
            "title": "☁️ 자유로운 발명가 (The Dreamer)",
            "desc": "머릿속은 테슬라급 혁신으로 가득하지만, 마감일은... 죄송합니다. 아이디어 뱅크인 당신에겐 꼼꼼한 매니저가 필수!"
        })

    # 3. Golden Retriever (E High + A High)
    if e >= 70 and a >= 70:
        combos.append({
            "title": "🐶 인간 골든 리트리버",
            "desc": "어딜 가나 사랑받는 인싸! 당신 주변엔 항상 웃음꽃이 핍니다. 꼬리만 없을 뿐, 사람을 좋아하는 건 강아지급이네요."
        })

    # 4. Bulldozer (E High + A Low)
    if e >= 70 and a <= 40:
        combos.append({
            "title": "🚜 불도저 리더",
            "desc": "'나를 따르라!' 카리스마가 넘칩니다. 목표를 위해서라면 거침없이 직진하는 스타일. 팩트로 뼈 때리는 건 덤."
        })

    # 5. Anxious Perfectionist (N High + C High)
    if n >= 70 and c >= 70:
        combos.append({
            "title": "⚡ 불안한 완벽주의자",
            "desc": "99점은 용납 못 하죠. 100점을 위해 밤새 수정하고 또 수정합니다. 결과물은 완벽하겠지만, 당신의 수면 시간은 안녕하신가요?"
        })

    # 6. Empath (N High + A High)
    if n >= 70 and a >= 70:
        combos.append({
            "title": "💧 감성 스폰지",
            "desc": "타인의 슬픔이 곧 나의 슬픔. 영화 보다 오열하고, 친구 고민에 같이 밤새워주는 진정한 공감 능력자."
        })

    # 7. Zen Master (N Low + C Low)
    if n <= 40 and c <= 40:
        combos.append({
            "title": "🧘 태평천하 (Zen Master)",
            "desc": "세상이 무너져도 '아, 그래요?' 하고 다시 잘 수 있는 분. 스트레스가 비켜가는 무의 경지에 도달하셨군요."
        })
        
    # 8. Lone Wolf (E Low + C High)
    if e <= 40 and c >= 70:
        combos.append({
             "title": "🐺 고독한 전략가 (Lone Wolf)",
             "desc": "혼자 있을 때 업무 효율이 200% 증가합니다. 팀플보다는 독고다이가 편하고 결과도 확실한 '고효율 솔로 플레이어'!"
        })

    if not combos:
        return ""
    
    # Generate HTML for combos
    html_parts = []
    html_parts.append('<section class="glass-panel rounded-2xl p-8 border-2 border-indigo-100 relative overflow-hidden">')
    html_parts.append('<div class="absolute top-0 right-0 p-4 opacity-5 text-8xl">🌟</div>')
    html_parts.append('<h2 class="text-xl font-bold text-indigo-900 mb-6 flex items-center">✨ Special Analysis <span class="ml-2 text-xs font-normal text-indigo-500 bg-indigo-50 px-2 py-1 rounded-full">히든 업적 달성!</span></h2>')
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

    return "\n".join(html_parts)

def get_score_text(score):
    """0-100 score to text badge."""
    if score is None: return "N/A", ""
    for limit, label, css in SCORE_MAP:
        if score <= limit:
            return label, css
    return "매우 높음", "bg-red-100 text-red-800"

def get_confidence_text(conf):
    """0.0-1.0 confidence to text."""
    if conf is None: return "알 수 없음", ""
    for limit, label, css in CONFIDENCE_MAP:
        if conf <= limit:
            return label, css
    return "확실", "text-blue-700 font-bold"

# -------------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EchoMind Profile Report</title>
    <!-- Tailwind CSS (via CDN for standalone simplicity) -->
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

    <div class="max-w-4xl mx-auto space-y-8">
        
        <!-- Header -->
        <header class="text-center py-10">
            <h1 class="text-4xl font-extrabold text-slate-900 tracking-tight mb-2">EchoMind Insight</h1>
            <div class="text-slate-500 text-sm">
                분석 대상: <span class="font-medium text-slate-900">{speaker_name}</span> | 
                생성일: {date_str}
            </div>
        </header>

        <!-- Executive Summary -->
        <section class="glass-panel rounded-2xl p-8">
            <h2 class="text-xl font-bold text-slate-900 mb-4 border-b pb-2 border-slate-100">💡 핵심 요약</h2>
            <p class="text-lg leading-relaxed text-slate-700">
                {summary_text}
            </p>
            <div class="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                {comm_bullets}
            </div>
        </section>

        <!-- Main Personality Types -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- MBTI -->
            <section class="glass-panel rounded-2xl p-6 relative overflow-hidden group hover:shadow-lg transition-all duration-300">
                <div class="absolute top-0 right-0 p-4 opacity-10 text-6xl font-black text-indigo-900 select-none group-hover:scale-110 transition-transform">MBTI</div>
                <h3 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-1">성격 유형 추정</h3>
                <div class="flex flex-col mb-4">
                    <span class="text-4xl font-bold text-indigo-600">{mbti_type}</span>
                    <span class="text-sm text-indigo-800 bg-indigo-50 px-2 py-1 rounded mt-1 inline-block self-start font-medium">{mbti_desc_str}</span>
                </div>
                 <div class="text-xs {mbti_conf_css} mb-2">신뢰도: {mbti_conf_text}</div>
                <ul class="space-y-2">
                    {mbti_reasons}
                </ul>
            </section>

            <!-- Socionics -->
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

        <!-- Big 5 Traits -->
        <section class="glass-panel rounded-2xl p-8">
            <h2 class="text-xl font-bold text-slate-900 mb-6 border-b pb-2 border-slate-100">🌊 성격 5요인 (Big 5) 상세 분석</h2>
            <div class="space-y-6">
                {big5_rows}
            </div>
             <div class="mt-4 text-right text-xs text-slate-400">
                * 신뢰수준: <span class="{big5_conf_css}">{big5_conf_text}</span>
            </div>
        </section>

        <!-- Special Analysis (Combo) -->
        {special_analysis_section}

        <!-- Caveats -->
        <section class="rounded-xl border border-slate-200 bg-slate-50 p-6 text-slate-500 text-sm">
            <h3 class="font-semibold text-slate-700 mb-2">⚠️ 분석의 한계 및 주의사항</h3>
            <ul class="list-disc pl-5 space-y-1">
                {caveats}
            </ul>
        </section>

    </div>
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
# Core Logic (Server Integratable)
# -------------------------------------------------------------------------

def generate_report_html(data: dict) -> str:
    """
    JSON 데이터(Dict)를 입력받아 렌더링된 HTML 문자열을 반환합니다.
    서버 환경에서는 이 함수를 import하여 사용하면 됩니다.
    """
    meta = data.get("meta", {})
    profile = data.get("llm_profile", {})
    
    # 1. Header
    speaker_name = html.escape(meta.get("speaker_name", "Unknown"))
    gen_time = meta.get("generated_at_utc", "")
    try:
        date_obj = datetime.fromisoformat(gen_time.replace("Z", "+00:00"))
        date_str = date_obj.strftime("%Y년 %m월 %d일")
    except:
        date_str = gen_time

    # 2. Summary
    summary = profile.get("summary", {})
    summary_text = html.escape(summary.get("one_paragraph", ""))
    comm_list = summary.get("communication_style_bullets", [])
    comm_bullets = "\n".join([f'<div class="flex items-start"><span class="text-indigo-500 mr-2">▪</span><span>{html.escape(c)}</span></div>' for c in comm_list])

    # 3. MBTI
    mbti = profile.get("mbti", {})
    mbti_type = html.escape(mbti.get("type", "Unknown"))
    
    # MBTI Description Map
    mbti_desc_str = MBTI_DESC_MAP.get(mbti_type.upper(), "")

    mConf, mCss = get_confidence_text(mbti.get("confidence"))
    mbti_reasons = "\n".join([f'<li class="text-sm text-slate-600 list-disc list-inside">{html.escape(r)}</li>' for r in mbti.get("reasons", [])])

    # 4. Socionics
    soc = profile.get("socionics", {})
    soc_type = html.escape(soc.get("type", "Unknown"))
    
    # Socionics Description Logic
    # If type is like "LII (Analyst)", we try to extract "LII"
    # Basic cleanup: take first word if it looks like 3 uppercase chars?
    # Or just use key lookup
    soc_key = soc_type.split()[0].upper() if soc_type else ""
    # Remove non-alpha
    import re
    soc_key = re.sub(r'[^A-Z]', '', soc_key)
    
    soc_desc_str = SOCIONICS_DESC_MAP.get(soc_key, "정보가 부족한 유형입니다.")
    
    sConf, sCss = get_confidence_text(soc.get("confidence"))
    soc_reasons = "\n".join([f'<li class="text-sm text-slate-600 list-disc list-inside">{html.escape(r)}</li>' for r in soc.get("reasons", [])])

    # Generate Socionics All Types List (Sorted)
    socionics_all_types_html = ""
    sorted_soc_keys = sorted(SOCIONICS_DESC_MAP.keys())
    for k in sorted_soc_keys:
         desc = SOCIONICS_DESC_MAP[k]
         # Highlight current user type
         bg_class = "bg-rose-100 font-bold text-rose-800" if k == soc_key else ""
         socionics_all_types_html += f'<div class="p-1 {bg_class}"><span class="font-bold">{k}</span>: {desc}</div>'

    # Add General Socionics Info (Collapsible)
    soc_reasons += f"""
    <div class="mt-4 pt-4 border-t border-slate-100">
        <details class="group">
            <summary class="list-none cursor-pointer text-xs font-semibold text-rose-500 hover:text-rose-700 flex items-center transition-colors select-none">
                <span class="mr-1">❓ 소시오닉스가 뭔가요?</span>
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
        "openness": ["개방성", "openness"],
        "conscientiousness": ["성실성", "conscientiousness"],
        "extraversion": ["외향성", "extraversion"],
        "agreeableness": ["우호성", "agreeableness"],
        "neuroticism": ["신경성", "neuroticism"]
    }
    
    display_names = {
        "openness": "개방성 (Openness)",
        "conscientiousness": "성실성 (Conscientiousness)",
        "extraversion": "외향성 (Extraversion)",
        "agreeableness": "우호성 (Agreeableness)",
        "neuroticism": "신경성 (Neuroticism)"
    }
    
    # Normalize reasons map
    reason_map = {}
    for r in reasons:
        # LLM output might be "Openness: Blah" or "개방성: 블라블라" or just "블라블라 (Openness)"
        # We try to detect the key.
        lower_r = r.lower()
        matched_key = None
        cleaned_val = r

        # Try splitting by colon first
        parts = r.split(":", 1)
        if len(parts) == 2:
            key_part = parts[0].strip().lower()
            val_part = parts[1].strip()
            
            # Check if key_part matches any trait keywords
            for t_key, keywords in trait_keys.items():
                if any(k in key_part for k in keywords):
                    matched_key = t_key
                    cleaned_val = val_part
                    break
        
        # If not matched by colon, try searching in the whole string
        if not matched_key:
            for t_key, keywords in trait_keys.items():
                if any(k in lower_r for k in keywords):
                    matched_key = t_key
                    # We keep the whole string as reason if we just found it via keyword search
                    break
        
        if matched_key:
            reason_map[matched_key] = cleaned_val

    big5_rows_html = []
    for key, display_name in display_names.items():
        score = scores.get(key)
        
        # New Integrated Logic:
        label, description, witty_comment, badge_css = get_trait_content(key, score)
        
        # Reason mapping from LLM (optional extra)
        raw_reason = reason_map.get(key, "")
        
        # Construct the HTML description block
        # 1. Informative Description (Bold or Primary)
        desc_html = f"<div class='font-medium text-slate-800 mb-2'>{description}</div>"
        
        # 2. Witty Comment (Boxed or styled)
        desc_html += f"<div class='text-sm text-indigo-600 bg-indigo-50/30 px-3 py-2 rounded-lg border border-indigo-50 mb-2'>💬 \"{witty_comment}\"</div>"

        # 3. AI Note (Collapsible Details)
        if raw_reason:
            desc_html += f"""
            <details class="group">
                <summary class="list-none cursor-pointer text-xs text-slate-400 hover:text-slate-600 flex items-center transition-colors select-none">
                    <span class="mr-1">🤖 AI 분석 노트 보기</span>
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

    # Special Analysis
    special_analysis_html = get_combo_comment(scores)

    # 6. Caveats
    caveats = profile.get("caveats", [])
    caveats_html = "\n".join([f'<li>{html.escape(c)}</li>' for c in caveats])

    # Render
    return HTML_TEMPLATE.format(
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

# -------------------------------------------------------------------------
# CLI Helper
# -------------------------------------------------------------------------

import argparse

def main():
    parser = argparse.ArgumentParser(description="Generate HTML profile report from JSON")
    parser.add_argument("input_file", nargs="?", default="profile.json", help="Input JSON file path (default: profile.json)")
    parser.add_argument("--out", "-o", help="Output HTML file path (default: [input_filename].html)")

    args = parser.parse_args()

    json_path = args.input_file
    
    # Determine output path
    if args.out:
        html_path = args.out
    else:
        # e.g., data/my_profile.json -> data/my_profile.html
        base, _ = os.path.splitext(json_path)
        html_path = base + ".html"
        # If input was just "profile.json" -> "profile.html"
        # Since previous default was "profile_report.html", 
        # let's only stick to that if input is exactly "profile.json" for backward compat preference,
        # OR just use the cleaner Rule: name.json -> name.html.
        # User asked for "options to change target file", so dynamic naming is better.
        # However, to be nice, if input is profile.json, let's keep profile_report.html or just profile.html?
        # profile.html is cleaner. But let's stick to the previous file name if input is default
        if json_path == "profile.json" and not args.out:
            html_path = "profile_report.html"

    if not os.path.exists(json_path):
        print(f"Error: '{json_path}' not found.")
        sys.exit(1)

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        sys.exit(1)

    # 서버에서는 이 함수만 import해서 쓰면 됨
    try:
        html_content = generate_report_html(data)
    except Exception as e:
        print(f"Error generating HTML: {e}")
        sys.exit(1)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Successfully generated {html_path} from {json_path}")

if __name__ == "__main__":
    main()
