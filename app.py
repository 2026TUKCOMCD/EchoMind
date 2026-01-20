import os
import sys
import re
import json
import time
import statistics
import pymysql
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from dotenv import load_dotenv
from kiwipiepy import Kiwi
from soynlp.normalizer import repeat_normalize
# -----------------------
# [0] 환경 설정 및 초기화
# -----------------------
load_dotenv()
app = Flask(__name__)
app.secret_key = 'echomind_secret_key_secure_random_string'

# Kiwi 형태소 분석기 초기화
kiwi = Kiwi()

# -----------------------
# [DB 설정]
# -----------------------
print("\n" + "="*40)
print("   EchoMind DB 접속 설정")
print("="*40)

db_config = {
    'host': 'echomind-db.cbqkoi8kaesl.ap-northeast-2.rds.amazonaws.com',
    'user': 'admin',        # 사용자님이 설정한 ID
    'password': 'mypassword1234',    # 사용자님이 설정한 비번
    'db': 'echomind',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# -----------------------
# [1] KNU 감성 사전 로딩 (로컬 파일)
# -----------------------
print(">>> KNU 감성 사전을 로딩 중입니다...")
SENTIMENT_DB = {}
try:
    with open('SentiWord_info.json', encoding='utf-8-sig') as f:
        senti_data = json.load(f)
    
    for entry in senti_data:
        root_word = entry['word_root']
        score = int(entry['polarity']) # -2 ~ 2
        SENTIMENT_DB[root_word] = score
        SENTIMENT_DB[entry['word']] = score 

    print(f">>> 사전 로딩 완료! (단어 수: {len(SENTIMENT_DB)}개)")
except Exception as e:
    print(f">>> [경고] 'SentiWord_info.json' 파일이 없습니다! 감성 분석이 정확하지 않을 수 있습니다.")
    print(f">>> 에러 내용: {e}")

# -----------------------
# [2] 분석 로직 모음
# -----------------------
# -----------------------
# [2] 분석 로직 모음 (MBTI Linguistic Features)
# -----------------------
LINE_RE = re.compile(r"^\[(?P<name>.+?)\] \[(?P<time>.+?)\] (?P<msg>.*)")
ANDROID_RE = re.compile(r"^(?P<time>\d{4}년 \d{1,2}월 \d{1,2}일 (오전|오후) \d{1,2}:\d{2}), (?P<name>.+?) : (?P<msg>.*)")
# -----------------------
# [1.1] 욕설/독성 사전 로딩 (korean_bad_words.json)
# -----------------------
print(">>> 독성(욕설) 사전을 로딩 중입니다...")
BAD_WORDS = set()
try:
    with open('korean_bad_words.json', encoding='utf-8') as f:
        bad_data = json.load(f)
        # bad_data가 리스트인지, 딕셔너리인지 확인 필요 (보통 리스트 ['시발', ...])
        # 만약 {"bad_words": [...]} 형태면 keys 확인
        if isinstance(bad_data, list):
            # Check if elements are dicts or strings
            if bad_data and isinstance(bad_data[0], dict):
                # Structure: [{"text": "word", ...}, ...]
                BAD_WORDS = {item.get('text') for item in bad_data if item.get('text')}
            else:
                # Structure: ["word", ...]
                BAD_WORDS = set(bad_data)
        elif isinstance(bad_data, dict) and "bad_words" in bad_data:
            BAD_WORDS = set(bad_data["bad_words"])
        else:
            # 딕셔너리 키 자체가 단어일 수도 있음
            BAD_WORDS = set(bad_data.keys())
            
    # 핵심 욕설은 강제 추가 (누락 방지)
    BAD_WORDS.update(["시발", "씨발", "병신", "개새끼", "존나", "미친", "죽어", "꺼져", "년", "놈"])
    print(f">>> 독성 사전 로딩 완료! (단어 수: {len(BAD_WORDS)}개)")
except Exception as e:
    print(f">>> [경고] 'korean_bad_words.json' 파일이 없습니다! 기본 욕설 목록만 사용합니다.")
    BAD_WORDS = {"시발", "씨발", "병신", "개새끼", "존나", "미친", "죽어", "꺼져", "년", "놈"}


# =============================================================================
# [사용자 설정] MBTI 가중치 조절
# ... (기존 설정 유지) ...
WEIGHT_E = 1.0; WEIGHT_I = 1.2
WEIGHT_S = 1.0; WEIGHT_N = 1.0
WEIGHT_T = 1.0; WEIGHT_F = 1.0
WEIGHT_J = 1.0; WEIGHT_P = 1.2
# =============================================================================

# ... (기존 키워드 유지) ...
E_ENDINGS = {'어', '자', '까', '해', '봐', '지', '니', '냐'}
I_ENDINGS = {'다', '음', '임', '셈', '함', '듯', '네'}
# ...

# [추가] SKIP_TOKENS 정의 (누락 수정)
SKIP_TOKENS = {'사진', '동영상', '이모티콘', '보이스톡 해요.', '페이스톡 해요.', '파일'}

# -----------------------------------------------------------------------------
# [추가] Big5 고도화를 위한 한국어 스타일 분석 (API 로직 이식)
# -----------------------------------------------------------------------------
def analyze_korean_style_features(sentences):
    """
    Big5 산출을 위한 정밀 언어 스타일 분석
    - TTR (어휘 다양성 -> 개방성)
    - Self-Ref (자기 지칭 -> 외향성)
    - Laughs (리액션 -> 외향성/친화성)
    - Certainty (확신어 -> 성실성/J)
    """
    full_text = " ".join(sentences[:5000])
    tokens = kiwi.tokenize(full_text)
    total_words = len(tokens)
    if total_words == 0: total_words = 1
    
    unique_morphs = set()
    self_ref_count = 0
    certainty_count = 0
    uncertainty_count = 0
    laugh_count = 0 
    
    # 자기지시어 (나, 저, 우리...)
    self_pronouns = {"나", "저", "우리", "내", "제"}
    # 확신어
    certainty_words = {"진짜", "정말", "너무", "완전", "확실히", "분명", "반드시", "물론", "절대", "당연"}
    # 불확신어
    uncertainty_words = {"아마", "글쎄", "약간", "좀", "어쩌면", "모르", "듯"}
    
    for t in tokens:
        m, tag = t.form, t.tag
        unique_morphs.add(m)
        
        # 1. 자기지칭 (NP: 대명사, MM: 관형사)
        if m in self_pronouns and (tag.startswith('N') or tag == 'MM'):
            self_ref_count += 1
            
        # 2. 리액션 (ㅋ, ㅎ, ㅠ) - 웃음소리
        if any(c in m for c in ['ㅋ', 'ㅎ', 'ㅠ', 'ㅜ']):
            laugh_count += 1
            
        # 3. 확신/불확신
        if m in certainty_words: certainty_count += 1
        if m in uncertainty_words: uncertainty_count += 1
            
    # Normalize (빈도 비율)
    style = {
        "avg_len": sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0, # 어절 기준 평균 길이
        "ttr": len(unique_morphs) / total_words,               # 어휘 다양성
        "self_ref": self_ref_count / total_words,              # 자기 중심성
        "laughs": laugh_count / total_words,                   # 리액션 비율
        "certainty": certainty_count / total_words,            # 확신 비율
        "uncertainty": uncertainty_count / total_words         # 불확신 비율
    }
    return style

def calculate_advanced_big5(style, tox_ratio, pos_ratio, neg_ratio):
    """
    스타일(Style) + 감성(Sentiment) + 독성(Toxicity) -> Big5 점수 산출
    [v3] 정규화 가중합 방식 - 0~100 전 범위 사용 가능
    """
    
    def normalize(val, scale=1.0, offset=0.0):
        """값을 0~1 범위로 정규화 (스케일 증폭 + 오프셋 지원)"""
        val = (val * scale) + offset
        return min(1.0, max(0.0, val))

    # ==========================================================================
    # 1. 개방성 (Openness) - 어휘 다양성 + 문장 길이(단답형 X)
    # TTR이 높고, 문장이 너무 짧지 않으면 개방적
    # ==========================================================================
    openness = (0.6 * normalize(style['ttr'], 2.5)) + \
               (0.2 * normalize(style['avg_len'] / 15)) + \
               (0.2 * normalize(pos_ratio, 1.2))

    # ==========================================================================
    # 2. 성실성 (Conscientiousness) - 확신어 + 리액션 절제 + 예의(독성↓)
    # 확신어 많고, ㅋㅋㅋ 적당하고, 욕설 없으면 성실
    # ==========================================================================
    conscientiousness = (0.4 * normalize(style['certainty'], 15.0)) + \
                        (0.3 * (1 - normalize(style['laughs'], 5.0))) + \
                        (0.3 * (1 - tox_ratio))

    # ==========================================================================
    # 3. 외향성 (Extraversion) - 리액션 + 긍정 + 자기표현
    # ㅋㅋㅋ 많고, 긍정적이고, 자기 이야기 많이 하면 외향
    # ==========================================================================
    extraversion = (0.4 * normalize(style['laughs'], 10.0)) + \
                   (0.3 * normalize(pos_ratio, 1.5)) + \
                   (0.3 * normalize(style['self_ref'], 20.0))

    # ==========================================================================
    # 4. 친화성 (Agreeableness) - 독성↓ + 리액션 + 긍정
    # 욕설 없고, 리액션 좋고, 긍정적이면 친화적
    # ==========================================================================
    neutral_ratio = 1 - pos_ratio - neg_ratio  # 중립 비율 추정
    agreeableness = (0.35 * (1 - tox_ratio)) + \
                    (0.25 * normalize(style['laughs'], 8.0)) + \
                    (0.2 * normalize(pos_ratio, 1.2)) + \
                    (0.2 * max(0, neutral_ratio))

    # ==========================================================================
    # 5. 신경성 (Neuroticism) - 부정 + 불확신 + 독성
    # 부정적이고, 불확실하고, 공격적이면 신경증 높음
    # ** 모두 0이면 0점, 모두 높으면 100점 **
    # ==========================================================================
    neuroticism = (0.5 * neg_ratio) + \
                  (0.3 * normalize(style['uncertainty'], 8.0)) + \
                  (0.2 * tox_ratio)

    # ==========================================================================
    # 최종: 0~1 값을 0~100으로 변환 (반올림)
    # ==========================================================================
    return {
        "openness": round(openness * 100, 1),
        "conscientiousness": round(conscientiousness * 100, 1),
        "extraversion": round(extraversion * 100, 1),
        "agreeableness": round(agreeableness * 100, 1),
        "neuroticism": round(neuroticism * 100, 1),
    }

# 2. S vs N
# [수정] S 키워드에서 너무 흔한 시점 단어 제거 ('오늘', '어제', '내일', '지금' 등은 누구나 씀)
S_KEYWORDS = {'현실', '사실', '팩트', '데이터', '검증', '증명', '확인', '경험', '관찰', '실제', '구체', '디테일', '세부', '오감', '체험', '실용', '도구', '재료', '수치', '통계', '증거', '기록', '지금', '오늘', '여기'} # [수정] 복구된 표현 키워드
N_KEYWORDS = {'상상', '만약', '혹시', '가능성', '미래', '의미', '비전', '아이디어', '직관', '영감', '철학', '우주', '가치관', '컨셉', '비유', '은유', '상징', '추상', '망상', '꿈', '이상', '원리', '패턴', '아마'} # [수정] 복구된 표현 키워드

# 3. T vs F
T_KEYWORDS = {'분석', '논리', '원인', '결과', '이유', '근거', '효율', '비판', '평가', '판단', '객관', '원칙', '정의', '검토', '해결', '방법', '시스템', '기능', '성능', '설명', '이해', '인과', '왜', '때문에', '그러므로', '즉'} # [수정] 복구된 표현 키워드
F_KEYWORDS = {'공감', '감동', '서운', '행복', '감사', '미안', '고마워', '소중', '배려', '응원', '위로', '좋아', '싫어', '마음', '기분', '느낌', '센스', '조화', '관계', '사람', '사랑', '우정', '감정', '화이팅', '진짜', '너무', '완전', '대박', '헐', 'ㅠㅠ', 'ㅜㅜ'} # [수정] 복구된 표현 키워드

# 4. J vs P
J_KEYWORDS = {'계획', '일정', '준비', '정리', '체계', '순서', '단계', '목표', '마감', '기한', '완료', '달성', '약속', '규칙', '통제', '미리', '예약', '스케줄', '리스트', '절차', '확정'} # [수정] 복구된 표현 키워드
P_KEYWORDS = {'상황', '변동', '유동', '그때', '봐서', '즉흥', '자유', '재미', '과정', '탐색', '경험', '오픈', '가능', '융통', '적응', '변화', '어떻게든', '놀자', '여유', '몰라', '아무거나', '그냥', '일단'} # [수정] 복구된 표현 키워드

def parse_kakao_txt(path: str):
    rows = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\n")
                m = LINE_RE.match(line)
                if m:
                    rows.append({
                        "speaker": m.group("name").strip(),
                        "time": m.group("time"),
                        "text": m.group("msg").strip(),
                    })
                    continue

                m2 = ANDROID_RE.match(line)
                if m2:
                    rows.append({
                        "speaker": m2.group("name").strip(),
                        "time": m2.group("time"),
                        "text": m2.group("msg").strip(),
                    })
                    continue
    except Exception as e:
        print(f"File parsing error: {e}")
    return rows

def clean_text(t: str) -> str:
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"이모티콘|사진|동영상", "", t) 
    t = re.sub(r"[^가-힣a-zA-Z0-9\s\.\?!]", " ", t) # 특수문자 일부 허용
    t = re.sub(r"\s+", " ", t).strip()
    return t

