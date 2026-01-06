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
LINE_RE = re.compile(r"^\[(?P<name>.+?)\]\s+\[(?P<time>.*?)\]\s+(?P<msg>.+)$")
SKIP_TOKENS = {"사진", "이모티콘", "동영상", "삭제된 메시지입니다.", "보이스톡 해요.", "파일"}
BAD_WORDS = {"시발", "씨발", "병신", "개새끼", "존나", "미친", "죽어", "꺼져", "년", "놈"}

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
    t = re.sub(r"\s+", " ", t).strip()
    return t

# [한국어 스타일 분석 - 개선된 버전]
def analyze_korean_style(sentences):
    full_text = " ".join(sentences)
    if not full_text:
        return {"avg_len": 0, "self_ref": 0, "certainty": 0, "uncertainty": 0, "ttr": 0, "laughs": 0}

    tokens = kiwi.tokenize(full_text)
    total_words = len(tokens)
    if total_words == 0: total_words = 1
    
    self_ref_count = 0
    certainty_count = 0
    uncertainty_count = 0
    laugh_count = 0
    unique_morphs = set()

    self_pronouns = {"나", "저", "우리", "너", "본인"}
    self_determiners = {"내", "제", "네"}
    certainty_words = {"확실히", "분명", "반드시", "틀림없이", "당연", "명백", "결코"}
    uncertainty_words = {"아마", "글쎄", "약간", "좀", "어쩌면", "가", "듯", "모르"}
# [참고] 확신어에서 원래 있던 '진짜', '정말', '너무', '완전'은 P나 F 성향에 가까우므로 제거함

    for t in tokens:
        morph = t.form
        tag = t.tag
        unique_morphs.add(morph)
        
        # 1. 자기지시어 ('바나나' 제외, 진짜 '나'만)
        if tag == 'NP' and morph in self_pronouns: self_ref_count += 1
        elif tag == 'MM' and morph in self_determiners: self_ref_count += 1
            
        # 2. 리액션
        if morph in ['ㅋ', 'ㅎ', 'ㅠ', 'ㅜ']: laugh_count += 1
            
        # 3. 확신어
        if morph in certainty_words: certainty_count += 1
            
        # 4. 불확신
        if morph in uncertainty_words: uncertainty_count += 1
        if tag.startswith('E') and any(x in morph for x in ['나', '가', '지']): uncertainty_count += 1

    return {
        "avg_len": sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0,
        "self_ref": self_ref_count / total_words,
        "certainty": certainty_count / total_words,
        "uncertainty": uncertainty_count / total_words,
        "ttr": len(unique_morphs) / total_words,
        "laughs": laugh_count / total_words
    }

# [감성 분석 - KNU 사전 사용 (빠름)]
def analyze_sentiment_local(sentences):
    pos_score_sum = 0
    neg_score_sum = 0
    total_sentiment_words = 0
    
    full_text = " ".join(sentences)
    tokens = kiwi.tokenize(full_text)
    
    for t in tokens:
        word = t.form
        if word in SENTIMENT_DB:
            score = SENTIMENT_DB[word]
            if score >= 1:
                pos_score_sum += score
                total_sentiment_words += 1
            elif score <= -1:
                neg_score_sum += abs(score)
                total_sentiment_words += 1
                
    if total_sentiment_words == 0:
        return {"POSITIVE": 0.0, "NEGATIVE": 0.0, "NEUTRAL": 1.0}
    
    total_score = pos_score_sum + neg_score_sum + 0.001
    pos_ratio = pos_score_sum / total_score
    neg_ratio = neg_score_sum / total_score
    neu_ratio = 1.0 - (pos_ratio + neg_ratio)
    if neu_ratio < 0: neu_ratio = 0
    
    return {"POSITIVE": round(pos_ratio, 3), "NEGATIVE": round(neg_ratio, 3), "NEUTRAL": round(neu_ratio, 3)}

