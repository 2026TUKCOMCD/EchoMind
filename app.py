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
import sqlalchemy
from sqlalchemy import text
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
from sqlalchemy.orm import aliased
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import logging
from logging.handlers import RotatingFileHandler

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

# --- Logging Mode Setting ---
# 1: DEBUG, 2: INFO, 3: WARNING, 4: ERROR, 5: CRITICAL
LOG_LEVEL_MAP = {
    1: logging.DEBUG,
    2: logging.INFO,
    3: logging.WARNING,
    4: logging.ERROR,
    5: logging.CRITICAL
}
CURRENT_LOG_MODE = 2  # [설정] 1: DEBUG, 2: INFO ... (터미널에는 INFO 표시)
target_log_level = LOG_LEVEL_MAP.get(CURRENT_LOG_MODE, logging.INFO)

# Logging Configuration
if not app.debug:
    # Production: File logging
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/echomind.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(target_log_level)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(target_log_level)
    app.logger.info('EchoMind startup')
else:
    # Development: Console(INFO) + File(ERROR) for debugging
    
    # 1. File Handler (ERROR only)
    file_handler = logging.FileHandler("debug.log", mode='a', encoding='utf-8')
    file_handler.setLevel(logging.ERROR) # 파일에는 에러만 기록
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(filename)s:%(lineno)d]'
    ))
    
    # 2. Stream Handler (INFO)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO) # 터미널에는 INFO(접속 주소 등) 출력
    stream_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(filename)s:%(lineno)d]'
    ))

    # 3. Apply Config
    logging.basicConfig(
        level=logging.INFO, # Root Logger는 INFO까지 허용
        handlers=[file_handler, stream_handler],
        force=True
    )
    
    # [FIX] 라이브러리 로거 레벨 조정
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING) # SQL 로그는 너무 많으므로 WARNING 권장
    
    app.logger.setLevel(logging.INFO)

# 업로드 폴더 자동 생성
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER']) 

# SQLAlchemy 인스턴스를 extensions에서 임포트 (순환 참조 방지)
from extensions import db, User, ChatLog, PersonalityResult, MatchRequest, Notification
db.init_app(app)

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

def dummy_simulation_required(f):
    """
    더미 시뮬레이션 기능이 활성화된 환경에서만 동작하도록 하는 데코레이터.
    config.py의 ENABLE_DUMMY_SIMULATION 플래그로 제어됩니다.
    
    사용법:
      @app.route('/admin/api/dummy/...')
      @admin_required
      @dummy_simulation_required
      def some_dummy_api():
          ...
    
    EC2 배포 시:
      - FLASK_ENV=production으로 설정하면 자동 비활성화
      - .env에 ENABLE_DUMMY_SIMULATION=true로 오버라이드 가능
    """
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not app.config.get('ENABLE_DUMMY_SIMULATION', False):
            return jsonify({
                'success': False, 
                'message': '이 환경에서는 더미 시뮬레이션이 비활성화되어 있습니다. (ENABLE_DUMMY_SIMULATION=false)'
            }), 403
        return f(*args, **kwargs)
    return decorated_function

# -------------------------------------------------------------------
# DB Schema Update Utility
# -------------------------------------------------------------------
def check_and_update_db_schema():
    """
    Checks if 'is_banned' column exists in 'users' table.
    If not, adds it dynamically.
    """
    with app.app_context():
        try:
            inspector = sqlalchemy.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('users')]
            if 'is_banned' not in columns:
                print("Adding 'is_banned' column to users table...")
                with db.engine.connect() as conn:
                    conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                print("'is_banned' column added successfully.")
        except Exception as e:
            print(f"Schema update failed: {e}")

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

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
            # 밴 체크
            if user.is_banned:
                flash('계정이 정지되었습니다. 관리자에게 문의하세요.', 'danger')
                return redirect(url_for('suspended'))
            
            session['user_id'] = user.user_id
            session['username'] = user.username
            session['is_admin'] = (user.email == 'admin@echomind.com') # 간단한 어드민 체크
            return redirect(url_for('home'))
        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("로그아웃 되었습니다.", "info")
    return redirect(url_for('login'))

