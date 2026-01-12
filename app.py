import os
import re
import json
import time
import statistics
import pymysql
import requests
import numpy as np
import pandas as pd
import getpass
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
    'host': 'localhost',
    'user': 'root',        # 사용자님이 설정한 ID
    'password': '1234',    # 사용자님이 설정한 비번
    'db': 'echomind_db',
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
LINE_RE = re.compile(r"^\[(?P<name>.+?)\]\s+\[(?P<time>.*?)\]\s+(?P<msg>.+)$")
SKIP_TOKENS = {"사진", "이모티콘", "동영상", "삭제된 메시지입니다.", "보이스톡 해요.", "파일", "샵검색"}
BAD_WORDS = {"시발", "씨발", "병신", "개새끼", "존나", "미친", "죽어", "꺼져", "년", "놈"}

# [단어 사전 정의]
# 1. E vs I
E_ENDINGS = {'어', '자', '까', '해', '봐', '지', '니', '냐'} # 권유, 질문, 공감 유도
I_ENDINGS = {'다', '음', '임', '셈', '함', '듯', '네'} # 서술, 독백, 단답

# 2. S vs N
S_KEYWORDS = {'원', '개', '번', '시', '분', '초', '년', '월', '일', '미터', 'kg', '오늘', '어제', '내일', '지금'} # 구체적 단위/시점
N_KEYWORDS = {'만약', '혹시', '아마', '미래', '의미', '상상', '느낌', '분위기', '기분', '우주', '영원', '사랑', '꿈'} # 추상적/가정

# 3. T vs F
T_KEYWORDS = {'왜', '그래서', '때문에', '결과', '이유', '원인', '효율', '해결', '분석', '팩트', '따라서', '즉', '결론'} # 인과/논리
F_KEYWORDS = {'고마워', '미안', '대박', '진짜', '너무', '완전', '헐', 'ㅠㅠ', 'ㅜㅜ', '행복', '슬퍼', '좋아', '싫어', '걱정'} # 감정/공감/리액션

# 4. J vs P
J_KEYWORDS = {'계획', '일정', '예약', '시간', '준비', '확인', '정리', '미리', '약속', '규칙', '순서', '목표', '완료'} # 계획/체계
P_KEYWORDS = {'갑자기', '일단', '그냥', '대충', '나중에', '언젠가', '아무거나', '변동', '자유', '내맘', '그때'} # 유연/즉흥

def parse_kakao_txt(path: str):
    rows = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\n")
                m = LINE_RE.match(line)
                if not m:
                    continue
                rows.append({
                    "speaker": m.group("name").strip(),
                    "time": m.group("time"),
                    "text": m.group("msg").strip(),
                })
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
            time_part = re.sub(r"[^0-9:]", "", ts)
            if ':' not in time_part: return -1 # 파싱 실패
            
            hh, mm = map(int, time_part.split(':'))
            
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
        # 명사(NNG, NNP), 수사(NR), 관형사(MM) 위주 확인
        if m in S_KEYWORDS or tag == 'SN': # 숫자 포함
            feats['s_score'] += 1.5
        if m in N_KEYWORDS:
            feats['n_score'] += 1.5
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
    
    return feats

def calculate_final_mbti(feats):
    # Rule-Set Weights
    
    # 1. Extraversion (E) vs Introversion (I)
    # E factors: Fast Reply (< 2 min), Initiation, Turn Length(Short & Frequent), Endings
    # I factors: Slow Reply (> 5 min), Long Turn, Endings
    
    # Reply Time Score: (Standard 5 min = 0)
    # < 2 min: E+2, > 10 min: I+2
    if feats['avg_reply_time'] < 2: feats['e_score'] += 3.0
    elif feats['avg_reply_time'] > 10: feats['i_score'] += 3.0
    
    # Turn Length: Short burst (1~2) -> E / Long paragraph (3+) -> I
    if feats['turn_length_avg'] < 1.5: feats['e_score'] += 2.0
    else: feats['i_score'] += 2.0
    
    # Initiation
    if feats['initiation_count'] > 5: feats['e_score'] += 2.0
    
    # E/I Decision
    e_total = feats['e_score']
    i_total = feats['i_score']
    # Default Bias to I (Korean Data) -> E needs +15% more
    e_final = 'E' if e_total > i_total * 0.9 else 'I'
    
    # 2. Sensing (S) vs Intuition (N)
    # S factors: Concrete numbers, S_KEYWORDS
    # N factors: Abstract words, N_KEYWORDS
    s_final = 'S' if feats['s_score'] > feats['n_score'] else 'N'
    
    # 3. Thinking (T) vs Feeling (F)
    # T factors: Logic words
    # F factors: Emotion words
    f_final = 'F' if feats['f_score'] > feats['t_score'] else 'T'
    
    # 4. Judging (J) vs Perceiving (P)
    j_final = 'J' if feats['j_score'] > feats['p_score'] else 'P'
    
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

    return mbti, "<br>".join(reasons), feats

