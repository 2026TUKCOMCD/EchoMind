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
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
from flask_compress import Compress
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from sqlalchemy.orm import aliased
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import logging
from logging.handlers import RotatingFileHandler
from markupsafe import escape

# [설정 및 커스텀 모듈 임포트]
from config import config_by_name
from match_manager import MatchManager
import main as analyzer
import visualize_profile
from activity_insights import build_activity_summary

app = Flask(__name__)
Compress(app)

# --- 환경 설정 (Environment Setup) ---
env = os.getenv('FLASK_ENV', 'development')
config_class = config_by_name.get(env, config_by_name['default'])
app.config.from_object(config_class)
config_class.init_app(app)

# --- 스케줄러 설정 ---
scheduler = APScheduler()
scheduler.init_app(app)

# --- Logging Mode Setting ---
# 1: DEBUG, 2: INFO, 3: WARNING, 4: ERROR, 5: CRITICAL
LOG_LEVEL_MAP = {
    1: logging.DEBUG,
    2: logging.INFO,
    3: logging.WARNING,
    4: logging.ERROR,
    5: logging.CRITICAL
}

# [설정] 개발자가 편하게 변경할 수 있는 로그 레벨 설정
from utils_system import get_system_config
sys_conf = get_system_config()

CONSOLE_LOG_MODE = 2  # 터미널 출력 레벨 (1: DEBUG, 2: INFO ...)
FILE_LOG_MODE = sys_conf.get('log_level', 4)     # 파일 기록 레벨 (Config에서 로드)

console_level = LOG_LEVEL_MAP.get(CONSOLE_LOG_MODE, logging.INFO)
file_level = LOG_LEVEL_MAP.get(FILE_LOG_MODE, logging.DEBUG)

# Logging Configuration
if not app.debug:
    # Production: File logging
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/echomind.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(file_level)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(min(console_level, file_level)) # 둘 중 더 낮은 레벨을 로거 기본 레벨로 설정
    app.logger.info('EchoMind startup')
else:
    # Development: Console(INFO) + File(ERROR) for debugging

    # 1. File Handler
    file_handler = logging.FileHandler("debug.log", mode='a', encoding='utf-8')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(filename)s:%(lineno)d]'
    ))

    # 2. Stream Handler (Console)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(console_level)
    stream_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(filename)s:%(lineno)d]'
    ))

    # 3. Apply Config
    logging.basicConfig(
        level=min(console_level, file_level), # Root Logger는 둘 중 낮은 레벨 허용
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

# --- Helper Functions ---
def _parse_json_safe(data):
    """
    JSON 문자열을 안전하게 파싱하여 dict로 반환합니다.
    이미 dict/list라면 그대로 반환하고, 파싱 실패 시 원본을 반환하거나 빈 dict를 반환합니다.
    """
    if isinstance(data, str):
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {} # 파싱 실패 시 빈 딕셔너리 안전 반환 (상황에 따라 원본 반환 가능)
    return data if data is not None else {}

# SQLAlchemy 인스턴스를 extensions에서 임포트 (순환 참조 방지)
from extensions import (
    db,
    User,
    ChatLog,
    PersonalityResult,
    MatchRequest, 
    Notification,
    Message,
    GroupChatRoom,
    GroupChatParticipant, 
    GroupChatMessage,
    GroupChatKickVote,
    BlindMatch,
    BlindMatchMessage,
    UserActivityLog
)
from blind_match_manager import BlindMatchManager, BlindMatchStatus

db.init_app(app)
migrate = Migrate(app, db)

# --- Template Filters ---
@app.template_filter('kst')
def kst_filter(dt, format='%Y-%m-%d %H:%M'):
    """UTC 시간을 KST(+9시간)로 변환하여 포맷팅하는 필터"""
    if not dt:
        return '-'
    from datetime import timedelta
    # [FIX] ISO 형식의 문자열이 입력될 경우 datetime 객체로 변환
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return dt # 변환 실패 시 원본 반환
    return (dt + timedelta(hours=9)).strftime(format)

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

# [REMOVED] dummy_simulation_required 데코레이터 삭제됨
# 더미 사용자도 이제 DB에 저장되므로, 환경 변수 플래그로 기능을 제한할 필요가 없음.

# -------------------------------------------------------------------
# DB Schema Update Utility
# -------------------------------------------------------------------
def check_and_update_db_schema():
    """
    DB 스키마 자동 마이그레이션:
    - 'is_banned' 컬럼 추가 (users)
    - 'is_dummy' 컬럼 추가 (users) - 더미 사용자 마이그레이션용
    - 'log_id' nullable 변경 (personality_results) - 더미 사용자용
    """
    with app.app_context():
        try:
            inspector = sqlalchemy.inspect(db.engine)
            user_columns = [col['name'] for col in inspector.get_columns('users')]

            with db.engine.connect() as conn:
                # 1. is_banned 컬럼 추가
                if 'is_banned' not in user_columns:
                    app.logger.info("Adding 'is_banned' column to users table...")
                    conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    app.logger.info("'is_banned' column added successfully.")

                # 2. is_dummy 컬럼 추가 (더미 사용자 지원)
                if 'is_dummy' not in user_columns:
                    app.logger.info("Adding 'is_dummy' column to users table...")
                    conn.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN is_dummy BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    app.logger.info("'is_dummy' column added successfully.")

                # 3. log_id nullable 변경 (ALTER COLUMN은 DB마다 문법이 다름 - MySQL 기준)
                # 이미 nullable이면 무시됨
                try:
                    conn.execute(sqlalchemy.text("""
                        ALTER TABLE personality_results
                        MODIFY COLUMN log_id INT NULL
                    """))
                    conn.commit()
                    app.logger.info("'log_id' column modified to nullable.")
                except Exception as e:
                    # 이미 nullable이거나 다른 DB 엔진인 경우 무시
                    app.logger.warning(f"log_id modification skipped or already nullable: {e}")

                # 4. group_chat_participants 테이블에 last_read_message_id 컬럼 추가
                try:
                    if 'group_chat_participants' in inspector.get_table_names():
                        p_cols = [col['name'] for col in inspector.get_columns('group_chat_participants')]
                        if 'last_read_message_id' not in p_cols:
                            conn.execute(sqlalchemy.text("ALTER TABLE group_chat_participants ADD COLUMN last_read_message_id INT DEFAULT 0"))
                            conn.commit()
                            app.logger.info("'last_read_message_id' column added.")
                except Exception as e:
                    app.logger.warning(f"last_read_message_id migration failed: {e}")

                # 5. group_chat_messages 테이블에 is_system 컬럼 추가
                try:
                    if 'group_chat_messages' in inspector.get_table_names():
                        m_cols = [col['name'] for col in inspector.get_columns('group_chat_messages')]
                        if 'is_system' not in m_cols:
                            conn.execute(sqlalchemy.text("ALTER TABLE group_chat_messages ADD COLUMN is_system BOOLEAN DEFAULT FALSE"))
                            conn.commit()
                            app.logger.info("'is_system' column added.")
                except Exception as e:
                    app.logger.warning(f"is_system migration failed: {e}")

                # 6. group_chat_kick_votes 테이블 추가
                try:
                    if 'group_chat_kick_votes' not in inspector.get_table_names():
                        conn.execute(sqlalchemy.text("""
                            CREATE TABLE group_chat_kick_votes (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                room_id INT NOT NULL,
                                voter_id INT NOT NULL,
                                target_id INT NOT NULL,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (room_id) REFERENCES group_chat_rooms(id) ON DELETE CASCADE,
                                FOREIGN KEY (voter_id) REFERENCES users(user_id) ON DELETE CASCADE,
                                FOREIGN KEY (target_id) REFERENCES users(user_id) ON DELETE CASCADE
                            )
                        """))
                        conn.commit()
                except Exception as e:
                    pass

                # 7. group_chat_rooms 테이블에 room_code 추가 및 마이그레이션
                try:
                    if 'group_chat_rooms' in inspector.get_table_names():
                        r_cols = [col['name'] for col in inspector.get_columns('group_chat_rooms')]
                        if 'room_code' not in r_cols:
                            import random
                            conn.execute(sqlalchemy.text("ALTER TABLE group_chat_rooms ADD COLUMN room_code VARCHAR(20)"))
                            conn.commit()

                            rooms = conn.execute(sqlalchemy.text("SELECT id FROM group_chat_rooms WHERE room_code IS NULL")).fetchall()
                            for r in rooms:
                                new_code = str(random.randint(1000000000, 9999999999))
                                conn.execute(sqlalchemy.text("UPDATE group_chat_rooms SET room_code = :c WHERE id = :id"),
                                             {"c": new_code, "id": r[0]})
                            conn.commit()

                            try:
                                conn.execute(sqlalchemy.text("ALTER TABLE group_chat_rooms MODIFY COLUMN room_code VARCHAR(20) NOT NULL"))
                                conn.execute(sqlalchemy.text("ALTER TABLE group_chat_rooms ADD UNIQUE INDEX idx_room_code (room_code)"))
                                conn.commit()
                            except Exception as e:
                                pass
                except Exception as e:
                    pass

                # 8. match_requests 테이블에 match_code 추가 및 마이그레이션
                try:
                    if 'match_requests' in inspector.get_table_names():
                        m_cols = [col['name'] for col in inspector.get_columns('match_requests')]
                        if 'match_code' not in m_cols:
                            import random
                            conn.execute(sqlalchemy.text("ALTER TABLE match_requests ADD COLUMN match_code VARCHAR(20)"))
                            conn.commit()

                            reqs = conn.execute(sqlalchemy.text("SELECT request_id FROM match_requests WHERE match_code IS NULL")).fetchall()
                            for r in reqs:
                                new_code = str(random.randint(1000000000, 9999999999))
                                conn.execute(sqlalchemy.text("UPDATE match_requests SET match_code = :c WHERE request_id = :id"),
                                             {"c": new_code, "id": r[0]})
                            conn.commit()

                            try:
                                conn.execute(sqlalchemy.text("ALTER TABLE match_requests MODIFY COLUMN match_code VARCHAR(20) NOT NULL"))
                                conn.execute(sqlalchemy.text("ALTER TABLE match_requests ADD UNIQUE INDEX idx_match_code (match_code)"))
                                conn.commit()
                            except Exception as e:
                                pass
                        else:
                            # 칼럼은 있지만 빈 문자열이거나 NULL인 데이터 정리
                            import random
                            bad_rows = conn.execute(sqlalchemy.text(
                                "SELECT request_id FROM match_requests WHERE match_code IS NULL OR match_code = ''"
                            )).fetchall()

                            if bad_rows:
                                app.logger.info(f"Cleaning {len(bad_rows)} invalid match_codes...")
                                for r in bad_rows:
                                    new_code = str(random.randint(1000000000, 9999999999))
                                    conn.execute(sqlalchemy.text(
                                        "UPDATE match_requests SET match_code = :c WHERE request_id = :id"
                                    ), {"c": new_code, "id": r[0]})
                                conn.commit()
                                app.logger.info("match_code cleanup completed.")
                except Exception as e:
                    app.logger.warning(f"match_code migration/cleanup failed: {e}")

                # 9. notifications 테이블에 related_entity 컬럼 추가
                try:
                    if 'notifications' in inspector.get_table_names():
                        n_cols = [col['name'] for col in inspector.get_columns('notifications')]
                        if 'related_entity_type' not in n_cols:
                            conn.execute(sqlalchemy.text("ALTER TABLE notifications ADD COLUMN related_entity_type VARCHAR(50)"))
                            app.logger.info("'related_entity_type' column added to notifications.")
                        if 'related_entity_id' not in n_cols:
                            conn.execute(sqlalchemy.text("ALTER TABLE notifications ADD COLUMN related_entity_id INT"))
                            app.logger.info("'related_entity_id' column added to notifications.")
                        conn.commit()
                except Exception as e:
                    app.logger.warning(f"notifications migration failed: {e}")

                # 10. user_activity_logs 테이블 추가
                try:
                    if 'user_activity_logs' not in inspector.get_table_names():
                        # MySQL/MariaDB 호환 문법 사용
                        conn.execute(sqlalchemy.text("""
                            CREATE TABLE user_activity_logs (
                                id INT NOT NULL AUTO_INCREMENT,
                                user_id INT NOT NULL,
                                activity_type VARCHAR(50) NOT NULL,
                                ip_address VARCHAR(45),
                                user_agent VARCHAR(255),
                                timestamp DATETIME,
                                details TEXT,
                                PRIMARY KEY (id),
                                FOREIGN KEY(user_id) REFERENCES users (user_id) ON DELETE CASCADE
                            )
                        """))
                        conn.commit()
                        app.logger.info("'user_activity_logs' table created.")
                except Exception as e:
                    app.logger.warning(f"user_activity_logs table creation failed: {e}")

        except Exception as e:
            app.logger.error(f"Schema update failed: {e}")

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@app.route('/favicon.ico')
def favicon():
    """브라우저의 자동 파비콘 요청으로 인한 404 에러 로그 방지"""
    return '', 204

@app.before_request
def load_user():
    user_id = session.get('user_id')
    g.user = db.session.get(User, user_id) if user_id else None
    if g.user:
        g.unread_count = len(MatchManager.get_unread_notifications(g.user.user_id))
        g.unread_blind_count = BlindMatchManager.get_unread_blind_count(g.user.user_id)
    else:
        g.unread_count = 0
        g.unread_blind_count = 0

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
            birth_date=datetime.strptime(request.form['birth_date'],
                                         '%Y-%m-%d').date() if request.form.get('birth_date') else None
        )
        try:
            db.session.add(new_user)
            db.session.commit()

            # 비회원 시절 남긴 분석 결과가 있다면 계정 귀속 및 로그 이관
            guest_result_id = session.pop('guest_result_id', None)
            if guest_result_id:
                guest_res = PersonalityResult.query.filter_by(result_id=guest_result_id, user_id=None).first()
                if guest_res:
                    guest_res.user_id = new_user.user_id
                    # 첫 분석이라면 자동으로 대표 결과로 설정
                    guest_res.is_representative = True
                    # 연관된 채팅 로그(ChatLog)도 있다면 함께 이관
                    if guest_res.log_id:
                        guest_log = ChatLog.query.get(guest_res.log_id)
                        if guest_log and guest_log.user_id is None:
                            guest_log.user_id = new_user.user_id
                    db.session.commit()
            flash("회원가입이 완료되었습니다! 로그인해주세요.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Registration error: {e}")
            flash("이미 존재하는 이메일이거나 회원가입 중 오류가 발생했습니다.", "danger")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        
        # Helper to log activity
        def log_activity(user_obj, success):
            if not user_obj:
                return
            try:
                activity = UserActivityLog(
                    user_id=user_obj.user_id,
                    activity_type='LOGIN_SUCCESS' if success else 'LOGIN_FAIL',
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string
                )
                db.session.add(activity)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Failed to log user activity for user {user_obj.user_id}: {e}")

        if user and check_password_hash(user.password_hash, request.form['password']):
            if user.is_banned:
                log_activity(user, False) # Log failed attempt for banned user
                flash('계정이 정지되었습니다. 관리자에게 문의하세요.', 'danger')
                return redirect(url_for('suspended'))

            log_activity(user, True) # Log successful login
            session['user_id'] = user.user_id
            session['username'] = user.username
            session['is_admin'] = (user.email == 'admin@echomind.com')
            
            guest_result_id = session.pop('guest_result_id', None)
            if guest_result_id:
                guest_res = PersonalityResult.query.filter_by(result_id=guest_result_id, user_id=None).first()
                if guest_res:
                    guest_res.user_id = user.user_id
                    has_rep = PersonalityResult.query.filter_by(user_id=user.user_id, is_representative=True).first()
                    if not has_rep:
                        guest_res.is_representative = True
                    if guest_res.log_id:
                        guest_log = ChatLog.query.get(guest_res.log_id)
                        if guest_log and guest_log.user_id is None:
                            guest_log.user_id = user.user_id
                    db.session.commit()
            return redirect(url_for('home'))
        
        if user:
            log_activity(user, False) # Log failed attempt for existing user with wrong password

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
    # unread_count is now handled by @before_request and available in `g`
    return render_template('index.html', user=g.user)