@app.route('/suspended')
def suspended():
    return render_template('suspended.html')

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
    print(f"[DEBUG] Entered start_matching route for user {g.user.user_id}", flush=True)
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
            limit=30
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
    """요청 및 알림함 - SQLAlchemy ORM 버전"""
    
    # 1. 받은 요청 (Received) - Sender의 성향 정보 및 리포트 포함
    received_query = db.session.query(
        MatchRequest, User, PersonalityResult
    ).join(
        User, MatchRequest.sender_id == User.user_id
    ).outerjoin(
        PersonalityResult, 
        (User.user_id == PersonalityResult.user_id) & (PersonalityResult.is_representative == True)
    ).filter(
        MatchRequest.receiver_id == g.user.user_id,
        MatchRequest.status == 'PENDING'
    ).order_by(MatchRequest.created_at.desc()).all()
    
    # 결과를 dict 형태로 변환 (템플릿 호환성 유지)
    received_requests = []
    for req, sender, profile in received_query:
        req_dict = {
            'request_id': req.request_id,
            'sender_id': sender.user_id,
            'sender_name': sender.username,
            'sender_nickname': sender.nickname,
            'created_at': req.created_at,
            'status': req.status,
            'sender_mbti': profile.mbti_prediction if profile else None,
            'sender_summary': '',
            'full_report_json': {},
            'user_id': sender.user_id  # _calculate_match_scores 호환용
        }
        
        # 프로필 데이터 처리
        if profile:
            # summary_text 처리
            raw_summary = profile.summary_text
            if raw_summary:
                try:
                    summary_data = json.loads(raw_summary) if isinstance(raw_summary, str) else raw_summary
                    if isinstance(summary_data, dict):
                        req_dict['sender_summary'] = summary_data.get('one_paragraph', '')
                    else:
                        req_dict['sender_summary'] = str(summary_data)
                except (ValueError, json.JSONDecodeError):
                    req_dict['sender_summary'] = raw_summary
            
            # full_report_json 처리
            raw_report = profile.full_report_json
            if raw_report:
                try:
                    req_dict['full_report_json'] = json.loads(raw_report) if isinstance(raw_report, str) else raw_report
                except:
                    req_dict['full_report_json'] = raw_report if raw_report else {}
        
        received_requests.append(req_dict)
    
    # 2. 현재 사용자의 대표 프로필 (매칭 점수 계산용)
    my_profile = PersonalityResult.query.filter_by(
        user_id=g.user.user_id, 
        is_representative=True
    ).first()
    
    current_profile = None
    if my_profile and my_profile.full_report_json:
        raw = my_profile.full_report_json
        try:
            current_profile = json.loads(raw) if isinstance(raw, str) else raw
        except:
            current_profile = raw
    
    # 매칭 점수 일괄 계산
    if received_requests and current_profile:
        received_requests = MatchManager._calculate_match_scores(
            my_user_id=g.user.user_id,
            candidates=received_requests,
            current_user_profile_json=current_profile
        )
    
    # 3. 보낸 신청 현황 (Sent) - PENDING 상태만
    sent_query = db.session.query(
        MatchRequest, User
    ).join(
        User, MatchRequest.receiver_id == User.user_id
    ).filter(
        MatchRequest.sender_id == g.user.user_id,
        MatchRequest.status == 'PENDING'
    ).order_by(MatchRequest.created_at.desc()).all()
    
    sent_requests = []
    for req, receiver in sent_query:
        sent_requests.append({
            'request_id': req.request_id,
            'receiver_name': receiver.username,
            'receiver_nickname': receiver.nickname,
            'created_at': req.created_at,
            'status': req.status
        })
    
    # 4. 성사된 매칭 목록
    successful_matches = MatchManager.get_successful_matches(g.user.user_id)
    
    # 5. 시스템 알림
    alerts = MatchManager.get_unread_notifications(g.user.user_id)
    
    # 6. 읽음 처리
    MatchManager.mark_notifications_as_read(g.user.user_id)

    return render_template('inbox.html', 
                           requests=received_requests, 
                           sent_requests=sent_requests, 
                           matches=successful_matches, 
                           alerts=alerts)

@app.route('/match/detail/<int:request_id>')
@login_required
def match_detail(request_id):
    """매칭 상세 정보 및 상대방 프로필 보기 (통합 뷰) - SQLAlchemy ORM 버전"""
    try:
        # aliased imports for self-join
        Sender = aliased(User)
        Receiver = aliased(User)
        SenderProfile = aliased(PersonalityResult)
        ReceiverProfile = aliased(PersonalityResult)
        
        # 1. 매칭 요청 정보 조회 (양쪽 유저 + 프로필 JOIN)
        result = db.session.query(
            MatchRequest, Sender, Receiver, SenderProfile, ReceiverProfile
        ).join(
            Sender, MatchRequest.sender_id == Sender.user_id
        ).join(
            Receiver, MatchRequest.receiver_id == Receiver.user_id
        ).outerjoin(
            SenderProfile, 
            (Sender.user_id == SenderProfile.user_id) & (SenderProfile.is_representative == True)
        ).outerjoin(
            ReceiverProfile, 
            (Receiver.user_id == ReceiverProfile.user_id) & (ReceiverProfile.is_representative == True)
        ).filter(
            MatchRequest.request_id == request_id
        ).first()
        
        if not result:
            flash("존재하지 않는 매칭 요청입니다.", "danger")
            return redirect(url_for('match_inbox'))
        
        req, sender, receiver, sender_profile, receiver_profile = result
        
        # 2. 권한 체크
        current_uid = g.user.user_id
        if current_uid != sender.user_id and current_uid != receiver.user_id:
            flash("조회 권한이 없습니다.", "danger")
            return redirect(url_for('match_inbox'))
        
        # 3. 역할 구분
        is_sender = (current_uid == sender.user_id)
        counterpart_nickname = receiver.nickname if is_sender else sender.nickname
        
        # 4. 프로필 데이터 준비 (JSON 파싱)
        def parse_profile(profile_obj):
            if not profile_obj or not profile_obj.full_report_json:
                return None
            raw = profile_obj.full_report_json
            try:
                return json.loads(raw) if isinstance(raw, str) else raw
            except:
                return raw
        
        my_profile = parse_profile(sender_profile if is_sender else receiver_profile)
        target_profile = parse_profile(receiver_profile if is_sender else sender_profile)
        
        # 5. 매칭 점수 재계산 (상세 데이터 확보용)
        target_candidate = {
            'user_id': receiver.user_id if is_sender else sender.user_id,
            'full_report_json': target_profile,
            'nickname': counterpart_nickname
        }
        
        calculated_list = MatchManager._calculate_match_scores(
            my_user_id=current_uid,
            candidates=[target_candidate],
            current_user_profile_json=my_profile
        )
        
        match_data = calculated_list[0]
        match_score = match_data.get('match_score', 0)
        match_details = match_data.get('match_details', {})
        
        # 6. 상대방 리포트 HTML 생성
        report_html = ""
        if target_profile:
            report_html = visualize_profile.generate_report_html(target_profile, return_body_only=True)
        else:
            report_html = "<div class='p-10 text-center text-slate-400'>상대방의 상세 프로필 데이터가 없습니다.</div>"
        
        # 7. 템플릿 전달 데이터 구성
        request_info = {
            'request_id': req.request_id,
            'status': req.status,
            'created_at': req.created_at,
            'counterpart_nickname': counterpart_nickname,
            'match_score': match_score
        }
        
        return render_template('match_detail.html',
                               request_info=request_info,
                               match_details=match_details,
                               report_html=report_html,
                               is_sender=is_sender)
        
    except Exception as e:
        app.logger.error(f"Error in match_detail: {e}")
        flash("상세 정보를 불러오는 중 오류가 발생했습니다.", "danger")
        return redirect(url_for('match_inbox'))

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