# [독성 분석 - 욕설 리스트 사용 (빠름)]
def analyze_toxicity_local(sentences):
    toxic_count = 0
    total = len(sentences)
    if total == 0: return 0.0
    for text in sentences:
        for bad in BAD_WORDS:
            if bad in text:
                toxic_count += 1
                break
    return toxic_count / total

# [Big 5 추론 - 한국어 최적화]
def infer_bigfive_korean(summary):
    s = summary
    st = s["style"]
    
    def normalize(val, scale=1.0, offset=0.0):
        val = (val * scale) + offset
        return min(1.0, max(0.0, val))

    # [1] 개방성 (Openness) - 주제 다양성(topic_div) 비중을 대폭 낮춤
    # topic_div가 카톡에선 항상 높게 나와서 무조건 N이 뜨는 문제 수정
    openness = (0.6 * normalize(st["ttr"], 2.0)) + \
               (0.1 * s.get("topic_div", 0.5)) + \
               (0.3 * normalize(st["avg_len"] / 15)) # 문장이 길어야 N(추상적) 인정

    # [2] 성실성 (Conscientiousness) - 리액션이 많으면 오히려 P일 확률 높임
    # 단어장을 줄였으므로 가중치는 300 유지하되, 웃음(laughs) 패널티를 강화
    conscientiousness = (0.6 * normalize(st["certainty"], 300.0)) + \
                        (0.2 * (1 - normalize(st["laughs"], 30.0))) + \
                        (0.2 * (1 - s["toxicity_avg"]))

    # [3] 외향성 (Extraversion) - 웃음기 뺐을 때 점수
    # 웃음(Laughs) 가중치를 60 -> 30으로 낮춤 (편한 사이면 I도 웃으므로)
    # 대신 긍정어(Positive) 비중을 높임
    extraversion = (0.3 * normalize(st["laughs"], 30.0)) + \
                   (0.4 * normalize(s["positive_ratio"], 1.5)) + \
                   (0.3 * normalize(st["self_ref"], 40.0))

    # [4] 우호성 (Agreeableness) - 긍정 단어를 써야 진짜 F
    # 웃음만 많다고 F 주지 않음 (비웃음일 수도 있음)
    agreeableness = (0.4 * (1 - normalize(s["toxicity_avg"], 20.0))) + \
                    (0.2 * normalize(st["laughs"], 30.0)) + \
                    (0.4 * normalize(s["positive_ratio"], 1.5))

    # [5] 신경성 (Neuroticism) - 기존 유지
    neuroticism = (0.4 * normalize(s["negative_ratio"], 0.7)) + \
                  (0.4 * normalize(st["uncertainty"], 15.0)) + \
                  (0.2 * normalize(s["toxicity_avg"], 10.0))

    return {
        "openness": round(openness * 100, 2),
        "conscientiousness": round(conscientiousness * 100, 2),
        "extraversion": round(extraversion * 100, 2),
        "agreeableness": round(agreeableness * 100, 2),
        "neuroticism": round(neuroticism * 100, 2),
    }