@app.route('/result')
@app.route('/result/<int:result_id>')
def view_result(result_id=None):
    """결과 조회 페이지 (특정 ID 또는 대표 결과)"""
    # [Auth Check] 관리자 또는 로그인 유저만 접근 가능
    is_admin = session.get('is_admin')
    guest_result_id = session.get('guest_result_id')

    if not g.user and not is_admin:
        if guest_result_id and not result_id:
            return redirect(url_for('view_result', result_id=guest_result_id))
        if not (guest_result_id and result_id == guest_result_id):
            flash("로그인이 필요합니다.", "warning")
            return redirect(url_for('login'))

    # [Admin Logic] 관리자는 모든 결과 조회 가능 (단, 본인 조회 의도인 경우 제외)
    if is_admin and (result_id or not g.user):
        if not result_id:
             flash("관리자는 특정 결과 ID를 지정해야 합니다.", "warning")
             return redirect(url_for('admin_dashboard'))

        result = PersonalityResult.query.get(result_id)
        if not result:
            flash("존재하지 않는 결과입니다.", "danger")
            return redirect(url_for('admin_dashboard'))

    # [Guest Logic] 비회원 결과 조회
    elif not getattr(g, 'user', None):
        result = PersonalityResult.query.filter_by(result_id=result_id, user_id=None).first()
        if not result:
            flash("세션이 만료되었거나 접근 권한이 없습니다.", "danger")
            return redirect(url_for('upload_chat'))

    # [User Logic] 본인의 결과만 조회 가능
    else:
        if result_id:
            result = PersonalityResult.query.filter_by(user_id=g.user.user_id, result_id=result_id).first()
        else:
            result = PersonalityResult.query.filter_by(user_id=g.user.user_id, is_representative=True).first()

        if not result:
            flash("분석된 결과가 없습니다. 채팅 로그를 먼저 업로드해주세요.", "info")
            return redirect(url_for('upload_chat'))

    # [Common Rendering]
    try:
        if result.full_report_json:
             # full_report_json 구조 확인
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
            if is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('upload_chat'))
    except Exception as e:
        flash(f"리포트 생성 실패: {str(e)}", "danger")
        if is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('upload_chat'))