# [시간 파싱 헬퍼 - 개선된 버전]
def parse_time_diff(t1_str, t2_str):
    """
    다양한 포맷의 시간 문자열 차이를 분 단위로 계산
    지원 포맷: "오전 10:23", "오후 2:05", "AM 10:23", "PM 2:05", "14:30"
    """
    def time_to_min(ts):
        ts = ts.strip()
        try:
            # 1. "오전/오후 HH:MM" 또는 "AM/PM HH:MM" 처리
            is_pm = '오후' in ts or 'PM' in ts or 'pm' in ts
            is_am = '오전' in ts or 'AM' in ts or 'am' in ts
            
            # 숫자와 콜론만 남기고 제거
            # 숫자와 콜론만 남기고 제거 (날짜 제외하고 시간만 추출하기 위해 수정)
            # Ex: "2024년 5월 20일 오후 3:15" -> "3:15" 추출
            time_match = re.search(r"(\d{1,2}):(\d{2})", ts)
            if not time_match: return -1
            hh, mm = int(time_match.group(1)), int(time_match.group(2))
            
            if is_pm and hh != 12: hh += 12
            elif is_am and hh == 12: hh = 0
            
            return hh * 60 + mm
        except:
            return -1

    m1 = time_to_min(t1_str)
    m2 = time_to_min(t2_str)
    
    if m1 == -1 or m2 == -1: return 0 # 파싱 실패시 0 처리
    
    diff = m2 - m1
    # 자정을 넘긴 경우 (예: 23:50 -> 00:10 = -1420분 -> +20분?)
    # 단순하게 하루 24시간을 더해봄 (단, 12시간 이상 차이나면 날짜 변경으로 간주)
    if diff < -720: diff += 1440 
    
    return max(0, diff) # 음수는 0 처리