@app.route('/unmatch/request/<int:request_id>', methods=['POST'])
@login_required
def request_unmatch(request_id):
    result = MatchManager.request_unmatch(g.user.user_id, request_id)
    flash(result['message'], 'success' if result['success'] else 'danger')
    return redirect(url_for('match_inbox'))

@app.route('/cancel_match_request/<int:request_id>', methods=['POST'])
@login_required
def cancel_match_request_route(request_id):
    result = MatchManager.cancel_match_request(g.user.user_id, request_id)
    flash(result['message'], 'success' if result['success'] else 'danger')
    return redirect(url_for('match_inbox'))

@app.route('/unmatch/respond/<int:request_id>/<action>')
@login_required
def respond_unmatch(request_id, action):
    result = MatchManager.respond_unmatch(request_id, action.upper())
    flash(result['message'], 'success' if result['success'] else 'danger')
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

    # 2-2-1. MBTI 차원별 통계
    mbti_e_i = {'E': 0, 'I': 0}
    mbti_s_n = {'S': 0, 'N': 0}
    mbti_t_f = {'T': 0, 'F': 0}
    mbti_p_j = {'P': 0, 'J': 0}
    
    representative_results = PersonalityResult.query.filter_by(is_representative=True).all()
    for result in representative_results:
        if result.mbti_prediction and len(result.mbti_prediction) == 4:
            mbti_e_i[result.mbti_prediction[0]] = mbti_e_i.get(result.mbti_prediction[0], 0) + 1
            mbti_s_n[result.mbti_prediction[1]] = mbti_s_n.get(result.mbti_prediction[1], 0) + 1
            mbti_t_f[result.mbti_prediction[2]] = mbti_t_f.get(result.mbti_prediction[2], 0) + 1
            mbti_p_j[result.mbti_prediction[3]] = mbti_p_j.get(result.mbti_prediction[3], 0) + 1
    
    stats['mbti_ei'] = mbti_e_i
    stats['mbti_sn'] = mbti_s_n
    stats['mbti_tf'] = mbti_t_f
    stats['mbti_pj'] = mbti_p_j
    
    # 2-2-2. 소시오닉스 분포
    socionics_dist = db.session.query(
        PersonalityResult.socionics_prediction, func.count(PersonalityResult.result_id)
    ).filter(PersonalityResult.is_representative == True).group_by(PersonalityResult.socionics_prediction).all()
    
    stats['socionics_labels'] = [s[0] for s in socionics_dist if s[0]]
    stats['socionics_counts'] = [s[1] for s in socionics_dist if s[0]]
    
    # 소시오닉스 차원별 (MBTI와 동일한 구조)
    soc_e_i = {'E': 0, 'I': 0}
    soc_s_n = {'S': 0, 'N': 0}
    soc_t_f = {'T': 0, 'F': 0}
    soc_p_j = {'P': 0, 'J': 0}
    
    for result in representative_results:
        if result.socionics_prediction and len(result.socionics_prediction) >= 3:
            # 소시오닉스는 ILE, SEI 등 3글자 형태
            # 첫 글자가 I 또는 E
            first = result.socionics_prediction[0]
            if first in ['I', 'E']:
                soc_e_i[first] = soc_e_i.get(first, 0) + 1
            # 나머지는 MBTI 매핑 필요 (간단히 MBTI와 동일하게 처리)
            if result.mbti_prediction and len(result.mbti_prediction) == 4:
                soc_s_n[result.mbti_prediction[1]] = soc_s_n.get(result.mbti_prediction[1], 0) + 1
                soc_t_f[result.mbti_prediction[2]] = soc_t_f.get(result.mbti_prediction[2], 0) + 1
                soc_p_j[result.mbti_prediction[3]] = soc_p_j.get(result.mbti_prediction[3], 0) + 1
    
    stats['socionics_ei'] = soc_e_i
    stats['socionics_sn'] = soc_s_n
    stats['socionics_tf'] = soc_t_f
    stats['socionics_pj'] = soc_p_j
    
    # 2-2-3. Big5 평균 점수
    if representative_results:
        avg_openness = sum(r.openness for r in representative_results if r.openness) / len(representative_results)
        avg_conscientiousness = sum(r.conscientiousness for r in representative_results if r.conscientiousness) / len(representative_results)
        avg_extraversion = sum(r.extraversion for r in representative_results if r.extraversion) / len(representative_results)
        avg_agreeableness = sum(r.agreeableness for r in representative_results if r.agreeableness) / len(representative_results)
        avg_neuroticism = sum(r.neuroticism for r in representative_results if r.neuroticism) / len(representative_results)
    else:
        avg_openness = avg_conscientiousness = avg_extraversion = avg_agreeableness = avg_neuroticism = 0
    
    stats['big5_labels'] = ['Openness', 'Conscientiousness', 'Extraversion', 'Agreeableness', 'Neuroticism']
    stats['big5_scores'] = [avg_openness, avg_conscientiousness, avg_extraversion, avg_agreeableness, avg_neuroticism]

    # 2-3. 후보군 파일 목록 (with metadata)
    candidates_dir = os.path.join(os.path.dirname(__file__), 'candidates_db')
    candidate_files = []
    if os.path.exists(candidates_dir):
        raw_files = sorted([f for f in os.listdir(candidates_dir) if f.endswith('.json')])
        for filename in raw_files:
            filepath = os.path.join(candidates_dir, filename)
            file_info = {'filename': filename, 'speaker_name': '', 'mbti': ''}
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        file_info['speaker_name'] = data.get('meta', {}).get('speaker_name', '')
                        file_info['mbti'] = data.get('llm_profile', {}).get('mbti', {}).get('type', '')
            except:
                pass
            candidate_files.append(file_info)
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
    
    # Chart.js용 데이터 구조화 (Frontend Jinja2 문법 오류 방지용)
    chart_data = {
        'mbti': {
            'full': {'labels': [m[0] for m in mbti_dist if m[0]], 'data': [m[1] for m in mbti_dist if m[0]]},
            'ei': {'labels': list(mbti_e_i.keys()), 'data': list(mbti_e_i.values())},
            'sn': {'labels': list(mbti_s_n.keys()), 'data': list(mbti_s_n.values())},
            'tf': {'labels': list(mbti_t_f.keys()), 'data': list(mbti_t_f.values())},
            'pj': {'labels': list(mbti_p_j.keys()), 'data': list(mbti_p_j.values())}
        },
        'socionics': {
            'full': {'labels': [s[0] for s in socionics_dist if s[0]], 'data': [s[1] for s in socionics_dist if s[0]]},
            'ei': {'labels': list(soc_e_i.keys()), 'data': list(soc_e_i.values())},
            'sn': {'labels': list(soc_s_n.keys()), 'data': list(soc_s_n.values())},
            'tf': {'labels': list(soc_t_f.keys()), 'data': list(soc_t_f.values())},
            'pj': {'labels': list(soc_p_j.keys()), 'data': list(soc_p_j.values())}
        },
        'big5': {
            'labels': ['개방성', '성실성', '외향성', '우호성', '신경성'],
            'data': [avg_openness, avg_conscientiousness, avg_extraversion, avg_agreeableness, avg_neuroticism]
        }
    }
    
    return render_template('admin/dashboard.html', 
                           stats=stats, 
                           chart_data=chart_data,
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
            'created_at': u.created_at.strftime('%Y-%m-%d'),
            'is_banned': u.is_banned
        })
        
    return {'success': True, 'users': users_data}

