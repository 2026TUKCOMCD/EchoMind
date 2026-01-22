# app.py
# -*- coding: utf-8 -*-

"""
[EchoMind] Flask 기반 통합 백엔드 API 및 컨트롤러 엔진
======================================================================

[1. 시스템 아키텍처 및 컨트롤러 역할]
본 모듈은 EchoMind 서비스의 '브레인' 역할을 하는 엔트리 포인트입니다. 
MVC 패턴에서 Controller를 담당하며, 프론트엔드(Jinja2)와 백엔드 서비스(LLM 분석, 매칭 로직) 
및 AWS RDS 데이터베이스 사이의 데이터 흐름을 오케스트레이션합니다.

[2. 핵심 비즈니스 파이프라인]
- 인증 시스템: Werkzeug 해시 기반 보안 인증 및 Flask Session을 활용한 권한 제어.
- 분석 엔진 인터페이스: 업로드된 텍스트 데이터를 main.py와 연동하여 OpenAI LLM에 전달, 
  Big5/MBTI 등 심리 지표를 추출한 후 personality_results 테이블에 객체 관계 매핑(ORM) 저장.
- 통합 매칭 엔진: MatchManager 및 Matcher 모듈을 호출하여 성향 유사도 기반의 후보 추천 
  및 매칭 신청/수락/거절의 트랜잭션 수명 주기를 관리합니다.

[3. 데이터 레이어 및 인터페이스 특징]
- SQLAlchemy ORM을 사용하여 SQL 마스터 스키마와 파이썬 객체를 동기화합니다.
- 통합 인박스(Integrated Inbox): 기존의 독립적인 알림 시스템과 매칭 신청함을 
  데이터베이스 수준에서 통합 조회(Join)하여 하나의 API 엔드포인트(/inbox)로 가공 배달합니다.
- 환경 주입(Dependency Injection): config.py를 통해 개발(Dev) 및 운영(Prod) 환경의 
  네트워크 및 보안 설정을 동적으로 주입받습니다.
"""

import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# [설정 및 커스텀 모듈 연동]
from config import config_by_name 
from match_manager import MatchManager 
import main as analyzer 

app = Flask(__name__)

# --- 환경 설정 및 유효성 체크 ---
env = os.getenv('FLASK_ENV', 'development')
config_class = config_by_name.get(env, config_by_name['default'])
app.config.from_object(config_class)
config_class.init_app(app) 

db = SQLAlchemy(app)

# --- 데이터베이스 모델 ---
class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    nickname = db.Column(db.String(100))