# -----------------------------------------------------------------------------
# [핵심] MBTI Feature Extraction
# -----------------------------------------------------------------------------
def analyze_mbti_features(rows, target_name):
    # 1. Init Features
    feats = {
        'total_msgs': 0,
        'avg_reply_time': 0.0,
        'initiation_count': 0,
        'turn_length_avg': 0.0,
        'e_score': 0.0, 'i_score': 0.0,
        's_score': 0.0, 'n_score': 0.0,
        't_score': 0.0, 'f_score': 0.0,
        'j_score': 0.0, 'p_score': 0.0
    }
    
    target_sentences = []
    
    # 2. Interaction Analysis (Reply Speed, Initiation)
    reply_times = []
    consecutive_counts = []
    curr_consecutive = 0
    last_speaker = None
    last_time = None
    
    for r in rows:
        speaker = r['speaker']
        msg_time = r['time']
        text = r['text']
        
        # --- Target Logic
        if speaker == target_name:
            if text in SKIP_TOKENS: continue
            
            cleaned = clean_text(text)
            if cleaned: target_sentences.append(cleaned)
            
            feats['total_msgs'] += 1
            curr_consecutive += 1
            
            # 답장 속도 (이전 화자가 다른 사람이었을 때)
            if last_speaker and last_speaker != target_name and last_time:
                diff = parse_time_diff(last_time, msg_time)
                # 6시간(360분) 이상 지났으면 '선톡'으로 간주, 답장 시간 제외
                if diff > 360:
                    feats['initiation_count'] += 1
                else:
                    reply_times.append(diff)
                    
        else:
            # 타겟이 말을 끝내고 턴이 넘어감
            if last_speaker == target_name:
                consecutive_counts.append(curr_consecutive)
                curr_consecutive = 0
                
        last_speaker = speaker
        last_time = msg_time

    # 3. Aggregation interaction
    if reply_times:
        feats['avg_reply_time'] = sum(reply_times) / len(reply_times)
    else:
        feats['avg_reply_time'] = 10.0 # Default
        
    if consecutive_counts:
        feats['turn_length_avg'] = sum(consecutive_counts) / len(consecutive_counts)
    else:
        feats['turn_length_avg'] = 1.0

    return feats, target_sentences