def calculate_mbti_and_reasoning(big5, summary_data):
    # 기준점(Threshold) 미세 조정
    # E: 외향성 점수 48점 이상이면 E (한국인은 I가 많으므로 기준을 살짝 낮춤)
    e_type = 'E' if big5['extraversion'] >= 48 else 'I'
    # N: 개방성 40점 기준
    n_type = 'N' if big5['openness'] >= 40 else 'S'     
    # F: 우호성 60점 기준
    f_type = 'F' if big5['agreeableness'] >= 60 else 'T' 
    # J: 성실성 40점 기준
    j_type = 'J' if big5['conscientiousness'] >= 40 else 'P' 
    
    mbti_result = f"{e_type}{n_type}{f_type}{j_type}"
    
    reasons = []
    # 멘트도 데이터 현실에 맞게 수정
    if e_type == 'E': reasons.append(f"대화 중 리액션과 자기 표현이 활발하여 **외향형(E)** 에너지가 느껴집니다.")
    else: reasons.append(f"차분하고 필요한 말 위주로 대화하여 **내향형(I)** 성향이 강합니다.")
    
    if n_type == 'N': reasons.append(f"다양한 어휘(TTR)를 구사하며 주제가 다채로워 **직관형(N)**입니다.")
    else: reasons.append(f"반복적인 용어 사용과 간결한 문장으로 **감각형(S)** 현실파입니다.")
    
    if f_type == 'F': reasons.append(f"상대방에게 긍정적인 표현과 호응을 많이 하여 **감정형(F)**입니다.")
    else: reasons.append(f"감정적 호응보다는 사실적이고 담백한 대화 패턴이라 **사고형(T)**입니다.")
    
    if j_type == 'J': reasons.append(f"확실한 표현(강조 부사 등)을 자주 사용하여 **판단형(J)** 계획파입니다.")
    else: reasons.append(f"유연하고 개방적인 표현(추측성 어미)이 많아 **인식형(P)**입니다.")

    full_reasoning = "<br>".join(reasons)
    return mbti_result, full_reasoning

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

            # 로컬 분석이라 매우 빠름. 5000개까지 분석
            MAX_LIMIT = 5000
            if len(my_sentences) > MAX_LIMIT:
                random.seed(42)
                my_sentences = random.sample(my_sentences, MAX_LIMIT)

            # [핵심] 로컬 함수 호출
            senti_result = analyze_sentiment_local(my_sentences)
            tox_avg = analyze_toxicity_local(my_sentences)
            korean_style = analyze_korean_style(my_sentences)
            
            pos_ratio = senti_result["POSITIVE"]
            neg_ratio = senti_result["NEGATIVE"]
            neu_ratio = senti_result["NEUTRAL"]

            summary_data = {
                "positive_ratio": float(pos_ratio),
                "negative_ratio": float(neg_ratio),
                "neutral_ratio": float(neu_ratio),
                "toxicity_avg": float(tox_avg),
                "style": korean_style,
                "topic_div": float(min(1.0, len(set(my_sentences)) / len(my_sentences)))
            }
            # [디버깅] 중간 계산 값을 콘솔에 출력 (이 부분을 복사해서 저에게 주세요)
            # -----------------------------------------------------------------
            print("\n" + "="*50)
            print(f"   [데이터 로그 - 대상: {target_name}]")
            print("="*50)
            print(f"1. 리액션(laughs, E/F):    {korean_style['laughs']:.5f}")
            print(f"2. 확신어(certainty, J):   {korean_style['certainty']:.5f}")
            print(f"3. 불확신(uncertainty, N): {korean_style['uncertainty']:.5f}")
            print(f"4. 자기지시(self_ref, E):  {korean_style['self_ref']:.5f}")
            print(f"5. 문장길이(avg_len, C):   {korean_style['avg_len']:.2f}")
            print(f"6. 어휘다양성(ttr, N):     {korean_style['ttr']:.5f}")
            print(f"7. 긍정비율(positive, E):  {pos_ratio:.5f}")
            print(f"8. 부정비율(negative, N):  {neg_ratio:.5f}")
            print(f"9. 독성비율(toxicity, A):  {tox_avg:.5f}")
            print("="*50 + "\n")
            # --------------------------------
            big5_result = infer_bigfive_korean(summary_data)
            mbti_prediction, reasoning_text = calculate_mbti_and_reasoning(big5_result, summary_data)
            
            print(f"1. 외향성(E) 점수: {big5_result['extraversion']}점  (기준: 48점 이상이면 E, 아니면 I)")
            print(f"2. 개방성(N) 점수: {big5_result['openness']}점  (기준: 50점 이상이면 N, 아니면 S)")
            print(f"3. 우호성(F) 점수: {big5_result['agreeableness']}점  (기준: 50점 이상이면 F, 아니면 T)")
            print(f"4. 성실성(J) 점수: {big5_result['conscientiousness']}점  (기준: 50점 이상이면 J, 아니면 P)")
            print("#" * 50 + "\n")
            summary_text = (f"총 {len(my_sentences)}문장 분석 완료. 긍정 {pos_ratio*100:.1f}%, 부정 {neg_ratio*100:.1f}%")

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