class PersonalityResult(db.Model):
    __tablename__ = 'personality_results'
    result_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    log_id = db.Column(db.Integer, nullable=False, default=0)
    is_representative = db.Column(db.Boolean, default=True)
    
    openness = db.Column(db.Float, nullable=False)
    conscientiousness = db.Column(db.Float, nullable=False)
    extraversion = db.Column(db.Float, nullable=False)
    agreeableness = db.Column(db.Float, nullable=False)
    neuroticism = db.Column(db.Float, nullable=False)
    line_count_at_analysis = db.Column(db.Integer, default=0)
    
    mbti_prediction = db.Column(db.String(10))
    socionics_prediction = db.Column(db.String(10))
    summary_text = db.Column(db.Text)
    full_report_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- 보안 및 세션 제어 ---
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is None:
            flash("로그인이 필요한 서비스입니다.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def load_user():
    user_id = session.get('user_id')
    g.user = db.session.get(User, user_id) if user_id else None

# --- 로그인 및 회원가입 ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'])
        new_user = User(
            email=request.form['email'],
            password_hash=hashed_pw,
            username=request.form['username'],
            nickname=request.form.get('nickname')
        )
        try:
            db.session.add(new_user)
            db.session.commit()
            flash("회원가입 완료! 로그인해주세요.", "success")
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash("이미 존재하는 이메일입니다.", "danger")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            session['user_id'] = user.user_id
            return redirect(url_for('home'))
        flash("로그인 정보가 틀렸습니다.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("로그아웃 되었습니다.", "info")
    return redirect(url_for('login'))

# --- 라우팅 컨트롤러 ---
@app.route('/')
def home():
    if not g.user: return redirect(url_for('login'))
    unread_count = len(MatchManager.get_unread_notifications(g.user.user_id))
    return render_template('index.html', user=g.user, unread_count=unread_count)

@app.route('/result')
@login_required
def view_result():
    """사용자의 최신 대표 성향 분석 결과를 보여주는 화면"""
    result = PersonalityResult.query.filter_by(user_id=g.user.user_id, is_representative=True).first()
    if not result:
        flash("아직 분석된 결과가 없습니다. 대화 로그를 업로드해주세요.", "info")
        return redirect(url_for('upload_chat'))
    return render_template('result.html', result=result)

# --- 분석 및 업로드 파이프라인 ---
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_chat():
    if request.method == 'POST':
        file = request.files.get('file')
        target_name = request.form.get('target_name')

        if not target_name:
            flash("분석할 상대방의 대화명을 입력해주세요.", "danger")
            return redirect(request.url)

        if file and file.filename.endswith('.txt'):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(save_path) 

            try:
                rows, quality = analyzer.parse_target_rows(save_path, target_name)
                
                if not rows:
                    raise ValueError(f"'{target_name}' 님의 대화 데이터를 찾을 수 없습니다.")

                signals = analyzer.compute_numeric_signals(rows)
                samples = analyzer.sample_texts_for_llm(rows, 120, 18000)
                
                from openai import OpenAI
                client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                profile = analyzer.call_llm_profile(client, os.environ.get("OPENAI_MODEL"), {
                    "samples": samples, "numeric_signals": signals
                })

                PersonalityResult.query.filter_by(user_id=g.user.user_id).update({'is_representative': False})

                new_profile = PersonalityResult(
                    user_id=g.user.user_id,
                    openness=float(profile['big5']['scores_0_100']['openness']),
                    conscientiousness=float(profile['big5']['scores_0_100']['conscientiousness']),
                    extraversion=float(profile['big5']['scores_0_100']['extraversion']),
                    agreeableness=float(profile['big5']['scores_0_100']['agreeableness']),
                    neuroticism=float(profile['big5']['scores_0_100']['neuroticism']),
                    line_count_at_analysis=quality.parsed_lines,
                    mbti_prediction=profile['mbti']['type'],
                    socionics_prediction=profile['socionics']['type'],
                    summary_text=profile['summary']['one_paragraph'],
                    full_report_json=profile
                )
                
                db.session.add(new_profile)
                db.session.commit()
                flash("분석이 완료되었습니다!", "success")
                return redirect(url_for('view_result'))

            except Exception as e:
                db.session.rollback()
                flash(f"분석 오류: {str(e)}", "danger")
            finally:
                if os.path.exists(save_path): os.remove(save_path)
                    
    return render_template('upload.html')

# --- 매칭 및 통합 인박스 ---

@app.route('/matching')
@login_required
def start_matching():
    """매칭 후보 목록 조회 (match.html 사용)"""
    candidates = MatchManager.get_matching_candidates(g.user.user_id, limit=5)
    return render_template('match.html', candidates=candidates)

@app.route('/inbox')
@login_required
def match_inbox():
    """받은 신청, 보낸 신청 상태, 시스템 알림을 모두 확인하는 통합 화면"""
    conn = MatchManager.get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 나에게 온 신청 (받은 신청)
            sql_received = """
                SELECT r.request_id, u.username as sender_name, u.nickname as sender_nickname, r.created_at, r.status
                FROM match_requests r
                JOIN users u ON r.sender_id = u.user_id
                WHERE r.receiver_id = %s AND r.status = 'PENDING'
                ORDER BY r.created_at DESC
            """
            cursor.execute(sql_received, (g.user.user_id,))
            received_requests = cursor.fetchall()

            # 2. 내가 상대에게 보낸 신청 (보낸 신청 결과 확인용)
            sql_sent = """
                SELECT r.request_id, u.username as receiver_name, u.nickname as receiver_nickname, r.created_at, r.status
                FROM match_requests r
                JOIN users u ON r.receiver_id = u.user_id
                WHERE r.sender_id = %s
                ORDER BY r.created_at DESC
            """
            cursor.execute(sql_sent, (g.user.user_id,))
            sent_requests = cursor.fetchall()

            # 3. 시스템 알림(alerts) 조회
            alerts = MatchManager.get_unread_notifications(g.user.user_id)
            
            # 4. 알림 확인 즉시 읽음 처리
            MatchManager.mark_notifications_as_read(g.user.user_id)

    finally:
        conn.close()

    return render_template('inbox.html', 
                           requests=received_requests, 
                           sent_requests=sent_requests, 
                           alerts=alerts)

@app.route('/apply_match/<int:receiver_id>', methods=['POST'])
@login_required
def apply_match(receiver_id):
    result = MatchManager.send_match_request(g.user.user_id, receiver_id)
    flash(result['message'], 'success' if result['success'] else 'danger')
    return redirect(url_for('start_matching'))

@app.route('/respond_match/<int:request_id>/<action>')
@login_required
def respond_match(request_id, action):
    result = MatchManager.respond_to_request(request_id, action.upper())
    flash(result['message'], "success" if result['success'] else "danger")
    return redirect(url_for('match_inbox'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
    app.run(host=config_class.RUN_HOST, port=config_class.RUN_PORT)