def analyze_linguistic_features(sentences, feats):
    # Kiwi Setup
    full_text = " ".join(sentences[:5000]) # Sample limit
    tokens = kiwi.tokenize(full_text)
    
    total_words = len(tokens)
    if total_words == 0: total_words = 1
    
    # Check simple keyword mapping first
    # Using raw morphemes for keyword matching
    morphs = [t.form for t in tokens]
    pos_tags = [t.tag for t in tokens] # Not heavily used yet, but good for filtering
    
    # --- Scoring Logic ---
    # [E vs I]
    # E: 질문/권유 어미, 짧은 턴, 선톡 많음
    # I: 서술형 어미, 긴 턴, 답장 느림(Interaction에서 처리)
    
    # Ending Analysis
    for t in tokens:
        m, tag = t.form, t.tag
        
        # S vs N
        # [수정] S 가중치 너프, N 가중치 버프
        if m in S_KEYWORDS: 
            feats['s_score'] += 1.0 # (기존 1.5)
        elif tag == 'SN': # 숫자
            feats['s_score'] += 0.5 # (기존 1.5 - 숫자는 너무 많이 나옴)

        if m in N_KEYWORDS:
            feats['n_score'] += 2.0 # (기존 1.5)
        # 가정/추상 표현: '듯', '것', '수' (의존명사 NNB) -> N 성향 약간
        if tag == 'NNB': 
            feats['n_score'] += 0.5

        # T vs F
        # 부사(MAG, MAJ) 접속사(MAJ) 감탄사(IC)
        if m in T_KEYWORDS:
            feats['t_score'] += 2.0
        if m in F_KEYWORDS:
            feats['f_score'] += 2.0
            
        # J vs P
        if m in J_KEYWORDS:
            feats['j_score'] += 2.0
        if m in P_KEYWORDS:
            feats['p_score'] += 2.0

        # E vs I (Endings)
        # 종결어미(EF)
        if tag.startswith('E'):
            if any(e in m for e in E_ENDINGS): feats['e_score'] += 1.0
            if any(e in m for e in I_ENDINGS): feats['i_score'] += 1.0
            
    # Normalize by text length (per 100 words)
    scale = 100 / total_words
    feats['s_score'] *= scale
    feats['n_score'] *= scale
    feats['t_score'] *= scale
    feats['f_score'] *= scale
    feats['j_score'] *= scale
    feats['p_score'] *= scale
    feats['e_score'] *= scale
    feats['i_score'] *= scale

    # [수정] 키워드 점수 비중 축소 (행동 점수 강조를 위해 0.2배 적용)
    # [수정] E/I는 행동 점수가 크므로 키워드 비중을 낮춤 (0.2배)
    for k in ['e_score', 'i_score']:
        feats[k] *= 0.2

    # [수정] 나머지는 행동 점수가 없으므로, 키워드 점수를 대폭 상향 (5.0배)
    # 정제된 희귀 키워드이므로 발견 시 높은 점수 부여 필요
    for k in ['s_score', 'n_score', 't_score', 'f_score', 'j_score', 'p_score']:
        # [수정] 흔한 단어 복구로 빈도가 늘었으므로 가중치 소폭 하향 (5.0 -> 3.0)
        feats[k] *= 3.0
    
    return feats