@app.route('/history')
@login_required
def history():
    """분석 히스토리 페이지"""
    from datetime import datetime
    from flask import request

    # 1. 쿼리 파라미터 가져오기
    sort_order = request.args.get('sort', 'desc') # 기본값: 최근 순
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # 2. 기본 쿼리 생성
    query = PersonalityResult.query.filter_by(user_id=g.user.user_id)

    # 3. 날짜 필터링 적용
    if start_date:
        try:
            query = query.filter(PersonalityResult.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
        except ValueError:
            pass # 형식 오류 시 무시

    if end_date:
        try:
            # end_date는 해당 일의 23:59:59.999 까지 포함하도록 처리
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(PersonalityResult.created_at <= end_date_obj)
        except ValueError:
            pass

    # 4. 정렬 적용
    if sort_order == 'asc':
        query = query.order_by(PersonalityResult.created_at.asc())
    else:
        query = query.order_by(PersonalityResult.created_at.desc())

    results = query.all()

    # 5. 현재 대표 결과 찾기 (전체 데이터 기준 유지)
    all_user_results = PersonalityResult.query.filter_by(user_id=g.user.user_id).all()
    active_result = next((r for r in all_user_results if r.is_representative), None)

    return render_template('history.html',
                           results=results,
                           active_result=active_result,
                           current_sort=sort_order,
                           current_start=start_date,
                           current_end=end_date)

# --- 유저 액티비티 ---

@app.route('/activity')
@login_required
def user_activity():
    """사용자의 최근 활동 내역을 보여주는 페이지입니다."""
    app.logger.info(f"User {g.user.user_id} is viewing their activity page.")
    
    time_threshold = datetime.utcnow() - timedelta(days=30)
    
    # 1. 로그인 활동 조회
    try:
        login_activities = UserActivityLog.query.filter(
            UserActivityLog.user_id == g.user.user_id,
            UserActivityLog.timestamp >= time_threshold
        ).order_by(UserActivityLog.timestamp.desc()).limit(20).all()
    except Exception as e:
        app.logger.error(f"Failed to fetch login activities for user {g.user.user_id}: {e}")
        login_activities = []
        flash("로그인 기록을 불러오는 데 실패했습니다.", "warning")

    # 2. 프로필 분석 활동 조회
    try:
        analysis_results = PersonalityResult.query.filter(
            PersonalityResult.user_id == g.user.user_id,
            PersonalityResult.created_at >= time_threshold
        ).order_by(PersonalityResult.created_at.desc()).limit(10).all()

        analysis_activities = []
        for result in analysis_results:
            report_json = result.full_report_json or {}
            meta = report_json.get('meta', {})
            analysis_activities.append({
                'result_id': result.result_id,
                'target_name': meta.get('speaker_name', '알 수 없음'),
                'mbti': result.mbti_prediction,
                'timestamp': result.created_at
            })
    except Exception as e:
        app.logger.error(f"Failed to fetch analysis activities for user {g.user.user_id}: {e}")
        analysis_activities = []
        flash("프로필 분석 기록을 불러오는 데 실패했습니다.", "warning")

    # 3. 매칭 활동 통합 조회
    try:
        matching_activities = []
        
        # 보낸 요청, 받은 요청, 상태 변경된 요청을 모두 합쳐서 시간 순으로 정렬
        sent_requests = MatchRequest.query.filter(MatchRequest.sender_id == g.user.user_id, MatchRequest.created_at >= time_threshold).all()
        received_requests = MatchRequest.query.filter(MatchRequest.receiver_id == g.user.user_id, MatchRequest.created_at >= time_threshold).all()
        
        # 활동들을 하나의 리스트로 통합
        all_related_requests = sent_requests + received_requests
        unique_request_ids = {req.request_id for req in all_related_requests}
        final_requests = MatchRequest.query.filter(MatchRequest.request_id.in_(unique_request_ids)).order_by(MatchRequest.updated_at.desc()).all()

        for req in final_requests:
            is_sender = req.sender_id == g.user.user_id
            partner_id = req.receiver_id if is_sender else req.sender_id
            partner = User.query.get(partner_id)
            if not partner: continue

            activity = { 'timestamp': req.updated_at, 'partner_name': partner.nickname or partner.username, 'request_id': req.request_id }

            if req.created_at == req.updated_at: # 생성 이벤트
                activity['timestamp'] = req.created_at
                if is_sender:
                    activity['type'] = 'sent'
                    activity['message'] = f"'{activity['partner_name']}'님에게 매칭을 신청했습니다."
                else:
                    activity['type'] = 'received'
                    activity['message'] = f"'{activity['partner_name']}'님으로부터 매칭 신청을 받았습니다."
            else: # 업데이트 이벤트
                if req.status == 'ACCEPTED':
                    activity['type'] = 'accepted'
                    activity['message'] = f"'{activity['partner_name']}'님과의 매칭이 성사되었습니다."
                elif req.status == 'REJECTED':
                    activity['type'] = 'rejected'
                    activity['message'] = f"'{activity['partner_name']}'님이 요청을 거절했습니다." if is_sender else f"'{activity['partner_name']}'님의 요청을 거절했습니다."
                elif req.status == 'CANCELLED':
                    activity['type'] = 'cancelled'
                    activity['message'] = f"'{activity['partner_name']}'님과의 매칭 신청을 취소했습니다."
            
            matching_activities.append(activity)

        matching_activities.sort(key=lambda x: x['timestamp'], reverse=True)

    except Exception as e:
        app.logger.error(f"Failed to fetch matching activities for user {g.user.user_id}: {e}")
        matching_activities = []
        flash("매칭 활동 기록을 불러오는 데 실패했습니다.", "warning")

    activity_summary = build_activity_summary(
        login_activities=login_activities,
        analysis_activities=analysis_activities,
        matching_activities=matching_activities,
    )

    return render_template(
        'activity.html',
        login_activities=login_activities,
        analysis_activities=analysis_activities,
        matching_activities=matching_activities,
        activity_summary=activity_summary,
    )
    
# --- END OF FEATURE: USER ACTIVITY ---


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
def upload_chat():
    if request.method == 'POST':
        current_user_id = g.user.user_id if getattr(g, 'user', None) else None
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

                # 회원 정보가 있다면 meta에 추가 (업로드된 JSON에 덮어쓰기)
                if g.user:
                    data['meta']['user_id'] = g.user.user_id
                    data['meta']['birth_date'] = g.user.birth_date.strftime('%Y-%m-%d') if g.user.birth_date else None
                    data['meta']['created_at'] = g.user.created_at.isoformat() + "Z" if g.user.created_at else None


                # ChatLog 생성 (Fake Log)
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

                new_log = ChatLog(
                    user_id=current_user_id,
                    file_name=filename,
                    file_path=save_path,
                    target_name=target_name,
                    process_status='COMPLETED'
                )
                db.session.add(new_log)
                db.session.flush()

                # 기존 대표 결과 해제 (회원인 경우만)
                if current_user_id:
                    PersonalityResult.query.filter_by(user_id=current_user_id).update({'is_representative': False})

                # PersonalityResult 저장
                new_profile = PersonalityResult(
                    user_id=current_user_id,
                    log_id=new_log.log_id,
                    is_representative=True if current_user_id else False,

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

                if not current_user_id:
                    session['guest_result_id'] = new_profile.result_id

                flash("결과 파일이 성공적으로 로드되었습니다!", "success")
                return redirect(url_for('view_result', result_id=new_profile.result_id))

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
                    user_id=current_user_id,
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

                if current_user_id:
                    PersonalityResult.query.filter_by(user_id=current_user_id).update({'is_representative': False})

                # 전체 구조 저장 (meta/llm_profile/parse_quality 포함)
                from dataclasses import asdict
                full_report_data = {
                    "meta": {
                        "user_id": current_user_id,
                        "speaker_name": target_name,
                        "generated_at_utc": datetime.utcnow().isoformat() + "Z"
                    },
                    "parse_quality": asdict(quality),
                    "llm_profile": profile
                }

                # 회원 정보가 있다면 meta에 추가
                if g.user:
                    full_report_data['meta']['birth_date'] = g.user.birth_date.strftime('%Y-%m-%d') if g.user.birth_date else None
                    full_report_data['meta']['created_at'] = g.user.created_at.isoformat() + "Z" if g.user.created_at else None
                

                new_profile = PersonalityResult(
                    user_id=current_user_id,
                    log_id=new_log.log_id,
                    is_representative=True if current_user_id else False,
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

                if not current_user_id:
                    session['guest_result_id'] = new_profile.result_id

                flash("분석이 완료되었습니다!", "success")
                return redirect(url_for('view_result', result_id=new_profile.result_id))

            except Exception as e:
                db.session.rollback()
                flash(f"분석 중 오류 발생: {str(e)}", "danger")
            finally:
                # 안전한 파일 삭제
                try:
                    if os.path.exists(save_path):
                        os.remove(save_path)
                except Exception as cleanup_error:
                    app.logger.warning(f"Warning: 임시 파일 삭제 실패: {cleanup_error}")

    return render_template('upload.html')

# --- 매칭 및 인박스 (Matching & Inbox) ---

@app.route('/matching')
@login_required
def start_matching():
    """매칭 후보 리스트 보기 - 현재 사용자의 최신 분석 결과 기반"""
    app.logger.debug(f"[DEBUG] Entered start_matching route for user {g.user.user_id}")
    try:
        # 대표 프로필 우선 조회 -> 없으면 최신순 Fallback
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

        # 기존 데이터에 parse_quality가 없는 경우 DB 값으로 복구
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
        # [진단용 로그] AVD에서 접속 시 후보자 수가 0명인지 확인하기 위함
        app.logger.info(f"[MATCHING_LOG] User {g.user.user_id} found {len(candidates)} candidates.")

        return render_template('match.html', candidates=candidates)
    except Exception as e:
        app.logger.error(f"Error in start_matching: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        flash('매칭 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('upload_chat'))

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
                req_dict['full_report_json'] = _parse_json_safe(raw_report)

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
        except (json.JSONDecodeError, TypeError):
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

    # 각 매칭별 안 읽은 메시지 개수 계산
    for match in successful_matches:
        match['unread_count'] = Message.query.filter_by(
            request_id=match['request_id'],
            sender_id=match['user_id'], # 상대방 ID
            is_read=False
        ).count()

        # 마지막 메시지 조회 (대화 미리보기용)
        last_msg = Message.query.filter_by(request_id=match['request_id'])\
            .order_by(Message.created_at.desc()).first()
        match['last_message'] = last_msg.content if last_msg else "대화를 시작해보세요."

    # 5. 시스템 알림
    alerts = MatchManager.get_unread_notifications(g.user.user_id)

    # 6. 읽음 처리
    MatchManager.mark_notifications_as_read(g.user.user_id)

    return render_template('inbox.html',
                           requests=received_requests,
                           sent_requests=sent_requests,
                           matches=successful_matches,
                           alerts=alerts)

@app.route('/api/inbox/updates')
@login_required
def inbox_updates():
    """인박스 실시간 업데이트를 위한 API (Polling용) - 매칭 상태 변경 감지 포함"""
    user_id = g.user.user_id
    successful_matches = MatchManager.get_successful_matches(user_id)

    updates = []
    for match in successful_matches:
        # 안 읽은 메시지 개수
        unread_count = Message.query.filter_by(
            request_id=match['request_id'],
            sender_id=match['user_id'], # 상대방 ID
            is_read=False
        ).count()

        # 마지막 메시지
        last_msg = Message.query.filter_by(request_id=match['request_id'])\
            .order_by(Message.created_at.desc()).first()
        last_message_content = last_msg.content if last_msg else "대화를 시작해보세요."

        updates.append({
            'request_id': match['request_id'],
            'unread_count': unread_count,
            'last_message': last_message_content
        })

    # 받은 매칭 신청 수 (PENDING만 — COUNT 쿼리로 가볍게)
    received_count = MatchRequest.query.filter_by(
        receiver_id=user_id, status='PENDING'
    ).count()

    # 보낸 신청 상태 (PENDING인 것만 — 상태 변경 감지용)
    sent_pending = MatchRequest.query.filter_by(
        sender_id=user_id, status='PENDING'
    ).all()
    sent_statuses = [{'request_id': r.request_id, 'status': r.status} for r in sent_pending]

    # 성사된 매칭 상태 (취소 요청 감지용)
    match_statuses = [{'request_id': m['request_id'], 'status': m['status']} for m in successful_matches]

    # 읽지 않은 알림 존재 여부
    has_new_alerts = Notification.query.filter_by(
        user_id=user_id, is_read=False
    ).count() > 0

    return jsonify({
        'updates': updates,
        'received_count': received_count,
        'sent_statuses': sent_statuses,
        'match_statuses': match_statuses,
        'has_new_alerts': has_new_alerts
    })

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
            except (json.JSONDecodeError, TypeError):
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

        # Jinja 템플릿의 (match_details.similarity_score) 구문 등호 오류 방지
        if not match_details:
            match_details = {
                'similarity_score': 0.0,
                'chemistry_score': 0.0,
                'activity_score': 0.0
            }

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

        # 8. 차트 및 확장 패널용 부가 데이터 구성
        cand_data = {
            'my_big5': match_data.get('my_big5', [50]*5),
            'cand_big5': match_data.get('cand_big5', [50]*5),
            'my_line_count': match_data.get('my_line_count', 0),
            'cand_line_count': match_data.get('cand_line_count', 0),
            'my_functions': match_data.get('my_functions'),
            'cand_functions': match_data.get('cand_functions'),
            'relative_traits': match_data.get('relative_traits', [])
        }

        return render_template('match_detail.html',
                               request_info=request_info,
                               match_details=match_details,
                               cand_data=cand_data,
                               report_html=report_html,
                               is_sender=is_sender)

    except Exception as e:
        app.logger.error(f"Error in match_detail: {e}")
        flash("상세 정보를 불러오는 중 오류가 발생했습니다.", "danger")
        return redirect(url_for('match_inbox'))


@app.route('/download_match_json/<int:request_id>')
@login_required
def download_match_json(request_id):
    """매칭 상세 정보를 JSON 파일로 다운로드합니다."""
    try:
        # aliased imports for self-join
        Sender = aliased(User)
        Receiver = aliased(User)
        SenderProfile = aliased(PersonalityResult)
        ReceiverProfile = aliased(PersonalityResult)

        # 1. 매칭 요청 정보 조회 (match_detail과 동일한 쿼리)
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

        # 3. 역할 구분 및 프로필 파싱 (match_detail과 동일)
        is_sender = (current_uid == sender.user_id)
        counterpart_nickname = receiver.nickname if is_sender else sender.nickname
        
        def parse_profile(profile_obj):
            if not profile_obj or not profile_obj.full_report_json: return None
            raw = profile_obj.full_report_json
            try: return json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError): return raw

        my_profile = parse_profile(sender_profile if is_sender else receiver_profile)
        target_profile = parse_profile(receiver_profile if is_sender else sender_profile)

        # 4. 매칭 점수 재계산 (match_detail과 동일)
        target_candidate = {
            'user_id': receiver.user_id if is_sender else sender.user_id,
            'full_report_json': target_profile, 'nickname': counterpart_nickname
        }
        calculated_list = MatchManager._calculate_match_scores(
            my_user_id=current_uid, candidates=[target_candidate], current_user_profile_json=my_profile
        )
        match_data = calculated_list[0] if calculated_list else {}

        # 5. JSON으로 내보낼 데이터 구성
        json_output = {
            "request_info": {
                'request_id': req.request_id,
                'status': req.status,
                'created_at_utc': req.created_at.isoformat(),
                'match_code': req.match_code,
                'is_sender': is_sender
            },
            "my_user_info": {
                "user_id": sender.user_id if is_sender else receiver.user_id,
                "nickname": sender.nickname if is_sender else receiver.nickname,
            },
            "counterpart_user_info": {
                "user_id": receiver.user_id if is_sender else sender.user_id,
                "nickname": receiver.nickname if is_sender else sender.nickname,
            },
            "match_analysis": {
                "match_score": match_data.get('match_score'),
                "match_details": match_data.get('match_details'),
                "comparison_data": {
                    'my_big5': match_data.get('my_big5'),
                    'cand_big5': match_data.get('cand_big5'),
                    'my_line_count': match_data.get('my_line_count'),
                    'cand_line_count': match_data.get('cand_line_count'),
                    'my_functions': match_data.get('my_functions'),
                    'cand_functions': match_data.get('cand_functions'),
                    'relative_traits': match_data.get('relative_traits', [])
                }
            },
            "my_profile_json": my_profile,
            "counterpart_profile_json": target_profile,
        }

        # 6. JSON 응답 생성
        response = app.response_class(
            response=json.dumps(json_output, indent=4, ensure_ascii=False),
            status=200,
            mimetype='application/json'
        )
        filename = f"match_detail_{request_id}_{datetime.now().strftime('%Y%m%d')}.json"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response

    except Exception as e:
        app.logger.error(f"Failed to download match JSON for request {request_id}: {e}")
        flash("JSON 데이터를 생성하는 중 오류가 발생했습니다.", "danger")
        return redirect(url_for('match_detail', request_id=request_id))


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

@app.route('/unmatch/withdraw/<int:request_id>', methods=['POST'])
@login_required
def withdraw_unmatch(request_id):
    result = MatchManager.withdraw_unmatch_request(g.user.user_id, request_id)
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
        valid = [r for r in representative_results if r.openness is not None]
        count = len(valid) or 1  # ZeroDivisionError 방지
        avg_openness = sum(r.openness for r in valid) / count
        avg_conscientiousness = sum(r.conscientiousness for r in valid if r.conscientiousness is not None) / count
        avg_extraversion = sum(r.extraversion for r in valid if r.extraversion is not None) / count
        avg_agreeableness = sum(r.agreeableness for r in valid if r.agreeableness is not None) / count
        avg_neuroticism = sum(r.neuroticism for r in valid if r.neuroticism is not None) / count
    else:
        avg_openness = avg_conscientiousness = avg_extraversion = avg_agreeableness = avg_neuroticism = 0

    stats['big5_labels'] = ['Openness',
                            'Conscientiousness',
                            'Extraversion',
                            'Agreeableness',
                            'Neuroticism']
    stats['big5_scores'] = [avg_openness,
                            avg_conscientiousness,
                            avg_extraversion,
                            avg_agreeableness,
                            avg_neuroticism]

    # [Modified] 2-3. 후보군 통계 (DB 기반)
    # File System Scanning Logic Removed
    candidate_files = [] # Legacy compatibility
    stats['candidate_files'] = PersonalityResult.query.filter_by(is_representative=True).count()

    # 3. 매칭 로그 조회 (최신 100건)
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
    """사용자 목록 검색 API (JSON) - 대표 결과 ID 포함"""
    query = request.args.get('q', '').strip()

    # User와 Representative Result ID를 함께 조회 (Outer Join)
    # PersonalityResult가 중복될 수 있으므로, 대표 결과(is_representative=True)만 조인
    q = db.session.query(User, PersonalityResult)\
        .outerjoin(PersonalityResult, (User.user_id == PersonalityResult.user_id) & (PersonalityResult.is_representative == True))

    if query:
        # Numeric ID search support
        from sqlalchemy import cast, String
        q = q.filter(
            (User.username.ilike(f'%{query}%')) |
            (User.nickname.ilike(f'%{query}%')) |
            (User.email.ilike(f'%{query}%')) |
            (cast(User.user_id, String).ilike(f'%{query}%'))
        )

    sort_by = request.args.get('sort_by', 'created_at')
    order = request.args.get('order', 'desc')

    # Sorting mapping
    sort_column = User.created_at
    if sort_by == 'user_id':
        sort_column = User.user_id
    elif sort_by == 'nickname':
        sort_column = User.nickname
    elif sort_by == 'email':
        sort_column = User.email
    elif sort_by == 'status': # Assuming status check logic or is_banned
         sort_column = User.is_banned

    # Apply ordering
    if order == 'asc':
        ordering = sort_column.asc()
    else:
        ordering = sort_column.desc()

    results = q.order_by(ordering).all()

    users_data = []
    for u, presult in results:
        # 성격 상세 정보
        mbti = presult.mbti_prediction if presult else None
        socio = presult.socionics_prediction if presult else None
        big5 = None
        if presult:
            big5 = {
                'O': presult.openness,
                'C': presult.conscientiousness,
                'E': presult.extraversion,
                'A': presult.agreeableness,
                'N': presult.neuroticism
            }

        users_data.append({
            'user_id': u.user_id,
            'username': u.username,
            'nickname': u.nickname or u.username,
            'email': u.email,
            'created_at': u.created_at.strftime('%Y-%m-%d'),
            'is_banned': u.is_banned,
            'is_dummy': getattr(u, 'is_dummy', False),
            'representative_result_id': presult.result_id if presult else None,
            'mbti': mbti,
            'socionics': socio,
            'big5': big5
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
             return jsonify({"success": False,
                             "message": "잘못된 사용자 ID 형식입니다. 존재하는 사용자 ID(숫자)를 입력 해주세요."}), 400
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
# [DB Migration] JSON 파일 대신 DB 테이블(users, personality_results)을 사용합니다.

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

def _create_dummy_user_in_db(name, mbti, socionics, big5, activity_lines):
    """
    [Helper] 더미 사용자를 DB에 생성합니다.

    Returns:
        dict: {'success': bool, 'user_id': int or None, 'message': str}
    """
    try:
        # 고유 식별자 생성 (UUID 기반)
        import uuid
        unique_id = uuid.uuid4().hex[:12]

        # 1. User 레코드 생성 (is_dummy=True, 가상 이메일 사용)
        new_user = User(
            email=f"dummy_{unique_id}@echomind.internal",  # 고유 가상 이메일
            password_hash="DUMMY_NO_LOGIN",  # 로그인 불가 마커
            username=name,
            nickname=name,
            gender="MALE", # 기본값 추가 (IntegrityError 방지)
            birth_date=datetime(2000, 1, 1), # 기본값 추가
            is_dummy=True,
            is_banned=False
        )
        db.session.add(new_user)
        db.session.flush()  # user_id 확보

        # 2. full_report_json 구조 생성 (기존 형식 유지)
        full_report = {
            "meta": {
                "source": "dummy_simulation",
                "is_dummy": True,
                "generated_at_utc": datetime.utcnow().isoformat() + "Z",
                "speaker_name": name,
                "user_id": new_user.user_id  # 이제 정수형 ID
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

        # 3. PersonalityResult 레코드 생성
        new_result = PersonalityResult(
            user_id=new_user.user_id,
            log_id=None,  # 더미는 ChatLog 없음
            is_representative=True,
            line_count_at_analysis=activity_lines,
            openness=float(big5.get('openness', 50)),
            conscientiousness=float(big5.get('conscientiousness', 50)),
            extraversion=float(big5.get('extraversion', 50)),
            agreeableness=float(big5.get('agreeableness', 50)),
            neuroticism=float(big5.get('neuroticism', 50)),
            big5_confidence=1.0,
            mbti_prediction=mbti,
            mbti_confidence=1.0,
            socionics_prediction=socionics,
            socionics_confidence=1.0,
            summary_text=f"[더미 데이터] {name} - 시뮬레이션 테스트용",
            full_report_json=full_report
        )
        db.session.add(new_result)
        db.session.commit()

        return {'success': True, 'user_id': new_user.user_id, 'message': f'더미 사용자 "{name}" 생성 완료'}

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"더미 생성 오류: {e}")
        return {'success': False, 'user_id': None, 'message': str(e)}

@app.route('/admin/api/dummy/list', methods=['GET'])
@admin_required
def admin_list_dummies():
    """[관리자] DB에서 더미 사용자 목록 조회 (is_dummy=True)"""
    try:
        # DB에서 더미 사용자 조회 (User + PersonalityResult JOIN)
        dummies = db.session.query(User, PersonalityResult)\
            .outerjoin(PersonalityResult,
                       (User.user_id == PersonalityResult.user_id) & (PersonalityResult.is_representative == True))\
            .filter(User.is_dummy == True)\
            .all()

        result = []
        for user, pr in dummies:
            # PersonalityResult에서 데이터 추출
            big5_data = {}
            if pr:
                big5_data = {
                    'openness': pr.openness,
                    'conscientiousness': pr.conscientiousness,
                    'extraversion': pr.extraversion,
                    'agreeableness': pr.agreeableness,
                    'neuroticism': pr.neuroticism
                }

            result.append({
                'dummy_id': user.user_id,  # 이제 정수형 ID
                'name': user.nickname or user.username,
                'mbti': pr.mbti_prediction if pr else '',
                'socionics': pr.socionics_prediction if pr else '',
                'big5': big5_data,
                'activity': pr.line_count_at_analysis if pr else 0,
                'created_at': user.created_at.isoformat() if user.created_at else ''
            })

        return {'success': True, 'dummies': result}

    except Exception as e:
        app.logger.error(f"더미 목록 조회 오류: {e}")
        return {'success': False, 'message': str(e)}, 500

@app.route('/admin/api/dummy/create', methods=['POST'])
@admin_required
def admin_create_dummy():
    """[관리자] 더미 사용자 생성 (DB 저장)"""
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

        # DB에 저장 (헬퍼 함수 호출)
        result = _create_dummy_user_in_db(name, mbti, socionics, big5, activity_lines)

        if result['success']:
            return {'success': True, 'dummy_id': result['user_id'], 'message': result['message']}
        else:
            return {'success': False, 'message': result['message']}, 500

    except Exception as e:
        app.logger.error(f"더미 생성 오류: {e}")
        return {'success': False, 'message': str(e)}, 500

@app.route('/admin/api/dummy/random', methods=['POST'])
@admin_required
def admin_create_random_dummy():
    """[관리자] 랜덤 더미 사용자 일괄 생성 (DB 저장)"""
    import random
    import string

    try:
        # 요청 파라미터에서 count 확인 (기본값 1, 최대 50)
        data = request.get_json(silent=True) or {}
        count = int(data.get('count', 1))

        if count < 1: count = 1
        if count > 50: count = 50  # 안전을 위한 최대 제한

        created_users = []

        for _ in range(count):
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

            # DB에 저장 (헬퍼 함수 호출)
            result = _create_dummy_user_in_db(random_name,
                                              random_mbti,
                                              random_socionics,
                                              random_big5,
                                              random_activity)

            if result['success']:
                created_users.append({
                    'dummy_id': result['user_id'],
                    'name': random_name
                })

        return {
            'success': True,
            'message': f'총 {len(created_users)}명의 더미 사용자가 생성되었습니다.',
            'count': len(created_users),
            'last_created': created_users[-1] if created_users else None
        }

    except Exception as e:
        app.logger.error(f"랜덤 더미 일괄 생성 오류: {e}")
        return {'success': False, 'message': str(e)}, 500

@app.route('/admin/api/dummy/<int:dummy_id>', methods=['DELETE'])
@admin_required
def admin_delete_dummy(dummy_id):
    """[관리자] 더미 사용자 삭제 (DB에서 삭제, CASCADE로 PersonalityResult도 삭제됨)"""
    try:
        user = User.query.filter_by(user_id=dummy_id, is_dummy=True).first()

        if not user:
            return {'success': False, 'message': '해당 더미 사용자를 찾을 수 없습니다.'}, 404

        nickname = user.nickname or user.username
        db.session.delete(user)  # CASCADE로 연관 데이터 자동 삭제
        db.session.commit()

        return {'success': True, 'message': f'더미 사용자 "{nickname}" (ID: {dummy_id}) 삭제 완료'}

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"더미 삭제 오류: {e}")
        return {'success': False, 'message': str(e)}, 500


@app.route('/admin/api/stats', methods=['GET'])
@admin_required
def admin_dashboard_stats():
    """[관리자] 대시보드 통계 데이터 JSON 반환 (새로고침용)"""
    try:
        # Chart Data
        chart_data = visualize_profile.generate_dashboard_stats()
        return {'success': True, 'chart_data': chart_data}
    except Exception as e:
        app.logger.error(f"통계 데이터 조회 오류: {e}")
        return {'success': False, 'message': str(e)}, 500


@app.route('/admin/api/dummy/bulk_delete', methods=['POST'])
@admin_required
def admin_delete_bulk_dummies():
    """[관리자] 더미 사용자 일괄 삭제"""
    try:
        data = request.get_json()
        count = int(data.get('count', 0))
        order = data.get('order', 'recent') # 'recent' or 'oldest'

        if count <= 0:
            return {'success': False, 'message': '삭제할 수량을 입력해주세요.'}, 400

        # 더미 사용자 조회 Query
        query = User.query.filter_by(is_dummy=True)

        if order == 'recent':
            query = query.order_by(User.created_at.desc())
        else:
            query = query.order_by(User.created_at.asc())

        targets = query.limit(count).all()

        if not targets:
            return {'success': False, 'message': '삭제할 더미 사용자가 없습니다.'}

        deleted_count = 0
        from extensions import MatchRequest

        for user in targets:
            # 연관 데이터 삭제 (Cascade 설정이 되어있지 않을 수 있으므로 명시적 삭제 권장)
            # PersonalityResult 삭제
            PersonalityResult.query.filter_by(user_id=user.user_id).delete()
            # MatchRequest 삭제
            MatchRequest.query.filter((MatchRequest.sender_id==user.user_id) | (MatchRequest.receiver_id==user.user_id)).delete()

            # User 삭제
            db.session.delete(user)
            deleted_count += 1

        db.session.commit()

        return {
            'success': True,
            'message': f'{deleted_count}명의 더미 사용자가 삭제되었습니다.',
            'deleted_count': deleted_count
        }

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"일괄 삭제 오류: {e}")
        return {'success': False, 'message': str(e)}, 500

# -------------------------------------------------------------------------
# [System Management APIs]
# -------------------------------------------------------------------------
from utils_system import get_system_config, update_system_config, get_log_file_path

@app.route('/admin/api/system/config', methods=['GET', 'POST'])
@admin_required
def admin_system_config():
    """시스템 설정 조회 및 업데이트"""
    if request.method == 'GET':
        return {'success': True, 'config': get_system_config()}
    else: # POST
        try:
            data = request.get_json()
            # Update known keys
            if 'hide_dummies' in data:
                update_system_config('hide_dummies', bool(data['hide_dummies']))

            if 'log_level' in data:
                new_level = int(data['log_level'])
                if 1 <= new_level <= 5:
                    update_system_config('log_level', new_level)
                    # 로그 레벨 즉시 적용 시도, 재시작 없이
                    # Root Logger 및 File Handler 레벨 조정
                    app.logger.setLevel(LOG_LEVEL_MAP.get(new_level, logging.ERROR))
                    for h in app.logger.handlers:
                        if isinstance(h, (logging.FileHandler, RotatingFileHandler)):
                            h.setLevel(LOG_LEVEL_MAP.get(new_level, logging.ERROR))

            return {'success': True, 'message': '설정이 저장되었습니다.', 'config': get_system_config()}
        except Exception as e:
            return {'success': False, 'message': str(e)}, 500

@app.route('/admin/api/system/logs', methods=['GET'])
@admin_required
def admin_system_logs():
    """서버 로그 파일 조회 (Tail 100 lines)"""
    try:
        log_path = get_log_file_path(app.debug)
        lines = []
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read all lines and take last 100
                # 효율적인 tail reading은 아니지만 로그 파일이 아주 크지 않다고 가정
                all_lines = f.readlines()
                lines = all_lines[-100:]
        return {'success': True, 'logs': lines, 'path': log_path}
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500

@app.route('/admin/api/system/reset_dummies', methods=['POST'])
@admin_required
def admin_reset_dummies():
    """[Danger] 모든 더미 사용자 및 관련 데이터 삭제"""
    try:
        # DB에서 더미 사용자 조회
        dummies = User.query.filter_by(is_dummy=True).all()
        count = len(dummies)

        if count == 0:
            return {'success': True, 'message': '삭제할 더미 사용자가 없습니다.'}

        from extensions import MatchRequest

        deleted_count = 0
        for user in dummies:
             # 연관 데이터 먼저 삭제
            PersonalityResult.query.filter_by(user_id=user.user_id).delete()
            MatchRequest.query.filter((MatchRequest.sender_id==user.user_id) | (MatchRequest.receiver_id==user.user_id)).delete()

            db.session.delete(user)
            deleted_count += 1

        db.session.commit()
        app.logger.warning(f"[System] Admin reset {deleted_count} dummy users.")

        return {'success': True, 'message': f'총 {deleted_count}명의 더미 사용자가 완전히 초기화되었습니다.'}
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"더미 초기화 오류: {e}")
        return {'success': False, 'message': str(e)}, 500

# -------------------------------------------------------------------------
# [Chat System]
# -------------------------------------------------------------------------
@app.route('/chat/<string:request_id>')
@login_required
def chat_room(request_id):
    """1:1 채팅방 화면"""
    req = MatchRequest.query.filter_by(match_code=request_id).first()

    # 이전의 숫자 ID(request_id)로 접근한 경우 난수 코드로 리다이렉트
    if not req and request_id.isdigit():
        req = MatchRequest.query.get_or_404(int(request_id))
        return redirect(url_for('chat_room', request_id=req.match_code))
    elif not req:
        from flask import abort
        abort(404)

    # 권한 확인 (당사자만 접근 가능)
    if req.sender_id != g.user.user_id and req.receiver_id != g.user.user_id:
        flash("접근 권한이 없습니다.", "danger")
        return redirect(url_for('match_inbox'))

    # 매칭 성사 여부 확인
    if req.status not in ['ACCEPTED', 'CANCEL_REQ_SENDER', 'CANCEL_REQ_RECEIVER']:
        flash("성사된 매칭만 채팅할 수 있습니다.", "warning")
        return redirect(url_for('match_inbox'))

    # 상대방 정보 조회
    partner_id = req.receiver_id if req.sender_id == g.user.user_id else req.sender_id
    partner = User.query.get(partner_id)

    # 템플릿의 API 호출이 깨지지 않도록 request_id 변수에 match_code를 담아 넘깁니다
    return render_template('chat.html', request_id=req.match_code, partner=partner)

@app.route('/api/chat/<string:request_id>/messages')
@login_required
def get_chat_messages(request_id):
    """메시지 목록 조회 (Polling용)"""
    try:
        req = MatchRequest.query.filter_by(match_code=request_id).first()
        if not req and request_id.isdigit():
            req = MatchRequest.query.get(int(request_id))
            if not req:
                return jsonify({'error': 'Not found'}), 404
        elif not req:
            return jsonify({'error': 'Not found'}), 404

        real_request_id = req.request_id

        if req.sender_id != g.user.user_id and req.receiver_id != g.user.user_id:
            return jsonify({'error': 'Unauthorized'}), 403

        messages = Message.query.filter_by(request_id=real_request_id).order_by(Message.created_at.asc()).all()

        # 읽음 처리 (상대방이 보낸 메시지)
        unread_exist = False
        for m in messages:
            if m.sender_id != g.user.user_id and not m.is_read:
                m.is_read = True
                unread_exist = True
        if unread_exist:
            db.session.commit()

        msg_list = []
        WEEKDAYS = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        last_date_str = None

        for m in messages:
            # KST 시간 변환
            kst_time = m.created_at + timedelta(hours=9) if m.created_at else datetime.utcnow() + timedelta(hours=9)
            current_date_str = kst_time.strftime('%Y년 %m월 %d일')

            # 날짜 구분선 삽입
            if current_date_str != last_date_str:
                weekday_str = WEEKDAYS[kst_time.weekday()]
                msg_list.append({
                    'id': f'date-{m.id}',
                    'sender_id': 0,
                    'content': f"{current_date_str} {weekday_str}",
                    'is_system': True,
                    'created_at': '',
                    'is_me': False,
                    'is_read': True
                })
                last_date_str = current_date_str

            msg_list.append({
                'id': m.id,
                'sender_id': m.sender_id,
                'content': m.content,
                'is_system': False,
                'created_at': kst_time.strftime('%H:%M'),
                'is_me': m.sender_id == g.user.user_id,
                'is_read': m.is_read
            })

        return jsonify({'messages': msg_list})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"API Chat messages error: {e}")
        return jsonify({'error': '서버 처리 중 오류가 발생했습니다.'}), 500

@app.route('/api/chat/<string:request_id>/send', methods=['POST'])
@login_required
def send_chat_message(request_id):
    """메시지 전송"""
    try:
        req = MatchRequest.query.filter_by(match_code=request_id).first()
        if not req and request_id.isdigit():
            req = MatchRequest.query.get_or_404(int(request_id))
        elif not req:
            return jsonify({'error': 'Not found'}), 404

        real_request_id = req.request_id

        data = request.get_json()
        content = data.get('content', '').strip()

        if not content: return jsonify({'error': 'Empty message'}), 400
        content = str(escape(content))  # XSS 방어: HTML 태그 이스케이프

        msg = Message(request_id=real_request_id, sender_id=g.user.user_id, content=content)
        db.session.add(msg)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"API Chat send error: {e}")
        return jsonify({'error': '서버 처리 중 오류가 발생했습니다.'}), 500

# -------------------------------------------------------------------------
# [Group Chat System (조건부 그룹 채팅)]
# -------------------------------------------------------------------------
def calculate_age(birth_date):
    if not birth_date: return None
    from datetime import date
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def validate_conditions(user, profile, conditions):
    if not conditions:
        return True, "조건 없음"

    # 1. 성별 검증
    allowed_genders = conditions.get('genders', [])
    if allowed_genders and user.gender not in allowed_genders:
        return False, f"입장 가능한 성별이 아닙니다. (내 성별: {user.gender})"

    # 2. 나이 검증
    min_age = conditions.get('min_age')
    max_age = conditions.get('max_age')
    if min_age or max_age:
        age = calculate_age(user.birth_date)
        if age is None:
            return False, "생년월일 정보가 없어 나이 조건을 확인할 수 없습니다."
        if min_age and age < int(min_age):
            return False, f"최소 {min_age}세 이상만 입장 가능합니다."
        if max_age and age > int(max_age):
            return False, f"최대 {max_age}세 이하만 입장 가능합니다."

    # 프로필 필수 조건 검증 (MBTI, 소시오닉스, Big5)
    has_personality_condition = any(k in conditions for k in ['mbtis', 'quadras', 'big5'])
    if has_personality_condition and not profile:
         return False, "성향 조건이 설정된 방입니다. 먼저 대화 분석을 진행하고 대표 프로필을 설정해주세요."

    if profile:
        # 3. MBTI 검증
        allowed_mbtis = conditions.get('mbtis', [])
        if allowed_mbtis and profile.mbti_prediction not in allowed_mbtis:
            return False, f"입장 가능한 MBTI가 아닙니다. (내 MBTI: {profile.mbti_prediction})"

        # 4. 소시오닉스 쿼드라 검증
        allowed_quadras = conditions.get('quadras', [])
        if allowed_quadras:
            from matcher import RelationshipBrain
            user_quadra = None
            for q_name, types in RelationshipBrain.QUADRAS.items():
                if profile.socionics_prediction in types:
                    user_quadra = q_name.split()[0] # "Alpha (개방/아이디어)" -> "Alpha"
                    break
            if not user_quadra or user_quadra not in allowed_quadras:
                return False, f"입장 가능한 소시오닉스 쿼드라가 아닙니다. (내 쿼드라: {user_quadra or '알수없음'})"

        # 5. Big 5 검증
        big5_conds = conditions.get('big5', {})
        for trait, limits in big5_conds.items():
            min_val, max_val = limits.get('min', 0), limits.get('max', 100)
            user_val = getattr(profile, trait, 50)
            if user_val < min_val or user_val > max_val:
                trait_kr = {"openness": "개방성",
                            "conscientiousness": "성실성",
                            "extraversion": "외향성",
                            "agreeableness": "우호성",
                            "neuroticism": "신경성"}.get(trait, trait)
                return False, f"{trait_kr} 점수가 조건({min_val}~{max_val})에 맞지 않습니다. (나의 점수: {int(user_val)})"

    return True, "조건을 모두 만족합니다."

@app.route('/groups')
@login_required
def group_lobby():
    """그룹 채팅방 로비 (목록)"""
    rooms = GroupChatRoom.query.order_by(GroupChatRoom.created_at.desc()).all()
    joined_rooms = [p.room_id for p in GroupChatParticipant.query.filter_by(user_id=g.user.user_id).all()]
    profile = PersonalityResult.query.filter_by(user_id=g.user.user_id, is_representative=True).first()

    room_data = []
    for r in rooms:
        is_joined = r.id in joined_rooms
        can_join, reason = validate_conditions(g.user, profile, r.conditions)
        participant_count = GroupChatParticipant.query.filter_by(room_id=r.id).count()

        room_data.append({
            'id': r.id,
            'room_code': r.room_code,
            'name': r.name,
            'description': r.description,
            'max_participants': r.max_participants,
            'current_participants': participant_count,
            'conditions': r.conditions,
            'is_joined': is_joined,
            'can_join': can_join,
            'reason': reason
        })

    return render_template('group_lobby.html', rooms=room_data)

@app.route('/groups/create', methods=['GET', 'POST'])
@login_required
def group_create():
    """새로운 조건부 그룹 채팅방 생성"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        max_p_raw = request.form.get('max_participants')
        max_p = int(max_p_raw) if max_p_raw and max_p_raw.isdigit() else 10

        conditions = {}
        genders = request.form.getlist('genders')
        if genders: conditions['genders'] = genders

        min_age = request.form.get('min_age')
        max_age = request.form.get('max_age')
        if min_age: conditions['min_age'] = int(min_age)
        if max_age: conditions['max_age'] = int(max_age)

        mbtis = request.form.getlist('mbtis')
        if mbtis: conditions['mbtis'] = mbtis

        quadras = request.form.getlist('quadras')
        if quadras: conditions['quadras'] = quadras

        big5_conds = {}
        for trait in ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']:
            t_min = request.form.get(f'big5_{trait}_min')
            t_max = request.form.get(f'big5_{trait}_max')
            if t_min and t_max:
                if int(t_min) > 0 or int(t_max) < 100:
                    big5_conds[trait] = {'min': int(t_min), 'max': int(t_max)}
        if big5_conds:
            conditions['big5'] = big5_conds

        try:
            import random
            new_room_code = str(random.randint(1000000000, 9999999999))
            new_room = GroupChatRoom(room_code=new_room_code,
                                     name=name,
                                     description=description,
                                     creator_id=g.user.user_id,
                                     max_participants=max_p,
                                     conditions=conditions)
            db.session.add(new_room)
            db.session.flush() # commit 대신 flush로 안전하게 room_id 확보 (단일 트랜잭션 보장)

            # 생성자는 자동으로 참여자로 등록
            db.session.add(GroupChatParticipant(room_id=new_room.id, user_id=g.user.user_id))

            # 방 개설 시스템 메시지
            join_msg = GroupChatMessage(
                room_id=new_room.id,
                sender_id=g.user.user_id,
                content=f"{g.user.nickname or g.user.username} 님께서 방을 개설했습니다.",
                is_system=True
            )
            db.session.add(join_msg)
            db.session.commit()

            flash("성향 기반 그룹 채팅방이 개설되었습니다.", "success")
            return redirect(url_for('group_lobby'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Group create error: {e}")
            flash("방 생성 중 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", "danger")
            return redirect(url_for('group_create'))

    return render_template('group_create.html')

@app.route('/groups/<room_code>/join', methods=['POST'])
@login_required
def group_join(room_code):
    """채팅방 조건 검증 및 입장"""
    room = GroupChatRoom.query.filter_by(room_code=room_code).first_or_404()
    room_id = room.id

    if GroupChatParticipant.query.filter_by(room_id=room_id, user_id=g.user.user_id).first():
        return redirect(url_for('group_chat_room', room_code=room_code))

    if GroupChatParticipant.query.filter_by(room_id=room_id).count() >= room.max_participants:
        flash("채팅방 인원이 가득 찼습니다.", "danger")
        return redirect(url_for('group_lobby'))

    profile = PersonalityResult.query.filter_by(user_id=g.user.user_id, is_representative=True).first()
    can_join, reason = validate_conditions(g.user, profile, room.conditions)

    if not can_join:
        flash(f"입장 불가: {reason}", "danger")
        return redirect(url_for('group_lobby'))

    try:
        db.session.add(GroupChatParticipant(room_id=room.id, user_id=g.user.user_id))

        # 입장 시스템 메시지
        join_msg = GroupChatMessage(
            room_id=room.id,
            sender_id=g.user.user_id,
            content=f"{g.user.nickname or g.user.username} 님께서 입장하셨습니다.",
            is_system=True
        )
        db.session.add(join_msg)
        db.session.commit()
        flash("채팅방에 성공적으로 입장했습니다.", "success")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Group join error: {e}")
        flash("입장 처리 중 서버 오류가 발생했습니다.", "danger")

    return redirect(url_for('group_chat_room', room_code=room_code))

@app.route('/groups/<room_code>')
@login_required
def group_chat_room(room_code):
    """조건부 그룹 채팅방 메인 UI"""
    room = GroupChatRoom.query.filter_by(room_code=room_code).first_or_404()
    participant = GroupChatParticipant.query.filter_by(room_id=room.id, user_id=g.user.user_id).first()
    if not participant:
        flash("참여하지 않은 채팅방입니다.", "warning")
        return redirect(url_for('group_lobby'))

    return render_template('group_chat.html', room=room)

@app.route('/groups/<room_code>/leave', methods=['POST'])
@login_required
def group_leave(room_code):
    """참여자: 채팅방 나가기"""
    room = GroupChatRoom.query.filter_by(room_code=room_code).first_or_404()
    room_id = room.id
    if room.creator_id == g.user.user_id:
        flash("방장은 방을 나갈 수 없습니다. 방 해체하기를 이용해주세요.", "warning")
        return redirect(url_for('group_chat_room', room_code=room_code))

    participant = GroupChatParticipant.query.filter_by(room_id=room_id, user_id=g.user.user_id).first()
    if participant:
        try:
            db.session.delete(participant)
            leave_msg = GroupChatMessage(
                room_id=room_id,
                sender_id=g.user.user_id,
                content=f"{g.user.nickname or g.user.username} 님이 채팅방을 나갔습니다.",
                is_system=True
            )
            db.session.add(leave_msg)
            db.session.commit()
            flash("채팅방에서 성공적으로 나갔습니다.", "success")
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Group leave error: {e}")
            flash("처리 중 서버 오류가 발생했습니다.", "danger")

    return redirect(url_for('group_lobby'))

@app.route('/groups/<room_code>/delete', methods=['POST'])
@login_required
def group_delete(room_code):
    """방장: 채팅방 해체"""
    room = GroupChatRoom.query.filter_by(room_code=room_code).first_or_404()
    if room.creator_id != g.user.user_id:
        flash("방을 해체할 권한이 없습니다.", "danger")
        return redirect(url_for('group_chat_room', room_code=room_code))

    try:
        db.session.delete(room)
        db.session.commit()
        flash("채팅방이 성공적으로 해체되었습니다.", "success")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Group delete error: {e}")
        flash("처리 중 서버 오류가 발생했습니다.", "danger")

    return redirect(url_for('group_lobby'))

@app.route('/api/groups/<room_code>/messages')
@login_required
def get_group_chat_messages(room_code):
    """그룹 채팅방 메시지 목록 조회 (Polling용)"""
    try:
        room = GroupChatRoom.query.filter_by(room_code=room_code).first()
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        room_id = room.id
        participant = GroupChatParticipant.query.filter_by(room_id=room_id, user_id=g.user.user_id).first()
        if not participant:
            return jsonify({'error': 'Unauthorized'}), 403

        messages = GroupChatMessage.query.filter_by(room_id=room_id).order_by(GroupChatMessage.created_at.asc()).all()

        # 메시지를 조회할 때 나의 마지막 읽은 지점 업데이트
        if messages:
            max_msg_id = messages[-1].id
            if participant.last_read_message_id < max_msg_id:
                participant.last_read_message_id = max_msg_id
                db.session.commit()

        # 안 읽은 카운트 계산을 위한 데이터 준비
        all_participants = GroupChatParticipant.query.filter_by(room_id=room_id).all()
        read_thresholds = [p.last_read_message_id for p in all_participants]
        total_participants = len(read_thresholds)

        msg_list = []
        WEEKDAYS = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        last_date_str = None

        for m in messages:
            sender = User.query.get(m.sender_id)
            read_count = sum(1 for threshold in read_thresholds if threshold >= m.id)
            unread_count = total_participants - read_count

            # KST 시간 변환
            kst_time = m.created_at + timedelta(hours=9) if m.created_at else datetime.utcnow() + timedelta(hours=9)
            current_date_str = kst_time.strftime('%Y년 %m월 %d일')

            # 날짜가 바뀌면 날짜 구분선(시스템 메시지) 삽입
            if current_date_str != last_date_str:
                weekday_str = WEEKDAYS[kst_time.weekday()]
                msg_list.append({
                    'id': f'date-{m.id}',
                    'sender_id': 0,
                    'sender_nickname': 'System',
                    'content': f"{current_date_str} {weekday_str}",
                    'is_system': True,
                    'unread_count': 0,
                    'created_at': '',
                    'is_me': False
                })
                last_date_str = current_date_str

            msg_list.append({
                'id': m.id,
                'sender_id': m.sender_id,
                'sender_nickname': sender.nickname or sender.username if sender else '알 수 없음',
                'content': m.content,
                'is_system': m.is_system,
                'unread_count': unread_count if unread_count > 0 else 0,
                'created_at': kst_time.strftime('%H:%M'),
                'is_me': m.sender_id == g.user.user_id
            })

        return jsonify({'messages': msg_list})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"API Group messages error: {e}")
        return jsonify({'error': '서버 처리 중 오류가 발생했습니다.'}), 500

@app.route('/api/groups/<room_code>/send', methods=['POST'])
@login_required
def send_group_chat_message(room_code):
    """그룹 채팅방 메시지 전송"""
    try:
        room = GroupChatRoom.query.filter_by(room_code=room_code).first_or_404()
        room_id = room.id
        participant = GroupChatParticipant.query.filter_by(room_id=room_id, user_id=g.user.user_id).first()
        if not participant:
            return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json()
        content = data.get('content', '').strip()

        if not content: return jsonify({'error': 'Empty message'}), 400
        content = str(escape(content))  # XSS 방어: HTML 태그 이스케이프

        msg = GroupChatMessage(room_id=room_id, sender_id=g.user.user_id, content=content)
        db.session.add(msg)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"API Group send error: {e}")
        return jsonify({'error': '메시지 전송 중 오류가 발생했습니다.'}), 500

@app.route('/api/groups/<room_code>/participants')
@login_required
def get_group_chat_participants(room_code):
    """그룹 채팅방 참여자 목록 조회"""
    try:
        room = GroupChatRoom.query.filter_by(room_code=room_code).first_or_404()
        room_id = room.id
        participant = GroupChatParticipant.query.filter_by(room_id=room_id, user_id=g.user.user_id).first()
        if not participant:
            return jsonify({'error': 'Unauthorized'}), 403

        participants = GroupChatParticipant.query.filter_by(room_id=room_id).all()
        total_p = len(participants)
        threshold = (total_p // 2) + 1

        res = []
        for p in participants:
            u = User.query.get(p.user_id)
            if u:
                votes = GroupChatKickVote.query.filter_by(room_id=room_id, target_id=p.user_id).count()
                my_vote = GroupChatKickVote.query.filter_by(room_id=room_id,
                                                            target_id=p.user_id,
                                                            voter_id=g.user.user_id).first() is not None
                res.append({
                    'user_id': u.user_id,
                    'nickname': u.nickname or u.username,
                    'is_me': u.user_id == g.user.user_id,
                    'is_creator': u.user_id == room.creator_id,
                    'votes': votes,
                    'threshold': threshold,
                    'voted_by_me': my_vote
                })
        return jsonify({'participants': res})
    except Exception as e:
        app.logger.error(f"API Group participants error: {e}")
        return jsonify({'error': '서버 처리 중 오류가 발생했습니다.'}), 500

@app.route('/api/groups/<room_code>/kick/<int:target_id>', methods=['POST'])
@login_required
def vote_kick_participant(room_code, target_id):
    """강퇴 투표 API"""
    try:
        room = GroupChatRoom.query.filter_by(room_code=room_code).first_or_404()
        room_id = room.id
        if target_id == room.creator_id:
            return jsonify({'error': '방장은 강퇴할 수 없습니다.'}), 400

        if not GroupChatParticipant.query.filter_by(room_id=room_id, user_id=g.user.user_id).first():
            return jsonify({'error': '권한이 없습니다.'}), 403

        target_p = GroupChatParticipant.query.filter_by(room_id=room_id, user_id=target_id).first()
        if not target_p:
            return jsonify({'error': '대상이 채팅방에 없습니다.'}), 400

        existing_vote = GroupChatKickVote.query.filter_by(room_id=room_id,
                                                          voter_id=g.user.user_id,
                                                          target_id=target_id).first()
        if existing_vote:
            db.session.delete(existing_vote)
            db.session.commit()
            return jsonify({'success': True, 'action': 'unvoted'})

        db.session.add(GroupChatKickVote(room_id=room_id, voter_id=g.user.user_id, target_id=target_id))
        db.session.commit()

        total_p = GroupChatParticipant.query.filter_by(room_id=room_id).count()
        votes = GroupChatKickVote.query.filter_by(room_id=room_id, target_id=target_id).count()
        if votes >= (total_p // 2) + 1:
            db.session.delete(target_p)
            votes_to_delete = GroupChatKickVote.query.filter_by(room_id=room_id, target_id=target_id).all()
            for v in votes_to_delete: db.session.delete(v)
            target_u = User.query.get(target_id)
            if target_u:
                db.session.add(GroupChatMessage(room_id=room_id,
                                                sender_id=g.user.user_id,
                                                content=f"투표 결과에 따라 {target_u.nickname or target_u.username} 님이 강제 퇴장되었습니다.",
                                                is_system=True))
            db.session.commit()
            return jsonify({'success': True, 'action': 'kicked'})

        return jsonify({'success': True, 'action': 'voted'})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Vote kick error: {e}")
        return jsonify({'error': "투표 처리 중 서버 오류가 발생했습니다."}), 500

# -------------------------------------------------------------------------
# [Blind Match System]
# -------------------------------------------------------------------------

@app.route('/blind-inbox')
@login_required
def blind_inbox():
    """블라인드 매칭 인박스 (요청, 활성, 완료 목록)"""
    result = BlindMatchManager.get_user_blind_matches(g.user.user_id)
    if not result.get('success'):
        flash(result.get('message', '데이터를 불러오는 데 실패했습니다.'), 'danger')
        return redirect(url_for('home'))
    
    # 이제 BlindMatchManager가 마지막 메시지와 안 읽은 메시지 수를 모두 계산하므로
    # app.py에서는 추가적인 로직이 필요 없습니다.
    return render_template('blind_inbox.html', blind_matches=result.get('data', {}))

@app.route('/blind-matching')
@login_required
def blind_matching():
    """블라인드 매칭 큐 페이지"""
    # 이제 후보 리스트를 전달하지 않고, 큐 페이지만 렌더링합니다.
    # Alpine.js가 클라이언트 측에서 API를 호출하여 모든 로직을 처리합니다.
    return render_template('blind_match.html')

@app.route('/blind-chat/<string:match_code>')
@login_required
def blind_chat(match_code):
    """블라인드 매칭 익명 채팅방"""
    match = BlindMatch.query.filter_by(match_code=match_code).first_or_404()

    if g.user.user_id not in [match.user1_id, match.user2_id]:
        flash("접근 권한이 없습니다.", "danger")
        return redirect(url_for('blind_inbox'))

    if match.status not in [BlindMatchStatus.ACTIVE,
                            BlindMatchStatus.REVEAL_REQUESTED_BY_1,
                            BlindMatchStatus.REVEAL_REQUESTED_BY_2]:
        flash("활성화된 블라인드 매칭만 채팅할 수 있습니다.", "warning")
        return redirect(url_for('blind_inbox'))

    partner_id = match.user2_id if match.user1_id == g.user.user_id else match.user1_id

    i_am_user1 = g.user.user_id == match.user1_id
    
    # New logic for profile status
    profile_sent_by_me = (i_am_user1 and match.status == BlindMatchStatus.REVEAL_REQUESTED_BY_1) or \
                         (not i_am_user1 and match.status == BlindMatchStatus.REVEAL_REQUESTED_BY_2)
    
    profile_sent_by_partner = (i_am_user1 and match.status == BlindMatchStatus.REVEAL_REQUESTED_BY_2) or \
                              (not i_am_user1 and match.status == BlindMatchStatus.REVEAL_REQUESTED_BY_1)

    profile_status = {
        "i_sent": profile_sent_by_me,
        "partner_sent": profile_sent_by_partner,
    }

    return render_template('blind_chat.html', match=match, partner_id=partner_id, profile_status=profile_status)

# --- 블라인드 매칭 큐 API (신규) ---

@app.route('/api/blind-match/queue/enter', methods=['POST'])
@login_required
def enter_blind_queue():
    """사용자를 매칭 대기열에 추가합니다."""
    result = BlindMatchManager.enter_blind_match_queue(g.user.user_id)
    return jsonify(result)

@app.route('/api/blind-match/queue/leave', methods=['POST'])
@login_required
def leave_blind_queue():
    """사용자를 매칭 대기열에서 제거합니다."""
    result = BlindMatchManager.leave_blind_match_queue(g.user.user_id)
    return jsonify(result)

@app.route('/api/blind-match/queue/status', methods=['GET'])
@login_required
def blind_queue_status():
    """사용자의 현재 대기열 상태를 확인합니다."""
    status = BlindMatchManager.get_queue_status(g.user.user_id)
    return jsonify(status)

@app.route('/api/blind-match/request', methods=['POST'])
@login_required
def api_request_blind_match():
    receiver_id = request.json.get('receiver_id')
    if not receiver_id:
        return jsonify({'success': False, 'message': '상대방 정보가 없습니다.'}), 400
    result = BlindMatchManager.create_blind_match_request(g.user.user_id, receiver_id)
    return jsonify(result)

@app.route('/api/blind-match/<int:match_id>/respond/<action>', methods=['POST'])
@login_required
def api_respond_blind_match(match_id, action):
    result = BlindMatchManager.respond_to_blind_match_request(match_id, g.user.user_id, action)
    return jsonify(result)

@app.route('/api/blind-match/<int:match_id>/send-profile', methods=['POST'])
@login_required
def api_send_blind_profile(match_id):
    result = BlindMatchManager.send_profile_and_create_match_request(match_id, g.user.user_id)
    return jsonify(result)

@app.route('/api/blind-match/<int:match_id>/end', methods=['POST'])
@login_required
def api_end_blind_match(match_id):
    result = BlindMatchManager.end_blind_match(match_id, g.user.user_id)
    return jsonify(result)

@app.route('/api/blind-chat/<string:match_code>/messages')
@login_required
def api_get_blind_chat_messages(match_code):
    match = BlindMatch.query.filter_by(match_code=match_code).first_or_404()
    if g.user.user_id not in [match.user1_id, match.user2_id]:
        return jsonify({'error': 'Unauthorized'}), 403

    response_data = {'status': match.status.value}

    # 실시간 버튼 상태 업데이트를 위해 프로필 전송 상태를 계산하여 전달합니다.
    i_am_user1 = g.user.user_id == match.user1_id
    profile_sent_by_me = (i_am_user1 and match.status == BlindMatchStatus.REVEAL_REQUESTED_BY_1) or \
                         (not i_am_user1 and match.status == BlindMatchStatus.REVEAL_REQUESTED_BY_2)
    
    profile_sent_by_partner = (i_am_user1 and match.status == BlindMatchStatus.REVEAL_REQUESTED_BY_2) or \
                              (not i_am_user1 and match.status == BlindMatchStatus.REVEAL_REQUESTED_BY_1)
    response_data['profile_status'] = {
        "i_sent": profile_sent_by_me,
        "partner_sent": profile_sent_by_partner,
    }

    # If the match is over, no need to process messages further, just inform the client.
    terminal_states = [
        BlindMatchStatus.ENDED_BY_USER,
        BlindMatchStatus.ENDED_BY_TIMEOUT,
        BlindMatchStatus.REJECTED,
        BlindMatchStatus.CANCELLED
    ]
    if match.status in terminal_states:
        return jsonify(response_data)

    # If profiles are revealed, provide the redirect URL to the general match detail page.
    if match.status == BlindMatchStatus.REVEALED:
        general_match = MatchRequest.query.filter(
            ((MatchRequest.sender_id == match.user1_id) & (MatchRequest.receiver_id == match.user2_id)) |
            ((MatchRequest.sender_id == match.user2_id) & (MatchRequest.receiver_id == match.user1_id))
        ).first()
        if general_match:
            response_data['redirect_url'] = url_for('match_detail', request_id=general_match.request_id)
        else:
            response_data['redirect_url'] = url_for('blind_inbox')
        return jsonify(response_data)

    partner_id = match.user2_id if match.user1_id == g.user.user_id else match.user1_id
    unread_messages = BlindMatchMessage.query.filter_by(match_id=match.id, sender_id=partner_id, is_read=False).all()
    for msg in unread_messages:
        msg.is_read = True
    if unread_messages:
        db.session.commit()

    messages = BlindMatchMessage.query.filter_by(match_id=match.id).order_by(BlindMatchMessage.created_at.asc()).all()
    msg_list = []
    for m in messages:
        kst_time = m.created_at + timedelta(hours=9)
        msg_list.append({
            'id': m.id,
            'sender_id': m.sender_id,
            'content': m.content,
            'created_at': kst_time.strftime('%H:%M'),
            'is_me': m.sender_id == g.user.user_id,
            'is_read': m.is_read
        })
    
    response_data['messages'] = msg_list
    return jsonify(response_data)

@app.route('/api/blind-chat/<string:match_code>/send', methods=['POST'])
@login_required
def api_send_blind_chat_message(match_code):
    match = BlindMatch.query.filter_by(match_code=match_code).first_or_404()
    if g.user.user_id not in [match.user1_id, match.user2_id]:
        return jsonify({'error': 'Unauthorized'}), 403

    content = request.json.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Empty message'}), 400

    content = str(escape(content))

    msg = BlindMatchMessage(match_id=match.id, sender_id=g.user.user_id, content=content)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'success': True})

def schedule_system_jobs():
    """스케줄러에 시스템 자동화 작업을 등록합니다."""

    app.logger.info("스케줄링 작업을 설정합니다...")
    # ID를 지정하여 중복 등록 방지
    if not scheduler.get_job('cleanup_expired_requests'):
        scheduler.add_job(id='cleanup_expired_requests',
                          func=BlindMatchManager.cleanup_expired_requests,
                          trigger='interval',
                          hours=1, args=[app])
        
        app.logger.info("-> 'cleanup_expired_requests' 작업이 1시간 간격으로 등록되었습니다.")
    
    if not scheduler.get_job('timeout_inactive_matches'):
        scheduler.add_job(id='timeout_inactive_matches',
                          func=BlindMatchManager.timeout_inactive_matches,
                          trigger='interval',
                          hours=6, args=[app])
        
        app.logger.info("-> 'timeout_inactive_matches' 작업이 6시간 간격으로 등록되었습니다.")

if __name__ == '__main__':
    import sys


    with app.app_context():
        db.create_all()
        check_and_update_db_schema()

    # 스케줄러 시작
    scheduler.start()
    
    # 개발 환경에서 리로더로 인한 중복 실행을 방지하기 위해 werkzeug reloader 감지
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        with app.app_context():
            schedule_system_jobs()

    app.run(host=config_class.RUN_HOST, port=config_class.RUN_PORT, use_reloader=app.debug)