@app.route('/admin/users/<int:user_id>/toggle_ban', methods=['POST'])
@admin_required
def admin_toggle_ban(user_id):
    """[관리자] 사용자 계정 정지/해제 토글"""
    user = User.query.get_or_404(user_id)
    
    # 관리자 자신은 정지 불가 (안전장치)
    if user.user_id == session.get('user_id'):
        return {'success': False, 'message': '자기 자신을 정지할 수 없습니다.'}, 400

    user.is_banned = not user.is_banned
    db.session.commit()
    
    status_msg = "정지되었습니다." if user.is_banned else "정지가 해제되었습니다."
    return {'success': True, 'message': f"사용자 {user.nickname}님이 {status_msg}", 'is_banned': user.is_banned}

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

@app.route('/admin/candidates/view/<filename>', methods=['GET'])
@admin_required
def admin_view_candidate(filename):
    """[관리자] 후보군 파일 내용 조회 (JSON)"""
    # 보안: 파일명에 경로 조작 문자 포함 여부 확인
    filename = secure_filename(filename)
    candidates_dir = os.path.join(os.path.dirname(__file__), 'candidates_db')
    file_path = os.path.join(candidates_dir, filename)
    
    if not os.path.exists(file_path):
        return {'success': False, 'message': '파일을 찾을 수 없습니다.'}, 404
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        return {'success': True, 'filename': filename, 'content': content}
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500

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
        try:
            sender_id = int(data.get('sender_id'))
            receiver_id = int(data.get('receiver_id'))
        except (ValueError, TypeError):
             return jsonify({"success": False, "message": "잘못된 사용자 ID 형식입니다. 존재하는 사용자 ID(숫자)를 입력해주세요."}), 400
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
            return jsonify({"success": False, "message": "해당 사용자의 분석 프로필을 찾을 수 없습니다."}), 404

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
             return jsonify({"success": False, "message": "매칭 계산 실패"}), 500

        result = results[0]
        return jsonify({
            "success": True,
            "match_score": result.get('match_score'),
            "details": result.get('match_details'),
            "relative_traits": result.get('relative_traits')
        })

    except Exception as e:
        app.logger.error(f"Simulation Error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/admin/match/delete/<int:request_id>', methods=['POST'])
@admin_required
def admin_delete_match(request_id):
    """[관리자] 매칭 요청 삭제 (Hard Delete)"""
    result = MatchManager.delete_match_by_admin(request_id)
    flash(result['message'], 'success' if result['success'] else 'danger')
    return redirect(url_for('admin_dashboard', tab='logs'))

@app.route('/admin/logout')
def admin_logout():
    # 기존 메시지 클리어 (중복 표시 방지)
    session.pop('_flashes', None)
    
    session.pop('is_admin', None)
    flash("관리자 로그아웃 되었습니다.", "info")
    return redirect(url_for('home'))

# --- 더미 사용자 시뮬레이션 (Dummy User Simulation) ---

# 유효한 MBTI 유형 목록
VALID_MBTI_TYPES = [
    'INTJ', 'INTP', 'ENTJ', 'ENTP',
    'INFJ', 'INFP', 'ENFJ', 'ENFP',
    'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
    'ISTP', 'ISFP', 'ESTP', 'ESFP'
]

# 유효한 소시오닉스 유형 목록
VALID_SOCIONICS_TYPES = [
    'ILE', 'SEI', 'ESE', 'LII',
    'EIE', 'LSI', 'SLE', 'IEI',
    'SEE', 'ILI', 'LIE', 'ESI',
    'LSE', 'EII', 'IEE', 'SLI'
]

# 더미 사용자 파일 경로
DUMMY_STORAGE_DIR = os.path.join(os.path.dirname(__file__), 'candidates_db', 'dummy_storage')
if not os.path.exists(DUMMY_STORAGE_DIR):
    os.makedirs(DUMMY_STORAGE_DIR)
DUMMY_USERS_FILE = os.path.join(DUMMY_STORAGE_DIR, 'dummy_users.json')

def load_dummy_users():
    """더미 사용자 목록 파일 로드"""
    if not os.path.exists(DUMMY_USERS_FILE):
        return []
    try:
        with open(DUMMY_USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        app.logger.warning(f"더미 파일 로드 실패, 빈 리스트로 초기화: {e}")
        return []

def save_dummy_users(data):
    """더미 사용자 목록 파일 저장"""
    # candidates_db 폴더 없으면 생성
    os.makedirs(os.path.dirname(DUMMY_USERS_FILE), exist_ok=True)
    with open(DUMMY_USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route('/admin/api/dummy/list', methods=['GET'])
@admin_required
@dummy_simulation_required
def admin_list_dummies():
    """[관리자] 저장된 더미 사용자 목록 조회"""
    dummy_list = load_dummy_users()
    
    result = []
    for dummy in dummy_list:
        meta = dummy.get('meta', {})
        profile = dummy.get('llm_profile', {})
        quality = dummy.get('parse_quality', {})
        
        result.append({
            'dummy_id': meta.get('user_id', ''),
            'name': meta.get('speaker_name', ''),
            'mbti': profile.get('mbti', {}).get('type', ''),
            'socionics': profile.get('socionics', {}).get('type', ''),
            'big5': profile.get('big5', {}).get('scores_0_100', {}),
            'activity': quality.get('parsed_lines', 0),
            'created_at': meta.get('generated_at_utc', '')
        })
    
    return {'success': True, 'dummies': result}

@app.route('/admin/api/dummy/create', methods=['POST'])
@admin_required
@dummy_simulation_required
def admin_create_dummy():
    """[관리자] 더미 사용자 생성"""
    try:
        data = request.get_json()
        
        # 입력값 추출
        name = data.get('name', '').strip()
        mbti = data.get('mbti', '').upper().strip()
        socionics = data.get('socionics', '').upper().strip()
        big5 = data.get('big5', {})
        activity_lines = int(data.get('activity_lines', 500))
        
        # 입력값 검증
        if not name:
            return {'success': False, 'message': '이름을 입력해주세요.'}, 400
        
        if mbti not in VALID_MBTI_TYPES:
            return {'success': False, 'message': f'유효하지 않은 MBTI 유형입니다. 유효값: {VALID_MBTI_TYPES}'}, 400
        
        if socionics not in VALID_SOCIONICS_TYPES:
            return {'success': False, 'message': f'유효하지 않은 소시오닉스 유형입니다. 유효값: {VALID_SOCIONICS_TYPES}'}, 400
        
        # Big5 점수 검증 (0-100 범위)
        big5_keys = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']
        for key in big5_keys:
            score = big5.get(key, 50)
            if not isinstance(score, (int, float)) or score < 0 or score > 100:
                return {'success': False, 'message': f'Big5 {key} 점수는 0-100 사이여야 합니다.'}, 400
        
        # 활동성 검증
        if activity_lines < 0 or activity_lines > 10000:
            return {'success': False, 'message': '활동성(라인 수)은 0-10000 사이여야 합니다.'}, 400
        
        # 고유 ID 생성
        dummy_id = f"dummy_{uuid.uuid4().hex[:8]}"
        
        # JSON 구조 생성 (candidates_db 형식 준수)
        dummy_data = {
            "meta": {
                "source": "dummy_simulation",
                "is_dummy": True,
                "generated_at_utc": datetime.utcnow().isoformat() + "Z",
                "speaker_name": name,
                "user_id": dummy_id
            },
            "parse_quality": {
                "total_lines": activity_lines,
                "parsed_lines": activity_lines,
                "parse_failed_lines": 0,
                "filtered_system_lines": 0,
                "empty_text_lines": 0,
                "pii_masked_hits": 0
            },
            "llm_profile": {
                "summary": {
                    "one_paragraph": f"[더미 데이터] {name} - 시뮬레이션 테스트용으로 생성된 가상 사용자입니다.",
                    "communication_style_bullets": ["시뮬레이션 테스트용 더미 데이터"]
                },
                "mbti": {
                    "type": mbti,
                    "confidence": 1.0,
                    "reasons": ["더미 데이터 - 관리자가 수동 설정"]
                },
                "big5": {
                    "scores_0_100": {
                        "openness": int(big5.get('openness', 50)),
                        "conscientiousness": int(big5.get('conscientiousness', 50)),
                        "extraversion": int(big5.get('extraversion', 50)),
                        "agreeableness": int(big5.get('agreeableness', 50)),
                        "neuroticism": int(big5.get('neuroticism', 50))
                    },
                    "confidence": 1.0,
                    "reasons": ["더미 데이터 - 관리자가 수동 설정"]
                },
                "socionics": {
                    "type": socionics,
                    "confidence": 1.0,
                    "reasons": ["더미 데이터 - 관리자가 수동 설정"]
                },
                "caveats": ["이 데이터는 시뮬레이션 테스트용 더미 데이터입니다."]
            }
        }
        
        # 파일에 저장
        dummy_list = load_dummy_users()
        dummy_list.append(dummy_data)
        save_dummy_users(dummy_list)
        
        return {'success': True, 'dummy_id': dummy_id, 'message': f'더미 사용자 "{name}" 생성 완료'}
    
    except Exception as e:
        app.logger.error(f"더미 생성 오류: {e}")
        return {'success': False, 'message': str(e)}, 500

@app.route('/admin/api/dummy/random', methods=['POST'])
@admin_required
@dummy_simulation_required
def admin_create_random_dummy():
    """[관리자] 랜덤 더미 사용자 생성"""
    import random
    import string
    
    # 랜덤 값 생성
    random_name = "Dummy_" + ''.join(random.choices(string.ascii_uppercase, k=4))
    random_mbti = random.choice(VALID_MBTI_TYPES)
    random_socionics = random.choice(VALID_SOCIONICS_TYPES)
    random_big5 = {
        'openness': random.randint(20, 80),
        'conscientiousness': random.randint(20, 80),
        'extraversion': random.randint(20, 80),
        'agreeableness': random.randint(20, 80),
        'neuroticism': random.randint(20, 80)
    }
    random_activity = random.randint(100, 2000)
    
    # create 로직 재사용을 위해 request context 조작 대신 직접 구현
    dummy_id = f"dummy_{uuid.uuid4().hex[:8]}"
    
    dummy_data = {
        "meta": {
            "source": "dummy_simulation",
            "is_dummy": True,
            "generated_at_utc": datetime.utcnow().isoformat() + "Z",
            "speaker_name": random_name,
            "user_id": dummy_id
        },
        "parse_quality": {
            "total_lines": random_activity,
            "parsed_lines": random_activity,
            "parse_failed_lines": 0,
            "filtered_system_lines": 0,
            "empty_text_lines": 0,
            "pii_masked_hits": 0
        },
        "llm_profile": {
            "summary": {
                "one_paragraph": f"[더미 데이터] {random_name} - 랜덤 생성된 가상 사용자입니다.",
                "communication_style_bullets": ["랜덤 생성된 시뮬레이션 테스트용 더미 데이터"]
            },
            "mbti": {
                "type": random_mbti,
                "confidence": 1.0,
                "reasons": ["더미 데이터 - 랜덤 생성"]
            },
            "big5": {
                "scores_0_100": random_big5,
                "confidence": 1.0,
                "reasons": ["더미 데이터 - 랜덤 생성"]
            },
            "socionics": {
                "type": random_socionics,
                "confidence": 1.0,
                "reasons": ["더미 데이터 - 랜덤 생성"]
            },
            "caveats": ["이 데이터는 시뮬레이션 테스트용 더미 데이터입니다."]
        }
    }
    
    dummy_list = load_dummy_users()
    dummy_list.append(dummy_data)
    save_dummy_users(dummy_list)
    
    return {
        'success': True, 
        'dummy_id': dummy_id, 
        'data': {
            'name': random_name,
            'mbti': random_mbti,
            'socionics': random_socionics,
            'big5': random_big5,
            'activity_lines': random_activity
        },
        'message': f'랜덤 더미 사용자 "{random_name}" 생성 완료'
    }

@app.route('/admin/api/dummy/<dummy_id>', methods=['DELETE'])
@admin_required
@dummy_simulation_required
def admin_delete_dummy(dummy_id):
    """[관리자] 더미 사용자 삭제"""
    dummy_list = load_dummy_users()
    
    # 해당 ID 찾아서 삭제
    new_list = [d for d in dummy_list if d.get('meta', {}).get('user_id') != dummy_id]
    
    if len(new_list) == len(dummy_list):
        return {'success': False, 'message': '해당 더미 사용자를 찾을 수 없습니다.'}, 404
    
    save_dummy_users(new_list)
    return {'success': True, 'message': f'더미 사용자 "{dummy_id}" 삭제 완료'}

@app.route('/admin/api/dummy/simulate', methods=['POST'])
@admin_required
@dummy_simulation_required
def admin_simulate_dummy_match():
    """[관리자] 두 더미 사용자 간 매칭 시뮬레이션
    
    # ========================================================================
    # TODO [미래 변경 대비]
    # ------------------------------------------------------------------------
    # 1. MBTI/소시오닉스가 문자열("INTJ", "LII")에서 수치(0-1 스케일)로 변경되면:
    #    - dummy_a.get('llm_profile', {}).get('mbti', {}).get('type') 접근 방식 수정 필요
    #    - 타입 변환 유틸리티 함수(type_converter.py) 도입 권장
    #
    # 2. 매칭 알고리즘(matcher.py)이 변경되면:
    #    - MatchManager._calculate_match_scores 호출부 수정 필요
    #    - 추상화 레이어(matching_adapter.py) 도입 권장
    #
    # 3. 가중치 파라미터 구조가 변경되면:
    #    - weights dict 키 이름 및 개수 변경 대응 필요
    # ========================================================================
    """
    try:
        data = request.get_json()
        dummy_id_a = data.get('dummy_id_a', '')
        dummy_id_b = data.get('dummy_id_b', '')
        weights = {
            'similarity': float(data.get('w_sim', 0.5)),
            'chemistry': float(data.get('w_chem', 0.4)),
            'activity': float(data.get('w_act', 0.1))
        }
        
        if not dummy_id_a or not dummy_id_b:
            return {'success': False, 'message': '두 더미 사용자 ID를 모두 입력해주세요.'}, 400
        
        if dummy_id_a == dummy_id_b:
            return {'success': False, 'message': '서로 다른 더미 사용자를 선택해주세요.'}, 400
        
        dummy_list = load_dummy_users()
        
        # 두 더미 데이터 찾기
        dummy_a = None
        dummy_b = None
        for d in dummy_list:
            uid = d.get('meta', {}).get('user_id', '')
            if uid == dummy_id_a:
                dummy_a = d
            elif uid == dummy_id_b:
                dummy_b = d
        
        if not dummy_a:
            return {'success': False, 'message': f'더미 사용자 "{dummy_id_a}"를 찾을 수 없습니다.'}, 404
        if not dummy_b:
            return {'success': False, 'message': f'더미 사용자 "{dummy_id_b}"를 찾을 수 없습니다.'}, 404
        
        # MatchManager._calculate_match_scores 활용
        candidates = [{
            'user_id': dummy_id_b,
            'full_report_json': dummy_b,
            'match_score': 0
        }]
        
        results = MatchManager._calculate_match_scores(
            my_user_id=dummy_id_a,
            candidates=candidates,
            current_user_profile_json=dummy_a,
            weights=weights
        )
        
        if not results:
            return {'success': False, 'message': '매칭 계산 실패'}, 500
        
        result = results[0]
        return {
            'success': True,
            'match_score': result.get('match_score'),
            'details': result.get('match_details'),
            'relative_traits': result.get('relative_traits'),
            'dummy_a': {
                'name': dummy_a.get('meta', {}).get('speaker_name', ''),
                'mbti': dummy_a.get('llm_profile', {}).get('mbti', {}).get('type', '')
            },
            'dummy_b': {
                'name': dummy_b.get('meta', {}).get('speaker_name', ''),
                'mbti': dummy_b.get('llm_profile', {}).get('mbti', {}).get('type', '')
            }
        }

    except Exception as e:
        app.logger.error(f"Dummy simulation error: {str(e)}")
        return {'success': False, 'message': str(e)}, 500

@app.route('/admin/api/dummy/hybrid-simulate', methods=['POST'])
@admin_required
@dummy_simulation_required
def admin_hybrid_simulation():
    """[관리자] 더미 사용자 vs 실제 사용자 간 매칭 시뮬레이션"""
    try:
        data = request.get_json()
        dummy_id = data.get('dummy_id')
        user_id = data.get('user_id')
        weights = {
            'similarity': float(data.get('w_sim', 0.5)),
            'chemistry': float(data.get('w_chem', 0.4)),
            'activity': float(data.get('w_act', 0.1))
        }
        
        # 1. 더미 사용자 로드
        dummy_list = load_dummy_users()
        dummy_data = next((d for d in dummy_list if d.get('meta', {}).get('user_id') == dummy_id), None)
        
        if not dummy_data:
            return {'success': False, 'message': '더미 사용자를 찾을 수 없습니다.'}, 404
            
        # 2. 실제 사용자 프로필 로드 (DB에서)
        # 2. 실제 사용자 프로필 로드 (DB에서)
        # SQLAlchemy ORM 사용
        try:
            target_result = PersonalityResult.query.filter_by(
                user_id=user_id, 
                is_representative=True
            ).first()

            if not target_result:
                # 대표 결과가 없으면 최신 결과 조회 (Fallback)
                target_result = PersonalityResult.query.filter_by(user_id=user_id).order_by(PersonalityResult.created_at.desc()).first()

            if not target_result:
                return {'success': False, 'message': f'사용자(ID: {user_id})의 분석 리포트가 없습니다.'}, 404
                
            user_profile_json = target_result.full_report_json
            if isinstance(user_profile_json, str):
                user_profile_json = json.loads(user_profile_json)

        except Exception as e:
            return {'success': False, 'message': f'DB 조회 오류: {str(e)}'}, 500

        # 3. 매칭 점수 계산
        # 실제 사용자를 Target(current_user)으로, 더미를 Candidate로 설정
        
        # 더미 데이터를 candidate 포맷으로 변환
        dummy_candidate = {
            'user_id': dummy_data.get('meta', {}).get('user_id'),
            'username': dummy_data.get('meta', {}).get('speaker_name'),
            'full_report_json': dummy_data, # 전체 JSON 전달
            'match_score': 0
        }
        
        candidates = [dummy_candidate]

        # 계산 실행
        results = MatchManager._calculate_match_scores(
            user_id,
            candidates,
            current_user_profile_json=user_profile_json,
            weights=weights
        )
        
        if len(results) > 0:
            result = results[0]
            return {
                'success': True,
                'match_score': result.get('match_score', 0),
                'details': result.get('match_details', {})
            }
        else:
            return {'success': False, 'message': '매칭 계산에 실패했습니다.'}
            
    except Exception as e:
        app.logger.error(f"Hybrid simulation error: {str(e)}")
        return {'success': False, 'message': str(e)}, 500
    
    except Exception as e:
        app.logger.error(f"더미 시뮬레이션 오류: {e}")
        return {'success': False, 'message': str(e)}, 500

@app.route('/admin/api/dummy/<dummy_id>/register', methods=['POST'])
@admin_required
def admin_register_dummy_as_candidate(dummy_id):
    """[관리자] 더미 데이터를 실제 후보군 파일로 등록"""
    dummy_list = load_dummy_users()
    
    # 해당 더미 찾기
    dummy = None
    for d in dummy_list:
        if d.get('meta', {}).get('user_id') == dummy_id:
            dummy = d
            break
    
    if not dummy:
        return {'success': False, 'message': '해당 더미 사용자를 찾을 수 없습니다.'}, 404
    
    try:
        # 새 파일명 생성
        filename = f"dummy_registered_{dummy_id}.json"
        candidates_dir = os.path.join(os.path.dirname(__file__), 'candidates_db')
        filepath = os.path.join(candidates_dir, filename)
        
        # 이미 존재하는지 확인
        if os.path.exists(filepath):
            return {'success': False, 'message': '이미 등록된 더미 사용자입니다.'}, 400
        
        # 파일로 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(dummy, f, ensure_ascii=False, indent=2)
        
        name = dummy.get('meta', {}).get('speaker_name', dummy_id)
        return {'success': True, 'filename': filename, 'message': f'더미 "{name}"가 후보군으로 등록되었습니다.'}
    
    except Exception as e:
        app.logger.error(f"더미 등록 오류: {e}")
        return {'success': False, 'message': str(e)}, 500



if __name__ == '__main__':
    import sys


    with app.app_context():
        db.create_all() 
        check_and_update_db_schema()
    app.run(host=config_class.RUN_HOST, port=config_class.RUN_PORT)