def calculate_final_mbti(feats):
    # Rule-Set Weights
    
    # 1. Extraversion (E) vs Introversion (I)
    # E factors: Fast Reply (< 2 min), Initiation, Turn Length(Short & Frequent), Endings
    # I factors: Slow Reply (> 5 min), Long Turn, Endings
    
    # [수정] 답장 속도 기준 완화 및 I 점수 강화
    # 한국인 특성상 '빨리빨리'가 많아 E가 과대평가됨. 기준을 더 엄격하게.
    # [수정] 답장 속도 (비례 점수제): 3분 이내면 점수 부여 (빠를수록 고득점, 최대 1.0점/기본 가중치 1.0)
    # 0분(즉시) -> 1.0점, 1.5분 -> 0.5점, 3분 -> 0점
    reply_score = max(0, (3.0 - feats['avg_reply_time']) / 3.0)
    # [수정] E 과대평가 방지: 답장 속도 가중치 1.0 -> 0.5로 축소
    feats['e_score'] += min(0.5, reply_score * 0.5)
    feats['e_score'] += min(1.0, reply_score)
    
    # 느린 답장(I 성향)은 기존 유지 (5분 이상이면 I +3.0)
    # [수정] 느린 답장 기준 완화: 3분만 넘어도 I 점수 부여
    if feats['avg_reply_time'] > 3.0: feats['i_score'] += 3.0
    
    # [수정] 턴 길이 (비례 점수제): 2.5어절 미만이면 점수 부여 (짧을수록 고득점, 최대 1.0점)
    turn_score = max(0, (2.5 - feats['turn_length_avg']) * 0.6)
    feats['e_score'] += min(1.0, turn_score)
    
    # 긴 턴(I 성향)은 기존 유지
    if feats['turn_length_avg'] >= 2.0: feats['i_score'] += 2.0
    
    # [수정] Initiation (비례 점수제): 횟수당 0.8점 (최대 4.0점)
    # 1회: 0.8점, 3회: 2.4점, 5회+: 4.0점
    # [수정] 선톡 3회부터 인정 (1~2회는 무시)
    # [수정] 선톡 점수 완화: 0.5점씩 천천히 증가 (최대 3.0점)
    # [수정] 선톡이 가장 중요함: 가중치 대폭 상향 (최대 15.0점)
    # 1~2회 무시, 3회부터 회당 1.5점씩 팍팍 부여
    init_score = max(0, (feats['initiation_count'] - 2) * 1.5)
    feats['e_score'] += min(15.0, init_score)
    # [수정] I 보너스: 선톡이 적으면(2회 이하) 내향형 점수 부여 (+5.0)
    if feats['initiation_count'] <= 2: feats['i_score'] += 5.0
    # E/I Decision
    e_total = feats['e_score'] * WEIGHT_E
    i_total = feats['i_score'] * WEIGHT_I
    
    # [수정] 사용자가 설정한 가중치 적용
    e_final = 'E' if e_total > i_total else 'I'
    
    # 2. Sensing (S) vs Intuition (N)
    # [수정] 사용자가 설정한 가중치 적용
    s_score_final = feats['s_score'] * WEIGHT_S
    n_score_final = feats['n_score'] * WEIGHT_N
    s_final = 'S' if s_score_final > n_score_final else 'N'
    
    # 3. Thinking (T) vs Feeling (F)
    t_score_final = feats['t_score'] * WEIGHT_T
    f_score_final = feats['f_score'] * WEIGHT_F
    f_final = 'F' if f_score_final > t_score_final else 'T'
    
    # 4. Judging (J) vs Perceiving (P)
    j_score_final = feats['j_score'] * WEIGHT_J
    p_score_final = feats['p_score'] * WEIGHT_P
    j_final = 'J' if j_score_final > p_score_final else 'P'
    
    mbti = f"{e_final}{s_final}{f_final}{j_final}"
    
    # Reasoning Generation
    reasons = []
    
    # E/I Reason
    if e_final == 'E': reasons.append(f"평균 답장 속도가 {feats['avg_reply_time']:.1f}분으로 빠르고, 대화를 자주 주도하여 **외향형(E)** 특성을 보입니다.")
    else: reasons.append(f"평균 답장 시간이 {feats['avg_reply_time']:.1f}분으로 신중하며, 한번에 긴 내용을 담아 **내향형(I)** 성향이 나타납니다.")
    
    # S/N Reason
    if s_final == 'S': reasons.append(f"구체적인 숫자와 현실적인 단어의 비중({feats['s_score']:.1f})이 추상적 표현보다 높아 **감각형(S)**입니다.")
    else: reasons.append(f"가정법이나 추상적인 어휘의 비중({feats['n_score']:.1f})이 높아 상상력이 풍부한 **직관형(N)**입니다.")
    
    # T/F Reason
    if f_final == 'F': reasons.append(f"공감과 리액션 단어의 빈도({feats['f_score']:.1f})가 논리적 표현보다 월등히 높아 **감정형(F)**입니다.")
    else: reasons.append(f"원인과 결과를 따지는 논리적 단어({feats['t_score']:.1f})를 자주 사용하여 **사고형(T)**입니다.")
    
    # J/P Reason
    if j_final == 'J': reasons.append(f"계획 및 일정을 언급하는 빈도({feats['j_score']:.1f})가 높아 계획적인 **판단형(J)**입니다.")
    else: reasons.append(f"상황에 따른 변동성이나 유연한 표현({feats['p_score']:.1f})이 많아 즉흥적인 **인식형(P)**입니다.")

    # [추가] 상세 수치 표기
    reasons.append(f"""
    <div style='background:#f8f9fa; padding:10px; border-radius:5px; margin-top:10px; font-size:0.9em;'>
        <strong>📊 상세 지표 점수 (가중치 적용됨)</strong><br>
        E({e_total:.1f}) vs I({i_total:.1f})<br>
        S({s_score_final:.1f}) vs N({n_score_final:.1f})<br>
        T({t_score_final:.1f}) vs F({f_score_final:.1f})<br>
        J({j_score_final:.1f}) vs P({p_score_final:.1f})
    </div>
    """)

    return mbti, "<br>".join(reasons), feats

