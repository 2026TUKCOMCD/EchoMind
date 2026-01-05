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

# -----------------------
# [0] 환경 설정 및 초기화
# -----------------------
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
PERSPECTIVE_API_KEY = os.getenv("PERSPECTIVE_API_KEY")

app = Flask(__name__)
app.secret_key = 'echomind_secret_key_secure_random_string'

# Kiwi 형태소 분석기 초기화 (속도 빠름)
kiwi = Kiwi()

# -----------------------
# [DB 설정] 실행 시 사용자 입력 받기
# -----------------------
print("\n" + "="*40)
print("   EchoMind DB 접속 설정")
print("="*40)

# 1. 사용자명 및 비밀번호 설정 (User Provided)
input_user = 'root'
input_password = '1234'

print("-" * 40 + "\n")

db_config = {
    'host': 'localhost',
    'user': input_user,      # 입력받은 값 사용
    'password': input_password, # 입력받은 값 사용
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
# [1] 한국어 분석 로직 (Kiwi 적용)
# -----------------------
LINE_RE = re.compile(r"^\[(?P<name>.+?)\]\s+\[(?P<time>.*?)\]\s+(?P<msg>.+)$")
SKIP_TOKENS = {"사진", "이모티콘", "동영상", "삭제된 메시지입니다.", "보이스톡 해요.", "파일"}

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
    t = re.sub(r"[ㅋㅎㅠㅜ]+", "", t)  # ㅋㅋㅋㅋ, ㅎㅎㅎ 등 제거
    t = re.sub(r"\s+", " ", t).strip()
    return t

def analyze_korean_style(sentences):
    full_text = " ".join(sentences)
    if not full_text:
        return {"avg_len": 0, "self_ref": 0, "certainty": 0, "uncertainty": 0, "ttr": 0}

    tokens = kiwi.tokenize(full_text)
    
    total_words = len(tokens)
    if total_words == 0: total_words = 1
    
    self_ref_count = 0
    certainty_count = 0
    uncertainty_count = 0
    unique_morphs = set()

    for t in tokens:
        morph = t.form
        tag = t.tag
        unique_morphs.add(morph)
        
        if morph in ["나", "저", "내", "제", "우리"] and tag.startswith('N'):
            self_ref_count += 1
            
        if morph in ["진짜", "정말", "너무", "완전", "확실히", "분명", "반드시", "개"] and tag.startswith('M'):
            certainty_count += 1
            
        if morph in ["듯", "나", "가", "글쎄", "아마", "지"] and (tag.startswith('E') or tag.startswith('M')):
            uncertainty_count += 1

    return {
        "avg_len": sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0,
        "self_ref": self_ref_count / total_words,
        "certainty": certainty_count / total_words,
        "uncertainty": uncertainty_count / total_words,
        "ttr": len(unique_morphs) / total_words
    }

def hf_sentiment_labels(texts):
    if not HF_TOKEN: return ["NEUTRAL"] * len(texts)
    HF_API_URL = "https://router.huggingface.co/hf-inference/models/cardiffnlp/twitter-xlm-roberta-base-sentiment"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    out = []
    for t in texts:
        payload = {"inputs": t[:500]} 
        try:
            r = requests.post(HF_API_URL, headers=headers, json=payload, timeout=5)
            if r.status_code == 200:
                js = r.json()
                arr = js[0] if isinstance(js, list) and js and isinstance(js[0], list) else js
                if isinstance(arr, list):
                    top = max(arr, key=lambda x: x["score"])
                    out.append(top["label"].upper())
                else: out.append("NEUTRAL")
            else: out.append("NEUTRAL")
        except: out.append("NEUTRAL")
        time.sleep(0.1)
    return out

def perspective_toxicity_scores(texts):
    if not PERSPECTIVE_API_KEY: return [0.0] * len(texts)
    PERSPECTIVE_URL = "https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze"
    scores = []
    for t in texts:
        try:
            data = {"comment": {"text": t[:1500]}, "languages": ["ko"], "requestedAttributes": {"TOXICITY": {}}}
            r = requests.post(f"{PERSPECTIVE_URL}?key={PERSPECTIVE_API_KEY}", json=data, timeout=5)
            if r.status_code == 200:
                val = r.json().get("attributeScores", {}).get("TOXICITY", {}).get("summaryScore", {}).get("value", 0.0)
                scores.append(float(val))
            else: scores.append(0.0)
        except: scores.append(0.0)
        time.sleep(1.04)
    return scores


def infer_bigfive_korean(summary):
    s = summary
    st = s["style"]
    
    # [수정] 정규화 함수: scale을 곱한 뒤 offset을 더해 기준점을 이동시킴
    def normalize(val, scale=1.0, offset=0.0):
        val = (val * scale) + offset
        return min(1.0, max(0.0, val))

    # 1. 개방성 (Openness) - N(상상) vs S(현실)
    # [수정] 기존 TTR * 2.0 -> 1.3으로 대폭 축소 (한국어 조사 거품 제거)
    # 주제가 다양하지 않으면(일상 대화) S가 나오도록 유도
    openness = (0.6 * normalize(st["ttr"], 1.3)) + (0.4 * s.get("topic_div", 0.5))

    # 2. 성실성 (Conscientiousness) - J(계획) vs P(즉흥)
    # 문장 길이(avg_len)가 길면 신중한 것으로 봄
    conscientiousness = (0.4 * normalize(st["certainty"], 10.0)) + \
                        (0.3 * (1 - s["toxicity_avg"])) + \
                        (0.3 * normalize(st["avg_len"] / 25))

    # 3. 외향성 (Extraversion) - E(외향) vs I(내향)
    # 긍정 비율 가중치를 높임
    extraversion = (0.5 * normalize(s["positive_ratio"], 1.5)) + \
                   (0.3 * normalize(st["avg_len"] / 20)) + \
                   (0.2 * normalize(st["self_ref"], 10.0))

    # 4. 우호성 (Agreeableness) - F(공감) vs T(논리)
    # [수정] 중요! '중립' 비율(neutral_ratio)도 30% 점수에 반영
    # 싸우지 않고 평범하게 말하면(Neutral) 착한(F) 것으로 인정해줌
    neutral_score = s.get("neutral_ratio", 0.5) * 0.3
    agreeableness = (0.4 * (1 - s["toxicity_avg"])) + \
                    (0.3 * normalize(s["positive_ratio"], 1.2)) + \
                    neutral_score + \
                    (0.1 * normalize(st["uncertainty"], 5.0))

    # 5. 신경성 (Neuroticism)
    neuroticism = (0.5 * s["negative_ratio"]) + \
                  (0.3 * normalize(st["uncertainty"], 5.0)) + \
                  (0.2 * s["toxicity_avg"])

    return {
        "openness": round(openness * 100, 2),
        "conscientiousness": round(conscientiousness * 100, 2),
        "extraversion": round(extraversion * 100, 2),
        "agreeableness": round(agreeableness * 100, 2),
        "neuroticism": round(neuroticism * 100, 2),
    }

def calculate_mbti_and_reasoning(big5, summary_data):
    e_type = 'E' if big5['extraversion'] >= 50 else 'I'
    n_type = 'N' if big5['openness'] >= 55 else 'S'     #N이 더 안나오도록 유도
    f_type = 'F' if big5['agreeableness'] >= 45 else 'T' #F가 더 잘나오도록 유도
    j_type = 'J' if big5['conscientiousness'] >= 45 else 'P' #J가 더 잘나오도록 유도
    
    mbti_result = f"{e_type}{n_type}{f_type}{j_type}"
    
    reasons = []
    if e_type == 'E': reasons.append(f"대화량이 많고 긍정적인 표현이 돋보여 **외향형(E)**으로 분석되었습니다.")
    else: reasons.append(f"필요한 말 위주로 차분하게 대화하여 **내향형(I)** 성향이 강합니다.")
    
    if n_type == 'N': reasons.append(f"다양한 어휘(TTR {summary_data['style']['ttr']:.2f})를 구사하여 **직관형(N)**입니다.")
    else: reasons.append(f"반복되고 익숙한 표현을 선호하여 **감각형(S)**으로 보입니다.")
    
    if f_type == 'F': reasons.append(f"상대방에게 우호적이고(독성 {summary_data['toxicity_avg']:.2f}) 긍정적인 반응을 보여 **감정형(F)**입니다.")
    else: reasons.append(f"감정 표현보다는 객관적 사실 위주의 대화로 **사고형(T)** 성향입니다.")
    
    if j_type == 'J': reasons.append(f"확실한 표현(강조 부사 등)을 사용하여 **판단형(J)**으로 예측됩니다.")
    else: reasons.append(f"유연하고 개방적인 어체(추측성 어미)가 보여 **인식형(P)**입니다.")

    full_reasoning = "<br>".join(reasons)
    return mbti_result, full_reasoning

# -----------------------
# [2] Flask 라우팅
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

            MAX_LIMIT = 200  # 분석할 총 문장 수 제한
            # 문장이 제한보다 많을 때만 줄이기 작업을 수행
            if len(my_sentences) > MAX_LIMIT:
                print(f"[알림] 문장이 {len(my_sentences)}개로 많아 '{MAX_LIMIT}'개로 압축합니다.")
                
                # 전략: 절반은 '긴 문장'(심층 분석용), 절반은 '랜덤'(일상 대화용)으로 채움
                half_limit = MAX_LIMIT // 2 
                
                # 1. 전체를 길이순으로 정렬
                # (긴 문장이 리스트 앞쪽으로, 짧은 문장이 뒤쪽으로 감)
                sorted_by_len = sorted(my_sentences, key=len, reverse=True)
                
                # 2. 상위 50%는 가장 긴 문장들로 채택
                long_part = sorted_by_len[:half_limit]
                
                # 3. 나머지는 '선택받지 못한 나머지 문장들' 중에서 랜덤 추출
                remaining_pool = sorted_by_len[half_limit:]
                
                random.seed(42) # 결과 재현을 위해 시드 고정
                # 남은 것들 중에서 (MAX_LIMIT - half_limit) 개수만큼 뽑음
                random_part = random.sample(remaining_pool, MAX_LIMIT - len(long_part))
                
                # 4. 두 리스트 합치기
                my_sentences = long_part + random_part
                
                # 5. 분석 순서가 섞이도록 최종 셔플 (API 호출 시 긴 것만 몰리지 않게)
                random.shuffle(my_sentences)

            senti_labels = hf_sentiment_labels(my_sentences)
            tox_scores = perspective_toxicity_scores(my_sentences)
            korean_style = analyze_korean_style(my_sentences)
            
            cnt = pd.Series(senti_labels).value_counts()
            n = len(my_sentences)
            pos_ratio = cnt.get("POSITIVE", 0) / n
            neg_ratio = cnt.get("NEGATIVE", 0) / n
            neu_ratio = cnt.get("NEUTRAL", 0) / n  # [추가] 중립 비율 계산
            tox_avg = float(np.mean(tox_scores)) if tox_scores else 0.0
            
            summary_data = {
                "positive_ratio": float(pos_ratio),
                "negative_ratio": float(neg_ratio),
                "neutral_ratio": float(neu_ratio), # [추가] 분석 함수로 전달
                "toxicity_avg": float(tox_avg),
                "style": korean_style,
                "topic_div": float(min(1.0, len(set(my_sentences)) / n))
            }
            
            big5_result = infer_bigfive_korean(summary_data)
            mbti_prediction, reasoning_text = calculate_mbti_and_reasoning(big5_result, summary_data)
            
            summary_text = (f"총 {n}문장 분석 완료. 긍정 {pos_ratio*100:.1f}%, 독성 {tox_avg:.3f}")

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
            print(e)
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