# [유틸리티] 톡방 요약 (Big5는 호환성 유지 위해 더미값 리턴하거나 대충 계산)
def infer_bigfive_dummy(mbti):
    # Map MBTI back to Big5 roughly to prevent SQL errors
    # E -> Extraversion
    # N -> Openness
    # F -> Agreeableness
    # J -> Conscientiousness
    # T/A (Neuroticism) -> Random
    mapping = {
        'E': 75, 'I': 35,
        'N': 75, 'S': 35,
        'F': 75, 'T': 35,
        'J': 75, 'P': 35
    }
    return {
        "extraversion": mapping[mbti[0]],
        "openness": mapping[mbti[1]],
        "agreeableness": mapping[mbti[2]],
        "conscientiousness": mapping[mbti[3]],
        "neuroticism": 50.0
    }


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

@app.route('/upload', methods=['GET'])
def upload_page():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('upload.html', nickname=session['nickname'])

@app.route('/api/upload_chat', methods=['POST'])
def upload_api():
    if 'user_id' not in session: return redirect(url_for('login'))
    if 'chat_file' not in request.files: return redirect(request.url)
    
    file = request.files['chat_file']
    target_name = request.form.get('target_name', '').strip()
    
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
            mbti_prediction, reasoning_text, debug_feats = calculate_final_mbti(full_features)
            big5_result = infer_bigfive_dummy(mbti_prediction) # DB 호환용 더미

            # 4. 기존 통계 (독성, 긍부정) - DB 저장용 단순 계산
            # (기존 함수가 삭제되었으므로 여기서 약식으로 계산하여 호환성 유지)
            tox_count = 0
            pos_count = 0
            neg_count = 0
            total_sent = len(target_sentences)
            
            for s in target_sentences:
                # 독성
                if any(bad in s for bad in BAD_WORDS): tox_count += 1
                # 긍부정 (간이)
                if any(w in s for w in F_KEYWORDS): pos_count += 1
                elif any(w in s for w in T_KEYWORDS): neg_count += 0.5 # T단어는 부정까진 아니지만... 감성사전이 없으니 약식
            
            tox_avg = tox_count / total_sent if total_sent else 0
            # SentiWord_info.json을 다시 로드하지 않고 키워드로 대체 or 0.0 처리
            # (사용자가 MBTI 정확도를 원했으니 감성점수는 크게 중요치 않음)
            pos_ratio = pos_count / total_sent if total_sent else 0
            neg_ratio = 0.0 # 약식
            
            # [디버깅] 중간 계산 값을 콘솔에 출력
            print("\n" + "="*50)
            print(f"   [MBTI 언어 특징 분석 - 대상: {target_name}]")
            print("="*50)
            print(f"1. E/I - 답장속도: {debug_feats['avg_reply_time']:.1f}분, 선톡: {debug_feats['initiation_count']}회")
            print(f"         E점수: {debug_feats['e_score']:.2f} vs I점수: {debug_feats['i_score']:.2f}")
            print(f"2. S/N - 구체어(S): {debug_feats['s_score']:.2f} vs 추상어(N): {debug_feats['n_score']:.2f}")
            print(f"3. T/F - 논리어(T): {debug_feats['t_score']:.2f} vs 공감어(F): {debug_feats['f_score']:.2f}")
            print(f"4. J/P - 계획어(J): {debug_feats['j_score']:.2f} vs 유연어(P): {debug_feats['p_score']:.2f}")
            print(f"▶ 최종 결과: {mbti_prediction}")
            print("="*50 + "\n")

            summary_text = f"분석 문장: {total_sent}개. 주요 특징 기반 MBTI 추론 결과."

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
                    tox_avg, pos_ratio, neg_ratio
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
    app.run(debug=True, port=5000)