# -----------------------------------------------------------------------------
# [추가] 감성/독성 기반 Big5 정밀 산출
# -----------------------------------------------------------------------------
def analyze_sentiment_score(sentences):
    """
    KNU 감성 사전을 이용하여 문장들의 평균 긍정/부정 점수를 계산
    Return: (pos_ratio, neg_ratio, avg_sentiment)
    """
    total_score = 0
    pos_score = 0
    neg_score = 0
    word_count = 0
    
    # KNU 사전을 활용 (SENTIMENT_DB)
    for sent in sentences:
        # 간단한 토큰화 (띄어쓰기 기준) 또는 Kiwi 토큰 활용 가능
        # 여기서는 Kiwi 토큰화가 이미 되어있지 않으므로 간단히 처리하거나,
        # app.py 상단의 kiwipiepy는 analyze_linguistic_features에서만 쓰임.
        # 성능을 위해 띄어쓰기 + 일부 조사 제거 매칭 시도
        words = sent.split()
        for w in words:
            # 조사 제거 등의 정규화는 복잡하므로, 있는 그대로 매칭하되
            # 사전에 있는 루트 단어도 매칭 (정확도는 떨어질 수 있으나 속도 중요)
            s = SENTIMENT_DB.get(w)
            if s is not None:
                word_count += 1
                total_score += s
                if s > 0: pos_score += s
                elif s < 0: neg_score += abs(s)
    
    if word_count == 0: return 0.0, 0.0, 0.0
    
    # 0~100점 스케일로 정규화된 지표를 만들기 위해 비율 계산
    # (단순 개수가 아니라 점수 비중)
    total_abs = pos_score + neg_score
    if total_abs == 0: return 0.0, 0.0, 0.0
    
    pos_ratio = pos_score / total_abs # 0.0 ~ 1.0
    neg_ratio = neg_score / total_abs # 0.0 ~ 1.0
    
    return pos_ratio, neg_ratio, total_score




