# app.py
# -*- coding: utf-8 -*-

"""
[EchoMind] Flask 기반 통합 백엔드 API 및 컨트롤러 엔진
======================================================================
이 파일은 애플리케이션의 진입점(Entry Point)으로, 라우팅, 인증, 파일 처리, 
및 분석 파이프라인의 오케스트레이션을 담당합니다.
"""

import os
import uuid
import re
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import aliased
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# [설정 및 커스텀 모듈 임포트]
from config import config_by_name 
from match_manager import MatchManager 
import main as analyzer 
import visualize_profile 

app = Flask(__name__)

# --- 환경 설정 (Environment Setup) ---
env = os.getenv('FLASK_ENV', 'development')
config_class = config_by_name.get(env, config_by_name['default'])
app.config.from_object(config_class)
config_class.init_app(app)

# 업로드 폴더 자동 생성
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER']) 

db = SQLAlchemy(app)

# --- 데이터베이스 모델 (Database Models) ---
class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(100), nullable=False) # 실명
    nickname = db.Column(db.String(100)) # 닉네임
    gender = db.Column(db.Enum('MALE', 'FEMALE', 'OTHER', name='gender_enum'))
    birth_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatLog(db.Model):
    __tablename__ = 'chat_logs'
    log_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    target_name = db.Column(db.String(100), nullable=False) # 분석 대상자 이름
    process_status = db.Column(db.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', name='process_status_enum'), default='PENDING')
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

class PersonalityResult(db.Model):
    __tablename__ = 'personality_results'
    result_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    log_id = db.Column(db.Integer, db.ForeignKey('chat_logs.log_id', ondelete='CASCADE'), nullable=False)
    is_representative = db.Column(db.Boolean, default=True) # 대표 결과 여부
    
    line_count_at_analysis = db.Column(db.Integer, default=0) # 분석 당시 대화 라인 수
    
    # Big5 점수 (0~100)
    openness = db.Column(db.Float, nullable=False)
    conscientiousness = db.Column(db.Float, nullable=False)
    extraversion = db.Column(db.Float, nullable=False)
    agreeableness = db.Column(db.Float, nullable=False)
    neuroticism = db.Column(db.Float, nullable=False)
    big5_confidence = db.Column(db.Float, default=0.0)
    
    # MBTI & Socionics
    mbti_prediction = db.Column(db.String(10))
    mbti_confidence = db.Column(db.Float, default=0.0)
    socionics_prediction = db.Column(db.String(10))
    socionics_confidence = db.Column(db.Float, default=0.0)
    
    summary_text = db.Column(db.Text)
    reasoning_text = db.Column(db.Text)
    full_report_json = db.Column(db.JSON) # 전체 JSON 원본 저장
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MatchRequest(db.Model):
    __tablename__ = 'match_requests'
    request_id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.Enum('PENDING', 'ACCEPTED', 'REJECTED', name='match_status_enum'), default='PENDING')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Notification(db.Model):
    __tablename__ = 'notifications'
    notification_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- 보안 및 세션 관리 (Security & Session) ---
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is None:
            flash("로그인이 필요합니다.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. 서버가 관리자 모드로 실행되었는지 확인

        
        # 2. 관리자 세션 확인
        if not session.get('is_admin'):
            flash("관리자 로그인이 필요합니다.", "warning")
            return redirect(url_for('admin_login'))
            
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def load_user():
    user_id = session.get('user_id')
    g.user = db.session.get(User, user_id) if user_id else None

# --- 로그인 및 회원가입 (Auth) ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'])
        new_user = User(
            email=request.form['email'],
            password_hash=hashed_pw,
            username=request.form['username'],
            nickname=request.form.get('nickname'),
            gender=request.form.get('gender'),
            birth_date=datetime.strptime(request.form['birth_date'], '%Y-%m-%d').date() if request.form.get('birth_date') else None
        )
        try:
            db.session.add(new_user)
            db.session.commit()
            flash("회원가입이 완료되었습니다! 로그인해주세요.", "success")
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
        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("로그아웃 되었습니다.", "info")
    return redirect(url_for('login'))

# --- 라우팅 컨트롤러 (Routing Controllers) ---
@app.route('/')
def home():
    if not g.user: return redirect(url_for('login'))
    unread_count = len(MatchManager.get_unread_notifications(g.user.user_id))
    return render_template('index.html', user=g.user, unread_count=unread_count)

@app.route('/result')
@app.route('/result/<int:result_id>')
@login_required
def view_result(result_id=None):
    """결과 조회 페이지 (특정 ID 또는 대표 결과)"""
    if result_id:
        result = PersonalityResult.query.filter_by(user_id=g.user.user_id, result_id=result_id).first()
    else:
        result = PersonalityResult.query.filter_by(user_id=g.user.user_id, is_representative=True).first()
    if not result:
        flash("분석된 결과가 없습니다. 채팅 로그를 먼저 업로드해주세요.", "info")
        return redirect(url_for('upload_chat'))
        
    # [Embedded Report Strategy]
    try:
        if result.full_report_json:
             # [Robustness Fix] full_report_json 구조 확인
            data_to_pass = result.full_report_json
            if 'llm_profile' not in data_to_pass:
                # 레거시 데이터 버그 수정 (프로필만 저장된 경우 래핑)
                data_to_pass = {
                    "meta": { "speaker_name": "Unknown" },
                    "llm_profile": result.full_report_json
                }

            # HTML 바디 생성
            html_content = visualize_profile.generate_report_html(data_to_pass, return_body_only=True)
            return render_template('result.html', report_content=html_content)
        else:
            flash("상세 리포트 데이터가 없어 결과를 표시할 수 없습니다.", "warning")
            return redirect(url_for('upload_chat'))
    except Exception as e:
        flash(f"리포트 생성 실패: {str(e)}", "danger")
        return redirect(url_for('upload_chat'))

@app.route('/history')
@login_required
def history():
    """분석 히스토리 페이지"""
    # 1. 사용자의 모든 결과 조회 (최신순)
    results = PersonalityResult.query.filter_by(user_id=g.user.user_id).order_by(PersonalityResult.created_at.desc()).all()
    
    # 2. 현재 대표 결과 찾기
    active_result = next((r for r in results if r.is_representative), None)
    
    return render_template('history.html', results=results, active_result=active_result)

@app.route('/set_representative/<int:result_id>', methods=['POST'])
@login_required
def set_representative(result_id):
    """특정 결과를 대표 결과로 설정"""
    try:
        # 1. 해당 결과가 본인 것인지 확인
        target = PersonalityResult.query.filter_by(user_id=g.user.user_id, result_id=result_id).first_or_404()
        
        # 2. 기존 대표 해제 및 새 대표 설정
        PersonalityResult.query.filter_by(user_id=g.user.user_id).update({'is_representative': False})
        target.is_representative = True
        db.session.commit()
        
        flash("대표 프로필이 변경되었습니다.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"변경 실패: {str(e)}", "danger")
        
    return redirect(url_for('history'))

@app.route('/download_json')
@login_required
def download_result_json():
    """대표 결과(Representative Result)를 JSON 파일로 다운로드"""
    result = PersonalityResult.query.filter_by(user_id=g.user.user_id, is_representative=True).first()
    
    if not result or not result.full_report_json:
        flash("다운로드할 분석 결과가 없습니다.", "warning")
        return redirect(url_for('view_result'))

    # JSON 응답 생성
    response = app.response_class(
        response=json.dumps(result.full_report_json, indent=4, ensure_ascii=False),
        status=200,
        mimetype='application/json'
    )
    
    # 파일명 설정 (예: result_20231025.json)
    filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

# --- 분석 및 업로드 파이프라인 (Analysis Pipeline) ---
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_chat():
    if request.method == 'POST':
        file = request.files.get('file')
        target_name = request.form.get('target_name')

        # 1. JSON 파일 직접 업로드 처리
        if file and file.filename.endswith('.json'):
            try:
                data = json.load(file)
                
                # 유효성 검사
                if 'llm_profile' not in data:
                    flash("잘못된 profile.json 형식입니다. (llm_profile 누락)", "danger")
                    return redirect(request.url)
                    
                profile = data['llm_profile']
                meta = data.get('meta', {})
                
                # 타겟 이름 결정 (메타데이터 우선)
                target_name_from_json = meta.get('speaker_name', 'Unknown')
                if not target_name:
                    target_name = target_name_from_json
                    
                if not target_name: 
                     target_name = "Unknown"

                # ChatLog 생성 (Fake Log)
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                
                new_log = ChatLog(
                    user_id=g.user.user_id,
                    file_name=filename,
                    file_path=save_path,
                    target_name=target_name,
                    process_status='COMPLETED'
                )
                db.session.add(new_log)
                db.session.flush()

                # 기존 대표 결과 해제
                PersonalityResult.query.filter_by(user_id=g.user.user_id).update({'is_representative': False})

                # PersonalityResult 저장
                new_profile = PersonalityResult(
                    user_id=g.user.user_id,
                    log_id=new_log.log_id,
                    is_representative=True,
                    
                    openness=float(profile['big5']['scores_0_100']['openness']),
                    conscientiousness=float(profile['big5']['scores_0_100']['conscientiousness']),
                    extraversion=float(profile['big5']['scores_0_100']['extraversion']),
                    agreeableness=float(profile['big5']['scores_0_100']['agreeableness']),
                    neuroticism=float(profile['big5']['scores_0_100']['neuroticism']),
                    big5_confidence=float(profile.get('big5', {}).get('confidence', 0.0)),
                    
                    line_count_at_analysis=data.get('parse_quality', {}).get('parsed_lines', 0),
                    
                    mbti_prediction=profile['mbti']['type'],
                    mbti_confidence=float(profile.get('mbti', {}).get('confidence', 0.0)),
                    
                    socionics_prediction=profile['socionics']['type'],
                    socionics_confidence=float(profile.get('socionics', {}).get('confidence', 0.0)),
                    
                    summary_text=profile['summary']['one_paragraph'],
                    reasoning_text=json.dumps(profile.get('mbti', {}).get('reasons', [])),
                    full_report_json=data
                )

                db.session.add(new_profile)
                db.session.commit()
                
                flash("결과 파일이 성공적으로 로드되었습니다!", "success")
                return redirect(url_for('view_result'))

            except Exception as e:
                db.session.rollback()
                flash(f"JSON 처리 오류: {str(e)}", "danger")
                return redirect(request.url)

        # 2. 텍스트 파일 업로드 및 분석
        if not target_name:
            flash("분석 대상자 이름을 입력해주세요.", "danger")
            return redirect(request.url)

        if file and file.filename.endswith('.txt'):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(save_path) 

            try:
                # 파싱 실행
                rows, quality = analyzer.parse_target_rows(save_path, target_name)
                
                if not rows:
                    raise ValueError(f"'{target_name}'님과의 대화 내역을 찾을 수 없습니다.")

                # ChatLog 생성
                new_log = ChatLog(
                    user_id=g.user.user_id,
                    file_name=filename,
                    file_path=save_path,
                    target_name=target_name,
                    process_status='PROCESSING'
                )
                db.session.add(new_log)
                db.session.flush()

                # 분석 실행
                signals = analyzer.compute_numeric_signals(rows)
                samples = analyzer.sample_texts_for_llm(rows, 120, 18000)
                
                from openai import OpenAI
                client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                profile = analyzer.call_llm_profile(client, os.environ.get("OPENAI_MODEL"), {
                    "samples": samples, "numeric_signals": signals
                })
                
                # [보장 장치] big5.reasons가 비어있으면 기본 설명 생성
                if not profile.get('big5', {}).get('reasons'):
                    big5_reasons = []
                    big5_data = profile.get('big5', {}).get('scores_0_100', {})
                    trait_names = {
                        'openness': '개방성',
                        'conscientiousness': '성실성',
                        'extraversion': '외향성',
                        'agreeableness': '우호성',
                        'neuroticism': '신경성'
                    }
                    for trait_key, trait_kr in trait_names.items():
                        score = big5_data.get(trait_key, 50)
                        if score >= 70:
                            level = '높음'
                        elif score >= 40:
                            level = '보통'
                        else:
                            level = '낮음'
                        big5_reasons.append(f"{trait_kr}: {level} (점수: {score})")
                    profile['big5']['reasons'] = big5_reasons

                PersonalityResult.query.filter_by(user_id=g.user.user_id).update({'is_representative': False})

                # [FIX] 전체 구조 저장 (meta/llm_profile/parse_quality 포함)
                from dataclasses import asdict
                full_report_data = {
                    "meta": {
                        "speaker_name": target_name,
                        "generated_at_utc": datetime.utcnow().isoformat()
                    },
                    "parse_quality": asdict(quality),
                    "llm_profile": profile
                }

                new_profile = PersonalityResult(
                    user_id=g.user.user_id,
                    log_id=new_log.log_id,
                    openness=float(profile['big5']['scores_0_100']['openness']),
                    conscientiousness=float(profile['big5']['scores_0_100']['conscientiousness']),
                    extraversion=float(profile['big5']['scores_0_100']['extraversion']),
                    agreeableness=float(profile['big5']['scores_0_100']['agreeableness']),
                    neuroticism=float(profile['big5']['scores_0_100']['neuroticism']),
                    big5_confidence=float(profile.get('big5', {}).get('confidence', 0.0)),
                    
                    line_count_at_analysis=quality.parsed_lines,
                    
                    mbti_prediction=profile['mbti']['type'],
                    mbti_confidence=float(profile.get('mbti', {}).get('confidence', 0.0)),
                    
                    socionics_prediction=profile['socionics']['type'],
                    socionics_confidence=float(profile.get('socionics', {}).get('confidence', 0.0)),
                    
                    summary_text=profile['summary']['one_paragraph'],
                    reasoning_text=json.dumps(profile.get('mbti', {}).get('reasons', [])), 
                    full_report_json=full_report_data
                )
                
                new_log.process_status = 'COMPLETED'
                db.session.add(new_profile)
                db.session.commit()
                
                flash("분석이 완료되었습니다!", "success")
                return redirect(url_for('view_result'))

            except Exception as e:
                db.session.rollback()
                flash(f"분석 중 오류 발생: {str(e)}", "danger")
            finally:
                # 안전한 파일 삭제
                try:
                    if os.path.exists(save_path):
                        os.remove(save_path)
                except Exception as cleanup_error:
                    print(f"Warning: 임시 파일 삭제 실패: {cleanup_error}")
                    
    return render_template('upload.html')

# --- 매칭 및 인박스 (Matching & Inbox) ---

@app.route('/matching')
@login_required
def start_matching():
    """매칭 후보 리스트 보기 - 현재 사용자의 최신 분석 결과 기반"""
    try:
        # [FIX] 대표 프로필 우선 조회 -> 없으면 최신순 Fallback
        latest_result = PersonalityResult.query.filter_by(
            user_id=g.user.user_id,
            is_representative=True
        ).first()
        
        if not latest_result:
            latest_result = PersonalityResult.query.filter_by(
                user_id=g.user.user_id
            ).order_by(PersonalityResult.created_at.desc()).first()
        
        if not latest_result:
            flash('분석 결과가 없습니다. 먼저 프로필을 분석해주세요.', 'warning')
            return redirect(url_for('upload_chat'))
        
        # [Robustness Fix] 기존 데이터에 parse_quality가 없는 경우 DB 값으로 복구
        current_profile = latest_result.full_report_json
        if 'parse_quality' not in current_profile:
            current_profile['parse_quality'] = {
                'parsed_lines': latest_result.line_count_at_analysis
            }

        # 현재 사용자의 프로필 JSON 데이터를 matcher에 전달
        candidates = MatchManager.get_matching_candidates(
            my_user_id=g.user.user_id,
            current_user_profile_json=current_profile,
            limit=5
        )
        return render_template('match.html', candidates=candidates)
    except Exception as e:
        print(f"Error in start_matching: {e}")
        import traceback
        traceback.print_exc()
        flash('매칭 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('upload_page'))

@app.route('/inbox')
@login_required
def match_inbox():
    """요청 및 알림함"""
    conn = MatchManager.get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 받은 요청 (Received)
            sql_received = """
                SELECT r.request_id, u.username as sender_name, u.nickname as sender_nickname, r.created_at, r.status
                FROM match_requests r
                JOIN users u ON r.sender_id = u.user_id
                WHERE r.receiver_id = %s AND r.status = 'PENDING'
                ORDER BY r.created_at DESC
            """
            cursor.execute(sql_received, (g.user.user_id,))
            received_requests = cursor.fetchall()

            # 2. 보낸 요청 (Sent)
            sql_sent = """
                SELECT r.request_id, u.username as receiver_name, u.nickname as receiver_nickname, r.created_at, r.status
                FROM match_requests r
                JOIN users u ON r.receiver_id = u.user_id
                WHERE r.sender_id = %s
                ORDER BY r.created_at DESC
            """
            cursor.execute(sql_sent, (g.user.user_id,))
            sent_requests = cursor.fetchall()

            # 3. 시스템 알림 (Alerts)
            alerts = MatchManager.get_unread_notifications(g.user.user_id)
            
            # 4. 읽음 처리
            MatchManager.mark_notifications_as_read(g.user.user_id)

    finally:
        conn.close()

    return render_template('inbox.html', 
                           requests=received_requests, 
                           sent_requests=sent_requests, 
                           alerts=alerts)

@app.route('/apply_match/<receiver_id>', methods=['POST'])
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

# --- 관리자 (Admin) ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():

    
    if request.method == 'POST':
        pw = request.form.get('password')
        # 환경변수 ADMIN_PASSWORD 사용 (기본값: 1234)
        admin_pw = os.environ.get('ADMIN_PASSWORD', '1234')
        if pw == admin_pw:
            session['is_admin'] = True
            flash("관리자 모드로 로그인되었습니다.", "success")
            return redirect(url_for('admin_dashboard'))
        flash("비밀번호가 올바르지 않습니다.", "danger")
    return render_template('admin/login.html')



@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # 1. 사용자 목록은 API로 클라이언트에서 로드 (Alpine.js)
    # 초기 렌더링용으로는 빈 리스트 혹은 기본 데이터만 전달하거나, 
    # 아예 템플릿에서 비동기로 로딩하도록 변경.
    
    # 2. 통계 데이터 계산
    from sqlalchemy import func
    
    # 2-1. 기본 카운트
    stats = {
        'total_users': User.query.count(), # 검색 결과와 무관하게 전체 수 표시
        'total_requests': MatchRequest.query.count(),
        'total_results': PersonalityResult.query.count(),
        'candidate_files': 0
    }
    
    # 2-2. MBTI 분포
    mbti_dist = db.session.query(
        PersonalityResult.mbti_prediction, func.count(PersonalityResult.result_id)
    ).filter(PersonalityResult.is_representative == True).group_by(PersonalityResult.mbti_prediction).all()
    
    # Chart.js용 데이터 포맷팅
    stats['mbti_labels'] = [m[0] for m in mbti_dist if m[0]]
    stats['mbti_counts'] = [m[1] for m in mbti_dist if m[0]]

    # 2-3. 후보군 파일 목록
    candidates_dir = os.path.join(os.path.dirname(__file__), 'candidates_db')
    candidate_files = []
    if os.path.exists(candidates_dir):
        candidate_files = sorted([f for f in os.listdir(candidates_dir) if f.endswith('.json')])
        stats['candidate_files'] = len(candidate_files)
        
    # [NEW] 3. 매칭 로그 조회 (최신 100건)
    Sender = aliased(User)
    Receiver = aliased(User)
    
    match_logs = db.session.query(
        MatchRequest, Sender, Receiver
    ).join(
        Sender, MatchRequest.sender_id == Sender.user_id
    ).join(
        Receiver, MatchRequest.receiver_id == Receiver.user_id
    ).order_by(MatchRequest.created_at.desc()).limit(100).all()
    
    return render_template('admin/dashboard.html', 
                           stats=stats, 
                           candidate_files=candidate_files,
                           match_logs=match_logs)

@app.route('/admin/api/users', methods=['GET'])
@admin_required
def admin_api_users():
    """사용자 목록 검색 API (JSON)"""
    query = request.args.get('q', '').strip()
    
    if query:
        # Numeric ID search support
        from sqlalchemy import cast, String
        users = User.query.filter(
            (User.username.ilike(f'%{query}%')) | 
            (User.nickname.ilike(f'%{query}%')) |
            (User.email.ilike(f'%{query}%')) |
            (cast(User.user_id, String).ilike(f'%{query}%'))
        ).order_by(User.created_at.desc()).all()
    else:
        users = User.query.order_by(User.created_at.desc()).all()
        
    users_data = []
    for u in users:
        users_data.append({
            'user_id': u.user_id,
            'username': u.username,
            'nickname': u.nickname or u.username,
            'email': u.email,
            'created_at': u.created_at.strftime('%Y-%m-%d')
        })
        
    return {'success': True, 'users': users_data}

@app.route('/admin/candidates/upload', methods=['POST'])
@admin_required
def admin_upload_candidate():
    if 'file' not in request.files:
        flash('파일이 없습니다.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    file = request.files['file']
    if file.filename == '':
        flash('선택된 파일이 없습니다.', 'danger')
        return redirect(url_for('admin_dashboard'))
        
    if file and file.filename.endswith('.json'):
        try:
            filename = secure_filename(file.filename)
            candidates_dir = os.path.join(os.path.dirname(__file__), 'candidates_db')
            if not os.path.exists(candidates_dir):
                os.makedirs(candidates_dir)
                
            file.save(os.path.join(candidates_dir, filename))
            flash(f'파일 {filename} 업로드 성공!', 'success')
        except Exception as e:
            flash(f'업로드 실패: {str(e)}', 'danger')
    else:
        flash('JSON 파일만 업로드 가능합니다.', 'danger')
        
    return redirect(url_for('admin_dashboard', tab='system'))

@app.route('/admin/candidates/delete/<filename>', methods=['POST'])
@admin_required
def admin_delete_candidate(filename):
    """후보군 파일 삭제"""
    filename = secure_filename(filename)
    file_path = os.path.join(os.path.dirname(__file__), 'candidates_db', filename)
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            flash(f"파일 '{filename}' 삭제 완료.", "success")
        except Exception as e:
            flash(f"파일 삭제 실패: {str(e)}", "danger")
    else:
        flash("파일을 찾을 수 없습니다.", "warning")
        
    return redirect(url_for('admin_dashboard', tab='system'))

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    try:
        username = user.nickname or user.username
        # 연관된 데이터는 CASCADE 설정에 의해 자동 삭제됨 (모델 정의 확인 필요)
        # User 모델 정의 시 cascade 옵션이 없으면 에러 날 수 있음. 
        # ChatLog, PersonalityResult 등 ForeignKey에 ondelete='CASCADE'가 있는지 확인.
        # app.py 모델 정의를 보면 ondelete='CASCADE'가 설정되어 있음.
        
        db.session.delete(user)
        db.session.commit()
        flash(f"사용자 '{username}' (ID: {user_id}) 삭제 완료.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"삭제 실패: {str(e)}", "danger")
    return redirect(url_for('admin_dashboard', tab='users'))

@app.route('/admin/candidates/refresh', methods=['POST'])
@admin_required
def admin_refresh_candidates():
    try:
        # MatchManager에 reload_candidates 메서드가 필요함
        count = MatchManager.reload_candidates()
        flash(f"후보군 {count}명 데이터 새로고침 완료.", "success")
    except Exception as e:
        flash(f"새로고침 실패: {str(e)}", "danger")
    return redirect(url_for('admin_dashboard', tab='system'))

@app.route('/admin/api/simulate', methods=['POST'])
@admin_required
def admin_simulate_match():
    try:
        data = request.get_json()
        sender_id = int(data.get('sender_id'))
        receiver_id = int(data.get('receiver_id'))
        weights = {
            'similarity': float(data.get('w_sim', 0.5)),
            'chemistry': float(data.get('w_chem', 0.4)),
            'activity': float(data.get('w_act', 0.1))
        }

        # 1. Fetch Profiles
        def get_profile(uid):
            res = PersonalityResult.query.filter_by(user_id=uid, is_representative=True).first()
            if not res: # fallback to latest
                 res = PersonalityResult.query.filter_by(user_id=uid).order_by(PersonalityResult.created_at.desc()).first()
            return res.full_report_json if res and res.full_report_json else None

        sender_profile = get_profile(sender_id)
        receiver_profile = get_profile(receiver_id)

        if not sender_profile or not receiver_profile:
            return {"success": False, "message": "해당 사용자의 분석 프로필을 찾을 수 없습니다."}, 404

        # 2. Prepare Candidate Structure
        candidates = [{
            'user_id': receiver_id,
            'full_report_json': receiver_profile,
            'match_score': 0
        }]
        
        # 3. Calculate
        # 실제 매칭 로직 호출 (가중치 전달)
        results = MatchManager._calculate_match_scores(
            my_user_id=sender_id,
            candidates=candidates,
            current_user_profile_json=sender_profile,
            weights=weights
        )
        
        if not results:
             return {"success": False, "message": "매칭 계산 실패"}, 500

        result = results[0]
        return {
            "success": True,
            "match_score": result.get('match_score'),
            "details": result.get('match_details'),
            "relative_traits": result.get('relative_traits')
        }

    except Exception as e:
        print(f"Simulation Error: {e}")
        return {"success": False, "message": str(e)}, 500

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    flash("관리자 로그아웃 되었습니다.", "info")
    return redirect(url_for('home'))

if __name__ == '__main__':
    import sys


    with app.app_context():
        db.create_all() 
    app.run(host=config_class.RUN_HOST, port=config_class.RUN_PORT)