# -----------------------
# [3] Flask 라우팅
# -----------------------
def get_db_connection():
    return pymysql.connect(**db_config)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    if 'user_id' in session: return redirect(url_for('upload_page'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET'])
def register_page(): return render_template('register.html')

@app.route('/api/register', methods=['POST'])
def register_api():
    try:
        email = request.form['email']
        password = request.form['password']
        username = request.form['username']
        nickname = request.form['nickname']
        gender = request.form['gender']
        birth_date = request.form['birth_date']
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = "INSERT INTO users (email, password_hash, username, nickname, gender, birth_date) VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(sql, (email, hashed_password, username, nickname, gender, birth_date))
        conn.commit()
        conn.close()
        flash("회원가입 완료. 로그인해주세요.")
        return redirect(url_for('login'))
    except Exception as e:
        flash(f"회원가입 실패: {e}")
        return redirect(url_for('register_page'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT * FROM users WHERE email = %s"
                cursor.execute(sql, (email,))
                user = cursor.fetchone()
                if user and check_password_hash(user['password_hash'], password):
                    session['user_id'] = user['user_id']
                    session['nickname'] = user['nickname']
                    return redirect(url_for('upload_page'))
                else:
                    flash("이메일 또는 비밀번호가 잘못되었습니다.")
        finally:
            conn.close()
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# [추가] 게스트 로그인 로직
def get_or_create_guest_user():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Check if guest exists
            sql = "SELECT * FROM users WHERE email = 'guest@echomind.com'"
            cursor.execute(sql)
            user = cursor.fetchone()
            
            if user:
                return user
            
            # 2. Create if not exists
            # 비밀번호는 랜덤 혹은 고정값 (로그인할 일이 없으므로 크게 중요치 않음)
            guest_pw = generate_password_hash("guest1234") 
            sql_insert = """
                INSERT INTO users (email, password_hash, username, nickname, gender, birth_date)
                VALUES ('guest@echomind.com', %s, 'GuestUser', '게스트', 'Non-Binary', '2000-01-01')
            """
            cursor.execute(sql_insert, (guest_pw,))
            conn.commit()
            
            # 3. Retrieve created user
            cursor.execute(sql)
            return cursor.fetchone()
    finally:
        conn.close()

@app.route('/guest_login')
def guest_login():
    try:
        user = get_or_create_guest_user()
        if user:
            session['user_id'] = user['user_id']
            session['nickname'] = user['nickname']
            flash("비회원(게스트)로 로그인되었습니다.")
            return redirect(url_for('upload_page'))
        else:
            flash("게스트 로그인 실패: 계정 생성 오류")
            return redirect(url_for('login'))
    except Exception as e:
        flash(f"Error: {e}")
        return redirect(url_for('login'))

@app.route('/upload', methods=['GET'])
def upload_page():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('upload.html', nickname=session['nickname'])

@app.route('/api/upload_chat', methods=['POST'])
def upload_api():
    print(">>> [DEBUG] /api/upload_chat 호출됨")
    sys.stdout.flush()

    if 'user_id' not in session: 
        print(">>> [DEBUG] 로그인 세션 없음 -> redirect")
        sys.stdout.flush()
        return redirect(url_for('login'))

    if 'chat_file' not in request.files: 
        print(">>> [DEBUG] 파일 없음 -> redirect")
        sys.stdout.flush()
        return redirect(request.url)
    
    file = request.files['chat_file']
    target_name = request.form.get('target_name', '').strip()
    
    print(f">>> [DEBUG] 파일명: {file.filename}, 분석대상: {target_name}")
    sys.stdout.flush()

    if not target_name:
        flash('분석할 대화명을 입력해주세요.')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], save_name)
        file.save(file_path)
        
        user_id = session['user_id']
        conn = get_db_connection()
        
        try:
            rows = parse_kakao_txt(file_path)
            my_sentences = []
            for r in rows:
                if r["speaker"] == target_name:
                    txt = r["text"]
                    if txt and txt not in SKIP_TOKENS:
                        cleaned = clean_text(txt)
                        if cleaned: my_sentences.append(cleaned)
            
            if len(my_sentences) < 5:
                flash(f"'{target_name}'님의 대화 내용이 너무 적습니다. 이름을 확인해주세요.")
                return redirect(url_for('upload_page'))

            # [핵심] 신규 언어 분석 함수 호출
            # 1. 상호작용 및 기본 특징 추출
            full_features, target_sentences = analyze_mbti_features(rows, target_name)
            
            if len(target_sentences) < 5:
                flash(f"'{target_name}'님의 대화 내용이 너무 적습니다(5문장 미만).")
                return redirect(url_for('upload_page'))

            # 2. 언어적 특징 심화 분석 (Kiwi)
            full_features = analyze_linguistic_features(target_sentences, full_features)
            
            # 3. MBTI 및 설명 생성
            # [수정] 함수를 여러 번 호출하면 feats 점수가 중복 누적되는 버그 수정
            # 한번만 호출해서 결과를 unpacking
            mbti_prediction, reasoning_text, debug_feats = calculate_final_mbti(full_features)

            # 4. 정밀 통계 (독성, 긍부정, 스타일)
            tox_count = 0
            for s in target_sentences:
                # 독성 (korean_bad_words.json + 기본 욕설)
                if any(bad in s for bad in BAD_WORDS): tox_count += 1
            
            total_sent = len(target_sentences)
            tox_ratio = tox_count / total_sent if total_sent else 0.0
            
            # KNU 감성 분석
            pos_ratio, neg_ratio, _ = analyze_sentiment_score(target_sentences)
            
            # [신규] 한국어 스타일 심층 분석 (TTR, 리액션 등)
            style_feats = analyze_korean_style_features(target_sentences)
            
            # 5. Big5 산출 (스타일 + 감성 + 독성 기반 고도화)
            big5_result = calculate_advanced_big5(style_feats, tox_ratio, pos_ratio, neg_ratio)

            # [디버깅] 중간 계산 값을 콘솔에 출력
            print("\n" + "="*50)
            print(f"   [상세 성향 분석 - 대상: {target_name}]")
            print("="*50)
            print(f"1. MBTI 결정: {mbti_prediction}")
            print(f"   - E: {debug_feats['e_score']:.1f} vs I: {debug_feats['i_score']:.1f}")
            print(f"   - S: {debug_feats['s_score']:.1f} vs N: {debug_feats['n_score']:.1f}")
            print(f"   - T: {debug_feats['t_score']:.1f} vs F: {debug_feats['f_score']:.1f}")
            print(f"   - J: {debug_feats['j_score']:.1f} vs P: {debug_feats['p_score']:.1f}")
            print(f"2. 언어 특징: 독성 {tox_ratio*100:.1f}%, 긍정 {pos_ratio*100:.1f}%, TTR {style_feats['ttr']:.2f}, 리액션 {style_feats['laughs']:.2f}")
            print(f"3. Big5 추론: Open({big5_result['openness']}), Consc({big5_result['conscientiousness']}), Extra({big5_result['extraversion']}), Agree({big5_result['agreeableness']}), Neuro({big5_result['neuroticism']})")
            print("="*50 + "\n")
            sys.stdout.flush()  # [추가] 출력 강제 플러시
            
            summary_text = f"분석 문장: {total_sent}개. 정밀 스타일 분석 기반 성향 도출."

            with conn.cursor() as cursor:
                sql_log = "INSERT INTO chat_logs (user_id, file_name, file_path, target_name, process_status) VALUES (%s, %s, %s, %s, 'COMPLETED')"
                cursor.execute(sql_log, (user_id, filename, file_path, target_name))
                log_id = cursor.lastrowid
                
                sql_result = """
                INSERT INTO personality_results 
                (user_id, log_id, openness, conscientiousness, extraversion, agreeableness, neuroticism, 
                 summary_text, mbti_prediction, reasoning_text, toxicity_score, sentiment_pos_ratio, sentiment_neg_ratio)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql_result, (
                    user_id, log_id,
                    big5_result['openness'], big5_result['conscientiousness'], 
                    big5_result['extraversion'], big5_result['agreeableness'], 
                    big5_result['neuroticism'], 
                    summary_text, mbti_prediction, reasoning_text,
                    tox_ratio, pos_ratio, neg_ratio
                ))
            conn.commit()
            return redirect(url_for('result_page', log_id=log_id))
            
        except Exception as e:
            conn.rollback()
            print(f"Error: {e}")
            flash(f"오류 발생: {str(e)}")
            return redirect(url_for('upload_page'))
        finally:
            conn.close()
    return redirect(url_for('upload_page'))

@app.route('/result/<int:log_id>')
def result_page(log_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
            SELECT r.*, l.file_name, l.target_name 
            FROM personality_results r
            JOIN chat_logs l ON r.log_id = l.log_id
            WHERE r.log_id = %s AND r.user_id = %s
            """
            cursor.execute(sql, (log_id, session['user_id']))
            result = cursor.fetchone()
            if not result:
                flash("결과를 찾을 수 없습니다.")
                return redirect(url_for('upload_page'))
            return render_template('result.html', data=result, nickname=session['nickname'])
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
